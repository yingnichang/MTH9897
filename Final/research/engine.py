"""Input validation, portfolio selection and monthly backtest accounting.

The notebook (`build_notebook.py`) and the tests import this module, so both exercise the same code.

Selection at each quarter-end formation follows the paper's order (p. 4) and the adopted decisions
(memory/decisions.md: DATA-001, NB-007):

    eligible & hist36 -> largest `n_universe` by market cap (all of them when fewer exist)
    -> low-volatility pool: the floor(N/2) members with the lowest vol36 (ties by permno)
    -> rank momentum and NPY (descending, average ties) among pool members with both signals
    -> best `n_hold` by mean rank (ties by permno), equal weight.

The backtest grows holdings with `ret_hold` (DATA-002, DATA-010): CRSP's return where observed, the
price ratio or 0 in a missing-return month. It never fills `ret_hold` itself; a held position whose
`ret_hold` is NaN, or whose row is missing, raises.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from crsp_pipeline import config
from crsp_pipeline.normalize import HOLD_SOURCES, consecutive
from crsp_pipeline.signals import build_signals

STRATEGIES = ["Conservative", "No momentum", "No payout", "No low-vol screen",
              "Low volatility only", "Universe equal weight", "Universe cap weight"]
RANKED = {"Conservative": ("momentum", "npy"), "No momentum": ("npy",), "No payout": ("momentum",),
          "No low-vol screen": ("momentum", "npy"), "Conservative buffer": ("momentum", "npy")}
# Paper controls (p. 4 and Table 1): the Speculative mirror image and three standalone portfolios.
PAPER_CONTROLS = ["Speculative", "Standalone low-vol", "Standalone momentum", "Standalone NPY", "Small"]
STANDALONE = {"Standalone low-vol": ("vol36", True), "Standalone momentum": ("momentum", False),
              "Standalone NPY": ("npy", False)}          # signal, True if low values are best
# Phase 5 declared improvement (decisions.md 2026-10-11; experiments/2026-10-11-rank-buffer): a named extension.
EXTENSIONS = ["Conservative buffer"]
BUFFER_N = 150                  # keep a holding still in the low-vol pool and ranked within the top 150 (declared)
ALL_STRATEGIES = STRATEGIES + PAPER_CONTROLS + EXTENSIONS
COUNT_FIELDS = ["eligible_n", "history_eligible_n", "universe_n", "low_vol_pool_n",
                "pool_missing_momentum_n", "pool_missing_npy_n", "signal_complete_n", "selected_n",
                "score_ties_at_cut", "ranking_pool_n"]
STALE_SOURCES = ("stale_carry", "price_ratio")
DEFAULT_HOLDINGS = config.HOLDINGS
SIGNAL_COLUMNS = ["vol36", "momentum", "div_yield", "net_issuance", "npy"]


# --- Inputs -----------------------------------------------------------------------------------

STOCK_FIELDS = {"date", "permno", "ret_total", "ret_price", "price_adj", "div_cash_adj", "shares_adj",
                "mktcap", "eligible", "is_exit", "hist36", "ret_hold", "ret_hold_source"}
NUMERIC_FIELDS = ["ret_total", "ret_price", "price_adj", "div_cash_adj", "shares_adj", "mktcap", "ret_hold"]
FLAG_FIELDS = ["eligible", "is_exit", "hist36"]


def validate_inputs(panel: pd.DataFrame, benchmark: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Check the panel contract (docs/DATA_CONVENTIONS.md) and the benchmark; return typed copies."""
    p, b = panel.copy(), benchmark.copy()
    missing = STOCK_FIELDS - set(p.columns)
    if missing:
        raise ValueError(f"Missing stock fields: {sorted(missing)}")
    if not {"date", "market_ret", "rf"}.issubset(b.columns):
        raise ValueError("Benchmark requires date, market_ret, rf")
    for df in (p, b):
        df["date"] = pd.to_datetime(df["date"], errors="raise")
        if df["date"].isna().any() or not df["date"].dt.is_month_end.all():
            raise ValueError("Dates must be calendar month ends")
    if p["permno"].isna().any():
        raise ValueError("Missing security identifier")
    if p.duplicated(["permno", "date"]).any() or b.duplicated("date").any():
        raise ValueError("Duplicate security-month or benchmark month")
    for col in NUMERIC_FIELDS:
        p[col] = pd.to_numeric(p[col], errors="raise")
        if np.isinf(p[col]).any():
            raise ValueError(f"Infinite values in {col}")
    for col in FLAG_FIELDS:
        if not p[col].isin([0, 1]).all():
            raise ValueError(f"{col} must be explicit 0 or 1")
        p[col] = p[col].astype(bool)
    for col in ("ret_total", "ret_price", "ret_hold"):
        if (p[col].dropna() < -1).any():
            raise ValueError(f"{col} below -100%; check missing-value codes")
    for col in ("mktcap", "price_adj", "shares_adj"):
        if (p.loc[p["eligible"] & ~p["is_exit"], col].dropna() <= 0).any():
            raise ValueError(f"Nonpositive {col} on eligible nonterminal row")
    if (p["div_cash_adj"].dropna() < 0).any():
        raise ValueError("Negative dividends require upstream reconciliation")

    src = p["ret_hold_source"]
    if not src.isin(HOLD_SOURCES).all():
        raise ValueError(f"Unknown ret_hold_source values {sorted(set(src) - set(HOLD_SOURCES))}")
    if not p["ret_hold"].isna().eq(src.eq("no_prior_row")).all():
        raise ValueError("ret_hold is NaN outside no_prior_row (or no_prior_row has a value)")
    observed = p["ret_total"].notna()
    if p.loc[observed, "ret_hold"].ne(p.loc[observed, "ret_total"]).any():
        raise ValueError("ret_hold differs from ret_total where the total return is observed")

    for col in ("market_ret", "rf"):
        b[col] = pd.to_numeric(b[col], errors="raise")
        if not np.isfinite(b[col]).all() or (b[col] <= -1).any():
            raise ValueError(f"Invalid benchmark field {col}")
    b = b.set_index("date").sort_index()
    if not pd.date_range(b.index.min(), b.index.max(), freq="ME").equals(b.index):
        raise ValueError("Benchmark calendar has gaps")

    p = p.sort_values(["permno", "date"]).reset_index(drop=True)
    exits = p.loc[p["is_exit"], ["permno", "date"]]
    if exits["permno"].duplicated().any():
        raise ValueError("Multiple terminal rows for a security")
    if not exits.empty:
        last = p.groupby("permno")["date"].max()
        if (exits["date"].to_numpy() != last.loc[exits["permno"]].to_numpy()).any():
            raise ValueError("Observations after terminal exit need reconciliation")
    return p, b


def make_demo(seed: int = 9897, n_stocks: int = 1100) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Synthetic fixed-universe panel; deliberately NOT calibrated to reproduce the paper."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2000-01-31", "2025-12-31", freq="ME")
    nt = len(dates)
    market = rng.normal(.005, .04, nt)
    rf = np.full(nt, .0015)
    beta = rng.uniform(.5, 1.5, n_stocks)
    residual_vol = rng.uniform(.02, .10, n_stocks)
    ret = np.clip(.001 + market[:, None] * beta +
                  rng.normal(size=(nt, n_stocks)) * residual_vol, -.85, 1.5)
    div_rate = rng.uniform(0, .004, n_stocks)
    price_ret = ret - div_rate
    price = 40 * np.cumprod(1 + price_ret, axis=0)
    lag_price = np.vstack([np.full(n_stocks, 40.), price[:-1]])
    div = lag_price * div_rate
    initial_shares = rng.lognormal(17, 1.0, n_stocks)
    issuance = rng.normal(0, .004, (nt, n_stocks))
    shares = initial_shares * np.cumprod(1 + issuance, axis=0)
    frame = pd.DataFrame({"date": np.repeat(dates, n_stocks),
                          "permno": np.tile(np.arange(10000, 10000 + n_stocks), nt),
                          "ret_total": ret.ravel(), "ret_price": price_ret.ravel(),
                          "price_adj": price.ravel(), "div_cash_adj": div.ravel(),
                          "shares_adj": shares.ravel(), "mktcap": (price * shares).ravel(),
                          "eligible": True, "is_exit": False})
    frame = frame.sort_values(["permno", "date"]).reset_index(drop=True)
    frame["hist36"] = consecutive(frame, frame["ret_total"].notna(), config.HISTORY_MONTHS)
    frame["ret_hold"] = frame["ret_total"]            # every synthetic return is observed
    frame["ret_hold_source"] = "crsp"
    bench = pd.DataFrame({"date": dates, "market_ret": market, "rf": rf})
    return frame, bench


# --- Signals ----------------------------------------------------------------------------------

def attach_signals(panel: pd.DataFrame) -> pd.DataFrame:
    """Panel plus the five formation signals of `crsp_pipeline.signals.build_signals`.

    Merged on (permno, date) one-to-one; every panel column and row is kept in the panel's order.
    """
    clash = [c for c in SIGNAL_COLUMNS if c in panel.columns]
    if clash:
        raise ValueError(f"Panel already has signal columns {clash}")
    if panel.duplicated(["permno", "date"]).any():
        raise ValueError("Duplicate (permno, date) rows; signals need one row per security-month")
    sig = build_signals(panel)[["permno", "date", *SIGNAL_COLUMNS]]
    out = panel.merge(sig, on=["permno", "date"], how="left", validate="one_to_one")
    if len(out) != len(panel):
        raise ValueError(f"Signal merge changed the row count: {len(panel)} -> {len(out)}")
    out.index = panel.index
    return out


# --- Selection --------------------------------------------------------------------------------

def resolve_n_hold(n_hold: int | str, universe_n: int) -> int:
    """An int, or "pct10" = floor(0.10 x universe size) (DATA-001 sensitivity)."""
    if n_hold == "pct10":
        return int(np.floor(0.10 * universe_n))
    if isinstance(n_hold, (int, np.integer)) and not isinstance(n_hold, bool) and n_hold > 0:
        return int(n_hold)
    raise ValueError(f"n_hold must be a positive int or 'pct10', got {n_hold!r}")


def history_eligible(snapshot: pd.DataFrame) -> pd.DataFrame:
    s = snapshot
    return s.loc[s["eligible"].eq(True) & s["hist36"].eq(True) & ~s["is_exit"].eq(True) & s["mktcap"].gt(0)]


def select_universe(snapshot: pd.DataFrame, n_universe: int = config.UNIVERSE_SIZE) -> pd.DataFrame:
    """History screen first, then the n_universe largest by market cap (ties by permno), or all when fewer."""
    pool = history_eligible(snapshot)
    return pool.sort_values(["mktcap", "permno"], ascending=[False, True]).head(n_universe)


def _best(candidates: pd.DataFrame, score: pd.Series, n: int) -> tuple[pd.DataFrame, int]:
    """The n lowest scores (ties by permno) and the number of other names sharing the cut score."""
    ranked = candidates.assign(_score=score).sort_values(["_score", "permno"])
    chosen = ranked.head(n)
    ties = int(ranked["_score"].eq(chosen["_score"].iloc[-1]).sum()) - 1
    return chosen, ties


def _buffered(candidates: pd.DataFrame, score: pd.Series, n: int, holdings: pd.Series | None,
              buffer_n: int) -> tuple[pd.DataFrame, int, int]:
    """Rank buffer: keep current holdings ranked within the best `buffer_n`, fill up to n with the best others.
    Returns the chosen rows, the ties at the fill cut and the number kept."""
    ranked = candidates.assign(_score=score).sort_values(["_score", "permno"])
    held = set() if holdings is None else set(holdings.index)
    keep = ranked.head(buffer_n).loc[lambda d: d["permno"].isin(held)]
    if len(keep) > n:
        raise ValueError(f"{len(keep)} kept holdings exceed the {n} slots")
    others = candidates.loc[~candidates["permno"].isin(keep["permno"])]
    fill, ties = _best(others, score.loc[others.index], n - len(keep)) if n > len(keep) else (others.iloc[:0], 0)
    return pd.concat([keep.drop(columns="_score"), fill.drop(columns="_score", errors="ignore")]), ties, len(keep)


def choose_weights(snapshot: pd.DataFrame, name: str, n_universe: int = config.UNIVERSE_SIZE,
                   n_hold: int | str = DEFAULT_HOLDINGS, holdings: pd.Series | None = None,
                   buffer_n: int = BUFFER_N) -> tuple[pd.Series, dict]:
    """Target weights (indexed by permno, summing to 1) and per-formation counts for one strategy.

    For the ranked strategies the counts describe the pool the strategy ranks over (`ranking_pool_n`):
    the low-vol pool, the whole universe for "No low-vol screen", or the high-volatility part for
    "Speculative" (`low_vol_pool_n` is None for the last two).

    Speculative (paper p. 4): the N - floor(N/2) universe members outside the low-vol pool; momentum and
    NPY are ranked ascending among members with both signals (the weakest gets rank 1) and the
    `n_hold` lowest mean ranks are held. Standalone portfolios (Table 1): the `n_hold` universe members
    with the lowest vol36, highest momentum or highest NPY, complete cases on that signal only.

    Small (Table 1; paper-targets task): the `n_hold` smallest universe members by market cap (ties by
    permno), equal weight.

    Conservative buffer (Phase 5 extension): the Conservative pool and combined score; a current holding
    (`holdings`, the previous formation's target) is kept if it is a signal-complete pool member ranked within
    the best `buffer_n` (order: score, then permno); the other slots are filled with the best-ranked
    non-holdings; equal weight. Every other strategy ignores `holdings`.
    """
    if name not in ALL_STRATEGIES:
        raise ValueError(f"Unknown strategy {name!r}")
    universe = select_universe(snapshot, n_universe)
    n = len(universe)
    if n == 0:
        raise ValueError("Empty universe")
    if universe["vol36"].isna().any():
        raise ValueError(f"vol36 missing for {int(universe['vol36'].isna().sum())} universe members; "
                         "hist36 should guarantee it")
    hold = resolve_n_hold(n_hold, n)
    counts = {"eligible_n": int(snapshot["eligible"].eq(True).sum()),
              "history_eligible_n": len(history_eligible(snapshot)), "universe_n": n,
              "low_vol_pool_n": None, "pool_missing_momentum_n": None, "pool_missing_npy_n": None,
              "signal_complete_n": int(universe[["momentum", "npy"]].notna().all(axis=1).sum()),
              "selected_n": 0, "score_ties_at_cut": 0, "ranking_pool_n": None}

    by_vol = universe.sort_values(["vol36", "permno"])
    if name == "Small":
        chosen, counts["score_ties_at_cut"] = _best(universe, universe["mktcap"], hold)
        weights = pd.Series(1 / hold, index=chosen["permno"].to_numpy())
    elif name.startswith("Universe"):
        sel = universe.set_index("permno")
        weights = (sel["mktcap"] / sel["mktcap"].sum() if name.endswith("cap weight")
                   else pd.Series(1 / n, index=sel.index))
    elif name in ("Low volatility only", "Standalone low-vol", "Standalone momentum", "Standalone NPY"):
        col, low_is_best = STANDALONE.get(name, ("vol36", True))
        complete = universe.dropna(subset=[col])
        counts["signal_complete_n"] = len(complete)
        if len(complete) < hold:
            raise ValueError(f"Only {len(complete)} universe members with {col} for {name}; need {hold}")
        score = complete[col] if low_is_best else -complete[col]
        chosen, counts["score_ties_at_cut"] = _best(complete, score, hold)
        weights = pd.Series(1 / hold, index=chosen["permno"].to_numpy())
    else:
        speculative = name == "Speculative"
        pool = (universe if name == "No low-vol screen" else by_vol.iloc[n // 2:] if speculative
                else by_vol.head(n // 2))
        counts["ranking_pool_n"] = len(pool)
        if name not in ("No low-vol screen", "Speculative"):
            counts["low_vol_pool_n"] = len(pool)
        counts["pool_missing_momentum_n"] = int(pool["momentum"].isna().sum())
        counts["pool_missing_npy_n"] = int(pool["npy"].isna().sum())
        complete = pool.dropna(subset=["momentum", "npy"])
        counts["signal_complete_n"] = len(complete)
        if len(complete) < hold:
            raise ValueError(f"Only {len(complete)} signal-complete pool members for {name}; need {hold}")
        cols = ("momentum", "npy") if speculative else RANKED[name]
        ranks = [complete[c].rank(ascending=speculative, method="average") for c in cols]
        score = sum(ranks) / len(ranks)
        if name == "Conservative buffer":
            chosen, counts["score_ties_at_cut"], counts["buffer_kept_n"] = _buffered(complete, score, hold,
                                                                                     holdings, buffer_n)
        else:
            chosen, counts["score_ties_at_cut"] = _best(complete, score, hold)
        weights = pd.Series(1 / hold, index=chosen["permno"].to_numpy())
    weights.index.name = "permno"
    counts["selected_n"] = len(weights)
    return weights.astype(float), counts


def formation_dates(dates, start: pd.Timestamp, last: pd.Timestamp | None = None) -> list[pd.Timestamp]:
    """Quarter-end months from the month before `start` up to (excluding) `last` (default: last date)."""
    dates = pd.DatetimeIndex(sorted(pd.unique(pd.DatetimeIndex(dates))))
    last = dates.max() if last is None else pd.Timestamp(last)
    first = pd.Timestamp(start) - pd.offsets.MonthEnd(1)
    return [d for d in dates if d.month in (3, 6, 9, 12) and first <= d < last]


def formation_targets(signals: pd.DataFrame, strategies=STRATEGIES, start=None, last=None,
                      n_universe: int = config.UNIVERSE_SIZE, n_hold: int | str = DEFAULT_HOLDINGS,
                      buffer_n: int = BUFFER_N):
    """Targets {strategy: {formation: weights}} and a counts table (one row per formation and strategy).

    `signals` is the panel with `vol36`, `momentum` and `npy` merged on (permno, date). Formations run in
    date order; each strategy's previous target is passed as `holdings` (only the buffer uses it).
    """
    targets = {s: {} for s in strategies}
    rows = []
    cols = ["date", "permno", "eligible", "hist36", "is_exit", "mktcap", "vol36", "momentum", "npy"]
    snaps = signals.loc[signals["date"].isin(formation_dates(signals["date"], start, last)), cols]
    prev = {}
    for date, snap in snaps.groupby("date", sort=True):
        for name in strategies:
            w, c = choose_weights(snap, name, n_universe, n_hold, holdings=prev.get(name), buffer_n=buffer_n)
            prev[name] = w
            targets[name][pd.Timestamp(date)] = w
            rows.append({"formation": pd.Timestamp(date), "strategy": name, **c})
    return targets, pd.DataFrame(rows)


# --- Backtest ---------------------------------------------------------------------------------

def validate_calendar(bench: pd.DataFrame, target_map: dict, start, end) -> pd.DatetimeIndex:
    """The explicit monthly calendar [start, end]; raise on any benchmark or target gap (NB-002).

    Required: every month of the window in the benchmark; a target at the first formation (the month
    before `start`); a target at every quarter-end formation whose holding period starts in the window.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if end < start:
        raise ValueError(f"Backtest end {end.date()} is before start {start.date()}")
    calendar = pd.date_range(start, end, freq="ME")
    if len(calendar) == 0 or calendar[0] != start:
        raise ValueError(f"Backtest start {start.date()} is not a month end")
    missing = calendar.difference(pd.DatetimeIndex(bench.index))
    if len(missing):
        raise ValueError(f"Benchmark lacks {len(missing)} month(s) in the window {start.date()}..{end.date()}; "
                         f"first missing {missing[0].date()}")
    first = start - pd.offsets.MonthEnd(1)
    if first not in target_map:
        raise ValueError(f"No target for the first formation {first.date()}")
    for f in calendar[:-1].union(pd.DatetimeIndex([first])):
        if f.month in (3, 6, 9, 12) and f not in target_map:
            raise ValueError(f"No target for quarter-end formation {f.date()}")
    return calendar


def backtest(p: pd.DataFrame, bench: pd.DataFrame, target_map: dict, start, end, cost_bps: float = 0,
             trade_log: list | None = None, name_costs: dict | None = None) -> pd.DataFrame:
    """Monthly long-only backtest with drift, a proportional cost haircut, exits to cash and rf on cash.

    `bench` is indexed by month-end date with an `rf` column. A target dated at formation month t is
    traded at t and earns returns from t+1. Holdings grow with `ret_hold`. The window is the explicit
    calendar `start`..`end` (`validate_calendar`). `all_cash` flags months that end fully in cash.
    If `trade_log` is a list, one frame per rebalance is appended with security-level pre-trade weights,
    targets and signed trades (cash is not a security; a trade's cash leg is not counted).

    Extensions (linear-optimization task; the paper baseline passes neither and is unchanged):
    - a `target_map` value may be a callable `f(holdings, cash) -> weights`, called at its formation with the
      drifted pre-trade weights (a copy) and cash, for targets that depend on the current portfolio;
    - `name_costs` {formation: Series permno -> cost per dollar traded (a fraction)} replaces `cost_bps`: the
      rebalance charge is sum_i c_i |trade_i|. A traded name without a cost raises.
    """
    if name_costs is not None and cost_bps != 0:
        raise ValueError("Pass cost_bps or name_costs, not both")
    calendar = validate_calendar(bench, target_map, start, end)
    cols = ["date", "permno", "ret_hold", "ret_hold_source", "is_exit"]
    p = p.loc[p["date"].between(calendar[0], calendar[-1]), cols]
    monthly = {d: g.set_index("permno") for d, g in p.groupby("date", sort=False)}
    holdings = pd.Series(dtype=float)
    cash = 1.0
    records = []
    for date in calendar:
        prev = date - pd.offsets.MonthEnd(1)
        traded = name_charge = 0.0
        if prev in target_map:
            new = target_map[prev]
            if callable(new):
                new = new(holdings.copy(), cash)
            assert new.ge(0).all() and np.isclose(new.sum(), 1)
            keys = holdings.index.union(new.index)
            pre, tgt = holdings.reindex(keys, fill_value=0), new.reindex(keys, fill_value=0)
            traded = float((tgt - pre).abs().sum())
            if name_costs is not None:
                size = (tgt - pre).abs()
                c = name_costs[prev].reindex(keys) if prev in name_costs else pd.Series(np.nan, index=keys)
                missing = c.isna() & size.gt(0)
                if missing.any():
                    raise ValueError(f"No cost at {prev.date()} for traded names {keys[missing.to_numpy()].tolist()[:8]}")
                name_charge = float((size * c.fillna(0)).sum())
            if trade_log is not None:
                trade_log.append(pd.DataFrame({"formation": prev, "permno": keys, "pre_weight": pre.to_numpy(),
                                               "target_weight": tgt.to_numpy(), "trade": (tgt - pre).to_numpy(),
                                               "pre_cash": cash}))
            holdings, cash = new.copy(), 0.0
        rf = float(bench.loc[date, "rf"])
        stale = {s: (0, 0.0) for s in STALE_SOURCES}
        if len(holdings):
            if date not in monthly:
                raise ValueError(f"No stock returns for {date}")
            rows = monthly[date].reindex(holdings.index)
            bad = rows["ret_hold"].isna() | rows["is_exit"].isna()
            if bad.any():
                raise ValueError(f"Missing held-stock return/event at {date.date()}: "
                                 f"{rows.index[bad].tolist()[:8]}; reconcile delistings or gaps")
            for s in STALE_SOURCES:
                m = rows["ret_hold_source"].eq(s)
                stale[s] = (int(m.sum()), float(holdings[m].sum()))
            grown = holdings * (1 + rows["ret_hold"])
            exited = rows["is_exit"].astype(bool)
        else:
            grown = pd.Series(dtype=float)
            exited = pd.Series(dtype=bool)
        gross_factor = float(grown.sum() + cash * (1 + rf))
        if gross_factor <= 0:
            raise ValueError("Portfolio exhausted")
        charge = name_charge if name_costs is not None else cost_bps / 10000 * traded
        if charge >= 1:
            raise ValueError("Costs exceed NAV")
        exit_cash = float(grown.loc[exited].sum())
        cash = (cash * (1 + rf) + exit_cash) / gross_factor
        holdings = grown.loc[~exited] / gross_factor
        holdings = holdings.loc[holdings > 1e-14]
        assert np.isclose(holdings.sum() + cash, 1, atol=1e-10)
        records.append({"date": date, "gross": gross_factor - 1,
                        "net": (1 - charge) * gross_factor - 1, "traded_notional": traded,
                        "one_way_turnover": traded / 2, "cost_fraction": charge,
                        "cash_weight": cash, "all_cash": bool(cash >= 1 - 1e-12), "holdings_n": len(holdings),
                        "stale_held_n": sum(n for n, _ in stale.values()),
                        "stale_weight": sum(w for _, w in stale.values()),
                        "stale_carry_n": stale["stale_carry"][0], "stale_carry_weight": stale["stale_carry"][1],
                        "price_ratio_n": stale["price_ratio"][0], "price_ratio_weight": stale["price_ratio"][1]})
    return pd.DataFrame(records).set_index("date")
