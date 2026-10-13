"""Performance statistics, turnover, cost reconciliation and the paper's comparison tables.

Definitions follow the Phase 3 comparison spec (experiments/2026-10-10-paper-replication), fixed
before any CRSP performance figure was read. All inputs are monthly decimal returns indexed by month end.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(r: pd.Series) -> float:
    """Largest fall of the wealth path from its running peak, with initial wealth 1 included."""
    wealth = (1 + r).cumprod()
    peak = wealth.cummax().clip(lower=1.0)
    return float((wealth / peak - 1).min())


def statistics(r: pd.Series, rf: pd.Series) -> dict:
    """Summary statistics of a monthly return series.

    - compounded: (prod(1 + r))^(12/T) - 1
    - arithmetic: 12 x mean(r)
    - volatility: sqrt(12) x sd(r), ddof 1
    - sharpe_paper: arithmetic / volatility. The paper's Table 1 "Sharpe" behaves like this ratio,
      despite its caption (memory/lessons.md); it is labeled and kept apart from the excess version.
    - sharpe_excess: 12 x mean(r - rf) / (sqrt(12) x sd(r - rf)), rf = monthly Fama-French rf
    - max_drawdown: see `max_drawdown`
    """
    r = r.dropna()
    rf = rf.reindex(r.index)
    if rf.isna().any():
        raise ValueError(f"rf missing for {int(rf.isna().sum())} months of the return series")
    ex = r - rf
    vol = float(r.std(ddof=1) * np.sqrt(12))
    ex_vol = float(ex.std(ddof=1) * np.sqrt(12))
    arith = float(12 * r.mean())
    return {"months": len(r), "first": r.index.min().date(), "last": r.index.max().date(),
            "compounded": float(np.prod(1 + r) ** (12 / len(r)) - 1), "arithmetic": arith,
            "volatility": vol, "sharpe_paper": arith / vol if vol > 0 else np.nan,
            "sharpe_excess": float(12 * ex.mean()) / ex_vol if ex_vol > 0 else np.nan,
            "max_drawdown": max_drawdown(r)}


# --- Paper Table 1 definitions (decisions.md 2026-10-11: targets confirmed from the PDF) ---------------

PAPER_TARGET_VOL = 0.165        # Table 1: the Formula's volatility, the common risk level


def sharpe_simple(simple: float, vol: float) -> float:
    """Table 1 "Sharpe": simple (arithmetic) return / volatility, with no T-bill subtracted."""
    return simple / vol


def derisking_factor(vol: float, target: float = PAPER_TARGET_VOL) -> float:
    """Table 1 "De-risking factor": target volatility / volatility."""
    return target / vol


def return_same_risk(simple: float, vol: float, rf: float, target: float = PAPER_TARGET_VOL) -> float:
    """Table 1 "Return same risk": rf + (simple - rf) x target / vol."""
    return rf + (simple - rf) * derisking_factor(vol, target)


def rebalance_months(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Months in which a quarter-end target is traded (the month after March, June, September, December)."""
    prev = index - pd.offsets.MonthEnd(1)
    return index[prev.month.isin([3, 6, 9, 12])]


def quarterly_turnover(run: pd.DataFrame) -> dict:
    """One-way, single-counted turnover per quarterly rebalance: 0.5 x traded_notional, averaged over
    rebalances, excluding the initial investment (the first month of the run)."""
    months = rebalance_months(run.index)
    months = months[months > run.index.min()]
    one_way = 0.5 * run.loc[months, "traded_notional"]
    return {"rebalances": len(months), "one_way_per_quarter": float(one_way.mean()),
            "initial_traded_notional": float(run["traded_notional"].iloc[0])}


def cost_reconciliation(run: pd.DataFrame, bps: float) -> dict:
    """Implied annual cost (turnover x 2 x 4 x c) against the engine's gross-minus-net drag.

    The engine charges c x traded_notional as a proportional NAV haircut in the rebalance month, so
    its monthly drag is c x traded x (1 + gross), close to c x traded. Both drags are annualized:
    arithmetic as 12 x mean(gross - net), compounded as the difference of compounded annual returns.
    """
    c = bps / 10_000
    t = quarterly_turnover(run)
    gross, net = run["gross"], run["net"]
    comp = lambda r: float(np.prod(1 + r) ** (12 / len(r)) - 1)
    return {"bps": bps, "one_way_per_quarter": t["one_way_per_quarter"],
            "implied_annual_cost": t["one_way_per_quarter"] * 2 * 4 * c,
            "engine_arithmetic_drag": float(12 * (gross - net).mean()),
            "engine_compounded_drag": comp(gross) - comp(net)}


def table(series: dict[str, pd.Series], rf: pd.Series) -> pd.DataFrame:
    """One row of `statistics` per named series."""
    return pd.DataFrame({name: statistics(r, rf) for name, r in series.items()}).T


def decade_label(year: int, first: pd.Timestamp, last: pd.Timestamp) -> str:
    lo, hi = max(year, first.year), min(year + 9, last.year)
    full = lo == year and hi == year + 9 and first <= pd.Timestamp(f"{year}-01-31") and last >= pd.Timestamp(f"{year + 9}-12-31")
    span = f"{lo}" if lo == hi else f"{lo}–{hi}"
    return f"{year}s" if full else f"{year}s ({span}, partial)"


def by_decade(series: dict[str, pd.Series]) -> pd.DataFrame:
    """Compounded annual return by calendar decade; partial decades are labeled with their years."""
    out = {}
    for name, r in series.items():
        r = r.dropna()
        dec = r.index.year // 10 * 10
        out[name] = r.groupby(dec).apply(lambda x: np.prod(1 + x) ** (12 / len(x)) - 1)
    t = pd.DataFrame(out)
    idx = pd.DatetimeIndex(next(iter(series.values())).dropna().index)
    months = pd.Series(1, index=idx).groupby(idx.year // 10 * 10).size()
    t.insert(0, "months", months)
    t.index = [decade_label(d, idx.min(), idx.max()) for d in t.index]
    t.index.name = "decade"
    return t


# --- Critical tests (RS-006): fixed periods, net series at any cost, break-even ----------------

PERIODS = {"1929–1962": ("1929-01-31", "1962-12-31"), "1963–1989": ("1963-01-31", "1989-12-31"),
           "1990–2016": ("1990-01-31", "2016-12-31"), "2017–2024": ("2017-01-31", "2024-12-31"),
           "1990–2024": ("1990-01-31", "2024-12-31")}          # decisions.md RS-006; 1990-2024 is the headline


def period_slice(s, name: str):
    """The months of a fixed RS-006 period; raise if the series does not cover all of them."""
    lo, hi = (pd.Timestamp(x) for x in PERIODS[name])
    expected = pd.date_range(lo, hi, freq="ME")
    out = s.loc[lo:hi]
    if not pd.DatetimeIndex(out.index).equals(expected):
        raise ValueError(f"Series does not cover the period {name} ({len(out)} of {len(expected)} months)")
    return out


def net_from_gross(run: pd.DataFrame, bps: float) -> pd.Series:
    """The engine's net series at any cost level: (1 - c x traded_notional) x (1 + gross) - 1.

    Exact for `engine.backtest`: its proportional haircut rescales holdings, so the weights and
    traded notional do not depend on the cost level (tests/test_report.py checks this against the engine).
    """
    return (1 - bps / 10_000 * run["traded_notional"]) * (1 + run["gross"]) - 1


def breakeven(f, lo: float = 0.0, hi: float = 2000.0, tol: float = 0.5) -> dict:
    """The cost (bps per dollar traded) at which the decreasing function f(bps) crosses zero, by bisection.

    Returns status "<= 0" without searching if f(lo) <= 0, and "> hi" if f(hi) > 0.
    """
    f_lo = f(lo)
    if f_lo <= 0:
        return {"status": "<= 0", "bps": np.nan, "value_at_zero_cost": f_lo}
    if f(hi) > 0:
        return {"status": f"> {hi:g}", "bps": np.nan, "value_at_zero_cost": f_lo}
    a, b = lo, hi
    while b - a > tol:
        mid = (a + b) / 2
        a, b = (mid, b) if f(mid) > 0 else (a, mid)
    return {"status": "found", "bps": (a + b) / 2, "value_at_zero_cost": f_lo}


# --- Uncertainty of performance statistics: moving-block bootstrap (critical-tests R1) -----------

def block_indices(n: int, block: int = 12, reps: int = 5000, seed: int = 9897) -> np.ndarray:
    """reps x n index draws: consecutive blocks of `block` months with uniform random starts in
    [0, n - block], concatenated and cut to n (moving-block bootstrap, no wrap-around)."""
    rng = np.random.default_rng(seed)
    k = -(-n // block)
    starts = rng.integers(0, n - block + 1, size=(reps, k))
    return (starts[:, :, None] + np.arange(block)).reshape(reps, k * block)[:, :n]


def bootstrap_statistics(r: pd.Series, rf: pd.Series, block: int = 12, reps: int = 5000,
                         seed: int = 9897) -> dict:
    """Bootstrap SE and 2.5/97.5 percentile CI of compounded, arithmetic, volatility, sharpe_paper and
    sharpe_excess (definitions as in `statistics`). The return and rf months are resampled together.
    Max drawdown is a path statistic and gets no interval."""
    r = r.dropna()
    rfv = rf.reindex(r.index).to_numpy(float)
    rv = r.to_numpy(float)
    idx = block_indices(len(rv), block, reps, seed)
    R, F = rv[idx], rfv[idx]
    T = R.shape[1]
    arith = 12 * R.mean(axis=1)
    vol = np.sqrt(12) * R.std(axis=1, ddof=1)
    ex = R - F
    draws = {"compounded": np.prod(1 + R, axis=1) ** (12 / T) - 1, "arithmetic": arith, "volatility": vol,
             "sharpe_paper": arith / vol,
             "sharpe_excess": 12 * ex.mean(axis=1) / (np.sqrt(12) * ex.std(axis=1, ddof=1))}
    out = {}
    for k, d in draws.items():
        out[f"{k}_se"] = float(np.std(d, ddof=1))
        out[f"{k}_ci95_low"], out[f"{k}_ci95_high"] = (float(x) for x in np.percentile(d, [2.5, 97.5]))
    return out
