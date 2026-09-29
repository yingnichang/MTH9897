"""Common evaluator for Table 4 strategies and the exact benchmark for random selection.

A strategy is a table of monthly simple returns indexed by month: a Series for one path (a
deterministic rule), or a DataFrame with one column per path (the random strategies). Over a
window, a path's holding return is W - 1, where W is the product of its gross returns over the
window's months: wealth starts at 1 in every window's first month. W comes from cumulative log
gross returns, as the difference of two cumulative sums. The T-bill and VW market wealth are
compounded separately over the same months, and comparisons are strict and made on wealth, so a
tie with a benchmark does not count as beating it.

Statistics follow Part 1: mean, sd (ddof=1), median, standardized skewness m3 / m2^1.5 with
biased central moments (NaN when all outcomes are equal), and the strict shares of outcomes
above zero, the T-bill and the market. evaluate() returns two tables:
  windows  one row per window, statistics across paths ("single realization" for one path);
  pooled   one row per window kind, over all path x window outcomes, each weighted equally
           ("across historical windows" for one path).

exact_random_moments() gives the exact moments of the holding return when one industry is drawn
uniformly from the eligible set A_t each month, independently across months, conditional on the
historical returns r and the eligible sets:
    E[W^k] = prod_t (1 / |A_t|) sum_{i in A_t} (1 + r_{i,t})^k,   k = 1, ..., 4.
With k = 1 this is the wealth of a portfolio rebalanced monthly to equal weights across the
eligible industries. The moments are evaluated in the normalized form used by
table1_sim.exact_moments, which avoids cancellation in short windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from ff_data import require_same_months

PAPER_TABLE4 = Path(__file__).resolve().parents[1] / "data" / "paper" / "table4.csv"

WINDOW_COLUMNS = ["kind", "start", "end", "n_months"]
STATS = ["mean", "median", "skew", "pct_positive", "pct_above_tbill", "pct_above_vw"]
STAT_LABELS = {"mean": "Holding return: mean", "median": "Holding return: median",
               "skew": "Holding return: skewness", "pct_positive": "% > 0", "pct_above_tbill": "% > T-bill",
               "pct_above_vw": "% > VW market"}
# Window kinds that correspond to Table 4's columns, and the paper's horizon_years for each.
HORIZONS = {"year": "1-year", "decade": "10-year", "full": "full period"}
PAPER_HORIZONS = {1: "1-year", 10: "10-year", 90: "full period"}

# The paper's first decade runs from the sample start to December 1936 (Section 3.2).
FIRST_DECADE_END = pd.Period("1936-12", "M")
EARLIEST_START, LATEST_START = pd.Period("1926-07", "M"), pd.Period("1927-01", "M")


class CheckError(ValueError):
    """A simulated result disagrees with its exact benchmark beyond the declared tolerance."""


# ----------------------------------------------------------------------------------------------
# Windows


def _period(year: int, month: int) -> pd.Period:
    return pd.Period(year=year, month=month, freq="M")


def custom_windows(kind: str, spans) -> pd.DataFrame:
    """Windows of one kind from (start, end) month pairs, both inclusive."""
    rows = []
    for start, end in spans:
        start, end = pd.Period(start, "M"), pd.Period(end, "M")
        if end < start:
            raise ValueError(f"{kind} window ends ({end}) before it starts ({start})")
        rows.append((kind, start, end, end.ordinal - start.ordinal + 1))
    return pd.DataFrame(rows, columns=WINDOW_COLUMNS)


def calendar_years(months: pd.PeriodIndex) -> pd.DataFrame:
    """Every complete January-December year in the months; partial first and last years are dropped."""
    first = months[0].year + (months[0].month != 1)
    last = months[-1].year - (months[-1].month != 12)
    return custom_windows("year", [(_period(y, 1), _period(y, 12)) for y in range(first, last + 1)])


def paper_decades(months: pd.PeriodIndex) -> pd.DataFrame:
    """The paper's non-overlapping decades: the sample start to December 1936, then 1937-1946, ...

    Only decades that end within the months are kept. The start must lie between July 1926 and
    January 1927, so the first decade has 120 to 126 months, as in the paper's convention of
    assigning the second half of 1926 to the first decade.
    """
    start = months[0]
    if not EARLIEST_START <= start <= LATEST_START:
        raise ValueError(f"the paper's first decade needs a start between {EARLIEST_START} and {LATEST_START}, "
                         f"not {start}")
    if months[-1] < FIRST_DECADE_END:
        raise ValueError("the months end before the first decade does")
    spans = [(start, FIRST_DECADE_END)]
    year = FIRST_DECADE_END.year + 1
    while _period(year + 9, 12) <= months[-1]:
        spans.append((_period(year, 1), _period(year + 9, 12)))
        year += 10
    return custom_windows("decade", spans)


def calendar_decades(months: pd.PeriodIndex, first_year: int, kind: str = "decade") -> pd.DataFrame:
    """Non-overlapping ten-year windows, January first_year + 10j to December first_year + 10j + 9,
    keeping those that lie entirely within the months."""
    spans, year = [], first_year
    while _period(year + 9, 12) <= months[-1]:
        if _period(year, 1) >= months[0]:
            spans.append((_period(year, 1), _period(year + 9, 12)))
        year += 10
    return custom_windows(kind, spans)


def full_period(months: pd.PeriodIndex) -> pd.DataFrame:
    return custom_windows("full", [(months[0], months[-1])])


def rolling_windows(months: pd.PeriodIndex, length: int = 120) -> pd.DataFrame:
    """Every window of `length` consecutive months, one starting in each month."""
    if len(months) < length:
        raise ValueError(f"{len(months)} months are fewer than one {length}-month window")
    return custom_windows(f"rolling{length}", [(months[k], months[k + length - 1])
                                               for k in range(len(months) - length + 1)])


def standard_windows(months: pd.PeriodIndex) -> pd.DataFrame:
    """Calendar years, the paper's decades, the full period and rolling 120-month windows."""
    return pd.concat([calendar_years(months), paper_decades(months), full_period(months), rolling_windows(months)],
                     ignore_index=True)


def _overlapping(windows: pd.DataFrame) -> bool:
    ordered = windows.sort_values("start")
    return bool((ordered["start"].to_numpy()[1:] <= ordered["end"].to_numpy()[:-1]).any())


# ----------------------------------------------------------------------------------------------
# Wealth and statistics


def _paths(returns: pd.Series | pd.DataFrame) -> tuple[pd.PeriodIndex, np.ndarray]:
    """The month index and a (months x paths) array of returns, after checking them."""
    if not isinstance(returns, (pd.Series, pd.DataFrame)):
        raise TypeError("returns must be a Series (one path) or a DataFrame (one column per path)")
    index = returns.index
    if not isinstance(index, pd.PeriodIndex) or index.freqstr != "M":
        raise ValueError("returns must be indexed by monthly periods")
    if len(index) and (np.diff(index.asi8) != 1).any():
        raise ValueError("returns must cover consecutive months")
    values = returns.to_numpy(dtype=float)
    values = values[:, None] if values.ndim == 1 else values
    if not np.isfinite(values).all():
        raise ValueError("a strategy return is missing or not finite; a selected return must never be missing")
    if (values <= -1).any():
        raise ValueError("a strategy return is -100% or below")
    return index, values


def _positions(months: pd.PeriodIndex, windows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    a = months.get_indexer(pd.PeriodIndex(windows["start"], freq="M"))
    b = months.get_indexer(pd.PeriodIndex(windows["end"], freq="M"))
    if (a < 0).any() or (b < 0).any():
        raise ValueError("a window starts or ends outside the strategy's months")
    if not np.array_equal(b - a + 1, windows["n_months"].to_numpy()):
        raise ValueError("window lengths do not match their start and end months")
    return a, b


def window_wealth(returns: pd.Series | pd.DataFrame, windows: pd.DataFrame) -> np.ndarray:
    """Gross wealth per window (rows) and path (columns), starting from 1 in each window's first month."""
    months, values = _paths(returns)
    a, b = _positions(months, windows)
    log_wealth = np.zeros((len(months) + 1, values.shape[1]))
    np.cumsum(np.log1p(values), axis=0, out=log_wealth[1:])
    with np.errstate(over="ignore", under="ignore"):
        wealth = np.exp(log_wealth[b + 1] - log_wealth[a])
    if not (np.isfinite(wealth).all() and (wealth > 0).all()):
        raise ValueError("window wealth overflowed or underflowed; it must be finite and positive")
    return wealth


def skewness(x: np.ndarray, axis: int | None = None):
    """table1_sim.sample_skewness along an axis: m3 / m2^1.5, biased central moments, NaN if constant."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return np.nan
    first = x.reshape(-1)[0] if axis is None else np.take(x, [0], axis=axis)
    constant = np.all(x == first, axis=axis)
    d = x - x.mean(axis=axis, keepdims=True)
    d2 = d * d
    m2, m3 = d2.mean(axis=axis), (d2 * d).mean(axis=axis)
    with np.errstate(invalid="ignore", divide="ignore"):
        result = np.where(constant, np.nan, m3 / m2**1.5)
    return float(result) if np.ndim(result) == 0 else result


def _statistics(wealth: np.ndarray, tbill, market, axis: int | None) -> dict:
    """Table 4 statistics of W - 1; comparisons are strict and made on wealth.

    Every statistic must be finite except two that are legitimately unavailable: sd for a single
    outcome, and skewness when all outcomes are equal. Anything else non-finite raises.
    """
    holding = wealth - 1.0
    n = wealth.size if axis is None else wealth.shape[axis]
    with np.errstate(invalid="ignore", divide="ignore"):
        sd = holding.std(axis=axis, ddof=1) if n > 1 else np.full(np.shape(holding.mean(axis=axis)), np.nan)
    stats = {"mean": holding.mean(axis=axis), "sd": sd, "median": np.median(holding, axis=axis),
             "skew": skewness(holding, axis=axis), "pct_positive": (wealth > 1.0).mean(axis=axis),
             "pct_above_tbill": (wealth > tbill).mean(axis=axis), "pct_above_vw": (wealth > market).mean(axis=axis)}
    first = holding.reshape(-1)[0] if axis is None else np.take(holding, [0], axis=axis)
    constant = np.all(holding == first, axis=axis)
    required = {name: True for name in ("mean", "median", "pct_positive", "pct_above_tbill", "pct_above_vw")}
    required["sd"] = n > 1
    required["skew"] = ~constant
    for name, applies in required.items():
        if np.any(applies & ~np.isfinite(stats[name])):
            raise ValueError(f"a computed {name} is not finite where it should be")
    return stats


def basis(n_paths: int, n_windows: int) -> str:
    """What a statistic is computed across, so path and historical-window results are never mixed up."""
    if n_paths > 1:
        return "across paths" if n_windows == 1 else "across paths and windows"
    return "single realization" if n_windows == 1 else "across historical windows"


@dataclass(frozen=True)
class Evaluation:
    windows: pd.DataFrame
    pooled: pd.DataFrame


def evaluate(returns: pd.Series | pd.DataFrame, benchmarks: pd.DataFrame, windows: pd.DataFrame) -> Evaluation:
    """Window-level and pooled Table 4 statistics of a strategy against the T-bill (rf) and VW market (mkt)."""
    require_same_months({"strategy": returns, "benchmarks": benchmarks})
    missing = {"rf", "mkt"} - set(benchmarks.columns)
    if missing:
        raise ValueError(f"benchmarks lack {sorted(missing)}")
    wealth = window_wealth(returns, windows)
    tbill = window_wealth(benchmarks["rf"], windows)[:, 0]
    market = window_wealth(benchmarks["mkt"], windows)[:, 0]
    n_paths = wealth.shape[1]

    by_window = windows.reset_index(drop=True).copy()
    by_window["n_paths"] = n_paths
    by_window["tbill"], by_window["market"] = tbill - 1.0, market - 1.0
    for name, values in _statistics(wealth, tbill[:, None], market[:, None], axis=1).items():
        by_window[name] = values
    by_window["basis"] = basis(n_paths, 1)

    pooled = []
    for kind, rows in by_window.groupby("kind", sort=False).groups.items():
        rows = np.asarray(rows)
        stats = _statistics(wealth[rows], tbill[rows, None], market[rows, None], axis=None)
        pooled.append({"kind": kind, "n_windows": len(rows), "n_paths": n_paths, "n_obs": len(rows) * n_paths,
                       **{name: float(value) for name, value in stats.items()}, "basis": basis(n_paths, len(rows))})
    return Evaluation(by_window, pd.DataFrame(pooled))


# ----------------------------------------------------------------------------------------------
# Exact benchmark for uniform random selection


def _eligible_gross(returns: pd.DataFrame, eligible: pd.DataFrame) -> np.ndarray:
    """Gross returns of eligible industries, NaN elsewhere; raises on an empty set or a missing return."""
    if not (returns.index.equals(eligible.index) and returns.columns.equals(eligible.columns)):
        raise ValueError("returns and eligibility must share months and column order")
    mask = eligible.to_numpy(dtype=bool)
    values = returns.to_numpy(dtype=float)
    empty = ~mask.any(axis=1)
    if empty.any():
        raise ValueError(f"no eligible industry in {returns.index[empty][0]}")
    if (mask & ~np.isfinite(values)).any():
        raise ValueError("an eligible industry has no return")
    if (mask & (values <= -1)).any():
        raise ValueError("an eligible industry has a return of -100% or below")
    return np.where(mask, 1.0 + values, np.nan)


def eligible_mean_returns(returns: pd.DataFrame, eligible: pd.DataFrame) -> pd.Series:
    """Monthly return of equal weights across the eligible industries, rebalanced monthly."""
    return pd.Series(np.nanmean(_eligible_gross(returns, eligible), axis=1) - 1.0, index=returns.index,
                     name="eligible_mean")


def exact_random_moments(returns: pd.DataFrame, eligible: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    """Exact mean, sd, skewness and kurtosis of the holding return of uniform random selection, per window.

    With m_t = mean over A_t of (1 + r) and e = (1 + r) / m_t - 1 (so e averages to zero over A_t),
    E[W^k] / E[W]^k = prod_t mean(1 + e)^k, and u, v, w = E[W^k] / E[W]^k - 1 for k = 2, 3, 4
    give skewness (v - 3u) / u^1.5 and kurtosis (w - 4v + 6u) / u^2 (not excess), as in
    table1_sim.exact_moments. Skewness and kurtosis are NaN when u = 0 (one eligible industry
    throughout the window).
    """
    gross = _eligible_gross(returns, eligible)
    m1 = np.nanmean(gross, axis=1)
    e = gross / m1[:, None] - 1.0
    e2 = np.nanmean(e**2, axis=1)
    e3 = np.nanmean(e**3, axis=1)
    e4 = np.nanmean(e**4, axis=1)
    logs = np.column_stack([np.log(m1), np.log1p(e2), np.log1p(3 * e2 + e3), np.log1p(6 * e2 + 4 * e3 + e4)])
    cumulative = np.vstack([np.zeros((1, 4)), np.cumsum(logs, axis=0)])
    a, b = _positions(returns.index, windows)
    log_mean, log_u, log_v, log_w = (cumulative[b + 1] - cumulative[a]).T
    u, v, w = np.expm1(log_u), np.expm1(log_v), np.expm1(log_w)
    out = windows.reset_index(drop=True).copy()
    out["exact_mean"] = np.expm1(log_mean)
    out["exact_sd"] = np.exp(log_mean) * np.sqrt(u)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["exact_skew"] = np.where(u > 0, (v - 3 * u) / u**1.5, np.nan)
        out["exact_kurt"] = np.where(u > 0, (w - 4 * v + 6 * u) / u**2, np.nan)
    return out


def pool_exact(exact: pd.DataFrame) -> pd.DataFrame:
    """Exact moments of the equally weighted mixture of each kind's windows (the pooled distribution).

    Central moments about the pooled mean c are averaged across windows: with d = mean_j - c,
    E(W-c)^2 = s^2 + d^2, E(W-c)^3 = k3 + 3 s^2 d + d^3 and E(W-c)^4 = k4 + 4 k3 d + 6 s^2 d^2 + d^4,
    where s^2, k3, k4 are window j's central moments.
    """
    rows = []
    for kind, group in exact.groupby("kind", sort=False):
        mean, sd = group["exact_mean"].to_numpy(), group["exact_sd"].to_numpy()
        k3 = np.nan_to_num(group["exact_skew"].to_numpy()) * sd**3
        k4 = np.nan_to_num(group["exact_kurt"].to_numpy()) * sd**4
        c = mean.mean()
        d, s2 = mean - c, sd**2
        m2 = np.mean(s2 + d**2)
        m3 = np.mean(k3 + 3 * s2 * d + d**3)
        m4 = np.mean(k4 + 4 * k3 * d + 6 * s2 * d**2 + d**4)
        rows.append({"kind": kind, "n_windows": len(group), "exact_mean": c, "exact_sd": np.sqrt(m2),
                     "exact_skew": m3 / m2**1.5 if m2 > 0 else np.nan,
                     "exact_kurt": m4 / m2**2 if m2 > 0 else np.nan})
    return pd.DataFrame(rows)


def _require_valid_check_inputs(table: pd.DataFrame) -> None:
    """Numerical validity of the mean check's inputs, enforced before any statistical label."""
    n = table["n_paths"].to_numpy(dtype=float)
    mean, exact_mean = table["mean"].to_numpy(dtype=float), table["exact_mean"].to_numpy(dtype=float)
    exact_sd, exact_skew = table["exact_sd"].to_numpy(dtype=float), table["exact_skew"].to_numpy(dtype=float)
    problems = {
        "has no exact benchmark": np.isnan(exact_mean) & np.isnan(exact_sd),
        "has a path count that is not a positive whole number": ~(np.isfinite(n) & (n >= 1) & (n == np.round(n))),
        "has a non-finite simulated mean": ~np.isfinite(mean),
        "has a simulated mean of -100% or below": np.isfinite(mean) & (mean <= -1),
        "has an invalid exact mean": ~np.isfinite(exact_mean) | (exact_mean <= -1),
        "has an invalid exact SD": ~np.isfinite(exact_sd) | (exact_sd < 0),
        "has no exact skewness although its exact SD is positive": (exact_sd > 0) & ~np.isfinite(exact_skew),
    }
    lines = [f"{int(bad.sum())} row(s) {what}, first: {table.loc[np.argmax(bad), ['kind', 'start', 'end']].tolist()}"
             for what, bad in problems.items() if bad.any()]
    if lines:
        raise CheckError("invalid input to the mean check:\n  " + "\n  ".join(lines))


def mean_check(by_window: pd.DataFrame, exact: pd.DataFrame, family_alpha: float = 0.001,
               skew_limit: float = 10.0, z_floor: float = 4.0, exact_rtol: float = 1e-10) -> pd.DataFrame:
    """Simulated means against the exact means, per window and pooled per kind.

    Numerical validity comes first and is never waived: every path count must be a positive whole
    number, every simulated mean finite and above -100%, and every exact mean and SD valid.
    Otherwise CheckError is raised before any row is labeled, whatever its tail.

    Each row then gets one test (column "test"):
      "exact"  the exact SD is 0, so the outcome is deterministic: simulated and exact gross wealth
               must agree to a relative exact_rtol (column "gap"), in any window kind;
      "z"      a normal-approximation check of z = (mean - exact mean) / se, for windows that do
               not overlap and whose exact skewness is below skew_limit (Part 1's screening
               heuristic; for a pooled row, in every window that is not deterministic);
      "none"   diagnostic only: overlapping (rolling) windows, or exact skewness at or above
               skew_limit. Their z is reported but not enforced.
    For a window, se = exact SD / sqrt(n_paths). For the pooled row of a non-overlapping kind,
    se = sqrt(sum_j SD_j^2) / (J sqrt(n_paths)); windows covering different months are independent
    under independent monthly draws, so this is exact under the sampling model.

    The z limit is max(z_floor, Phi^-1(1 - family_alpha / (2N))), where N counts the z-tested rows in
    this call: a nominal Bonferroni family-wise level for one call (one universe and weighting). The
    normal approximation is not exact, so the level is nominal, not calibrated error control.
    """
    key = ["kind", "start", "end"]
    table = by_window[key + ["n_paths", "mean"]].merge(exact[key + ["exact_mean", "exact_sd", "exact_skew"]],
                                                       on=key, how="left", validate="one_to_one")
    _require_valid_check_inputs(table)
    overlapping = {kind: _overlapping(group) for kind, group in table.groupby("kind", sort=False)}
    deterministic = table["exact_sd"] == 0
    z_ready = ~table["kind"].map(overlapping).astype(bool) & (table["exact_skew"] < skew_limit)
    table["test"] = np.select([deterministic, z_ready], ["exact", "z"], default="none")
    table["se"] = table["exact_sd"] / np.sqrt(table["n_paths"])

    pooled = []
    for kind, group in table.groupby("kind", sort=False):
        if overlapping[kind] or len(group) < 2:
            continue
        if group["n_paths"].nunique() != 1:
            raise CheckError(f"the {kind} windows have different path counts")
        n_paths, tests = group["n_paths"].iloc[0], set(group["test"])
        test = "exact" if tests == {"exact"} else "z" if tests <= {"exact", "z"} else "none"
        pooled.append({"kind": f"{kind} (pooled)", "start": group["start"].min(), "end": group["end"].max(),
                       "n_paths": n_paths, "mean": group["mean"].mean(), "exact_mean": group["exact_mean"].mean(),
                       "exact_sd": np.nan, "exact_skew": group["exact_skew"].max(), "test": test,
                       "se": np.sqrt((group["exact_sd"] ** 2).sum()) / (len(group) * np.sqrt(n_paths))})
    table = pd.concat([table, pd.DataFrame(pooled)], ignore_index=True) if pooled else table

    exact_rows = table["test"] == "exact"
    table["gap"] = (1 + table["mean"]) / (1 + table["exact_mean"]) - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        table["z"] = np.where(exact_rows, np.nan, (table["mean"] - table["exact_mean"]) / table["se"])
    n_tested = int((table["test"] == "z").sum())
    z_limit = max(z_floor, NormalDist().inv_cdf(1 - family_alpha / (2 * max(n_tested, 1))))
    table["z_limit"] = z_limit
    table["check"] = np.select(
        [exact_rows, table["test"] == "z"],
        [np.where(table["gap"].abs() <= exact_rtol, "pass", "fail"),
         np.where(table["z"].abs() <= z_limit, "pass", "fail")],
        default="diagnostic only")
    return table


def enforce_mean_check(checked: pd.DataFrame) -> pd.DataFrame:
    """Raise CheckError on any failed row; otherwise a summary per kind, test and label."""
    failed = checked[checked["check"] == "fail"]
    if len(failed):
        raise CheckError(f"{len(failed)} simulated mean(s) differ from the exact mean (|z| limit "
                         f"{checked['z_limit'].iloc[0]:.2f}; deterministic rows compare gross wealth):\n"
                         + failed[["kind", "start", "end", "test", "mean", "exact_mean", "z", "gap"]]
                         .to_string(index=False))
    grouped = checked.assign(abs_z=checked["z"].abs(), abs_gap=checked["gap"].abs()) \
        .groupby(["kind", "test", "check"], sort=False)
    return grouped.agg(rows=("z", "size"), max_abs_z=("abs_z", "max"), max_abs_gap=("abs_gap", "max")).reset_index()


SHARES = ["pct_positive", "pct_above_tbill", "pct_above_vw"]


def share_standard_errors(by_window: pd.DataFrame) -> pd.DataFrame:
    """Plug-in estimates of the Monte Carlo standard errors of the pooled shares, per non-overlapping kind.

    With estimated window shares p_j over J windows and n paths, se = sqrt(sum_j p_j (1 - p_j)) / (J sqrt n).
    Paths are independent, and under independent monthly draws so are one path's outcomes in windows
    covering different months. Overlapping kinds, and single paths, get NaN: their outcomes are not
    independent draws. The estimate uses estimated, not known, probabilities: it is zero when every
    share is 0 or 1, which does not establish a probability of exactly 0 or 1 (use wilson_interval).
    It measures simulation error conditional on the historical returns, not uncertainty about markets.
    """
    rows = []
    for kind, group in by_window.groupby("kind", sort=False):
        n = group["n_paths"].iloc[0]
        valid = n > 1 and not _overlapping(group)
        row = {"kind": kind}
        for share in SHARES:
            p = group[share].to_numpy()
            row[f"se_{share}"] = np.sqrt((p * (1 - p)).sum()) / (len(group) * np.sqrt(n)) if valid else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def wilson_interval(share, n, level: float = 0.95) -> tuple[np.ndarray, np.ndarray]:
    """Pointwise Wilson score interval for a share estimated from n independent paths.

    Unlike the plug-in standard error, it stays informative at 0% and 100%: with all n paths above a
    benchmark the lower bound is n / (n + z^2). share * n must be a whole number of paths.
    """
    share, n = np.asarray(share, dtype=float), np.asarray(n, dtype=float)
    successes = share * n
    if not np.allclose(successes, np.round(successes), rtol=0, atol=1e-6) or (n < 1).any():
        raise ValueError("share * n must be a whole number of paths, with n >= 1")
    p = np.round(successes) / n
    z = NormalDist().inv_cdf(0.5 + level / 2)
    centre = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    # The bounds are exactly 0 and 1 at the boundaries; set them so rounding cannot move them.
    return np.where(p == 0, 0.0, centre - half), np.where(p == 1, 1.0, centre + half)


def percentile_among(strategy_wealth: np.ndarray, path_wealth: np.ndarray) -> pd.DataFrame:
    """Per window, a strategy's percentile among paths: the share of paths with strictly lower wealth.

    strategy_wealth has one value per window and path_wealth is (windows x paths), both from
    window_wealth over the same windows. Ties are counted separately.
    """
    strategy_wealth = np.asarray(strategy_wealth, dtype=float).reshape(-1)
    if path_wealth.shape[0] != strategy_wealth.size:
        raise ValueError("strategy and path wealth must cover the same windows")
    below = (path_wealth < strategy_wealth[:, None]).sum(axis=1)
    ties = (path_wealth == strategy_wealth[:, None]).sum(axis=1)
    return pd.DataFrame({"percentile": below / path_wealth.shape[1], "paths_below": below, "ties": ties,
                         "n_paths": path_wealth.shape[1]})


def allocation_turnover(weights: pd.DataFrame, returns: pd.DataFrame) -> pd.Series:
    """One-way turnover across industry portfolios at each rebalance.

    At month t it is 0.5 * sum_i |w_target_{i,t} - w_pretrade_{i,t}|, where the pre-trade weights are
    month t-1's targets drifted by month t-1's returns. The first month (the initial investment) is
    NaN and the final liquidation is excluded. A switch in a one-industry strategy is 1 (100%).
    """
    if not returns.index.equals(weights.index) or not returns.columns.equals(weights.columns):
        raise ValueError("weights and returns must share months and column order")
    w = weights.to_numpy(dtype=float)
    if (w < 0).any() or not np.allclose(w.sum(axis=1), 1.0, rtol=0, atol=1e-12):
        raise ValueError("target weights must be non-negative and sum to one each month")
    r = returns.to_numpy(dtype=float)
    held = w > 0
    if (held & ~np.isfinite(r)).any():
        raise ValueError("a held industry has no return")
    grown = np.where(held, w * (1.0 + np.where(held, r, 0.0)), 0.0)
    pretrade = grown[:-1] / grown[:-1].sum(axis=1, keepdims=True)
    turnover = 0.5 * np.abs(w[1:] - pretrade).sum(axis=1)
    return pd.Series(np.r_[np.nan, turnover], index=weights.index, name="turnover")


def performance_summary(returns: pd.Series, rf: pd.Series) -> dict:
    """Annualized figures for one monthly return series; before costs.

    Annualized return is geometric, (terminal wealth)^(12 / months) - 1. Volatility is the monthly
    SD (ddof=1) times sqrt(12). The Sharpe ratio is the mean monthly excess return over T-bills
    divided by its SD, times sqrt(12). Maximum drawdown is the largest fall of wealth, starting at 1,
    from its running peak; the peak and trough are the months at whose ends wealth peaked and bottomed.
    """
    if not returns.index.equals(rf.index):
        raise ValueError("returns and T-bill returns must cover the same months")
    r = returns.to_numpy(dtype=float)
    if not np.isfinite(r).all() or (r <= -1).any():
        raise ValueError("returns must be finite and above -100%")
    wealth = np.r_[1.0, np.cumprod(1.0 + r)]
    drawdown = wealth / np.maximum.accumulate(wealth) - 1.0
    trough = int(np.argmin(drawdown))
    peak = int(np.argmax(wealth[:trough + 1]))
    excess = r - rf.to_numpy(dtype=float)

    def label(k: int) -> str:
        # wealth[k] is wealth at the end of month k - 1; wealth[0] is the start.
        return "start" if k == 0 else str(returns.index[k - 1])

    return {"months": len(r), "terminal wealth": wealth[-1],
            "annualized return": wealth[-1] ** (12 / len(r)) - 1.0,
            "annualized volatility": r.std(ddof=1) * np.sqrt(12),
            # Undefined (NaN) when the excess return never varies.
            "Sharpe ratio": excess.mean() / sd * np.sqrt(12) if (sd := excess.std(ddof=1)) > 0 else np.nan,
            "max drawdown": drawdown[trough], "drawdown peak": label(peak), "drawdown trough": label(trough)}


def classify_against(share, n, threshold: float = 0.5, level: float = 0.95) -> np.ndarray:
    """"above", "below" or "not resolved" relative to a threshold, by the pointwise Wilson interval."""
    low, high = wilson_interval(share, n, level)
    return np.select([low > threshold, high < threshold], ["above", "below"], default="not resolved")


# ----------------------------------------------------------------------------------------------
# Table 4 layout


def table4_layout(pooled: pd.DataFrame, stats=STATS, horizons: dict = HORIZONS) -> pd.DataFrame:
    """Pooled statistics laid out like Table 4: statistics as rows, horizons (by default 1-year, 10-year and
    full period) as columns."""
    rows = pooled.set_index("kind").reindex(list(horizons))
    layout = rows[list(stats)].T
    layout.columns = list(horizons.values())
    layout.index.name = "stat"
    return layout


def load_paper_table4(path: Path = PAPER_TABLE4) -> pd.DataFrame:
    """Bessembinder (2018) Table 4 in long form: stat, horizon_years, n_stocks, value (decimals)."""
    paper = pd.read_csv(path)
    if paper.duplicated(["stat", "horizon_years", "n_stocks"]).any():
        raise ValueError(f"{path} has duplicate (stat, horizon_years, n_stocks) rows")
    return paper


def paper_layout(paper: pd.DataFrame, n_stocks: int) -> pd.DataFrame:
    """The paper's rows for one portfolio size, in the table4_layout shape."""
    rows = paper[paper["n_stocks"] == n_stocks]
    if rows.empty:
        raise ValueError(f"the paper has no {n_stocks}-stock rows")
    layout = rows.pivot(index="stat", columns="horizon_years", values="value").reindex(STATS)
    layout = layout[list(PAPER_HORIZONS)]
    layout.columns = list(PAPER_HORIZONS.values())
    return layout
