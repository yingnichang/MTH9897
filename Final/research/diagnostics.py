"""Factor diagnostics (Instructions.md 1-7C): neutralized exposures, forward returns, IC, decay,
persistence and deciles. Conventions are fixed in experiments/2026-10-11-factor-diagnostics (before any result).

Kept separate from the paper baseline (`research.engine`), which stays long-only and unneutralized.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from crsp_pipeline import config

SIGNALS = ["lowvol", "momentum", "npy"]          # oriented so that higher is better
EXPOSURES = [f"{s}_z" for s in SIGNALS] + ["composite_z"]
MIN_GROUP = 5
CLIP = 3.0


def monthly_universe(panel: pd.DataFrame, start, end, n_universe: int = config.UNIVERSE_SIZE) -> pd.DataFrame:
    """History-first universe at every month-end in [start, end]: eligible, hist36, not terminal, mktcap > 0,
    then the n largest by security market cap (ties by permno), or all of them when fewer (DATA-001).
    Same rule as `research.engine.select_universe`, applied to every month at once."""
    p = panel.loc[panel["date"].between(pd.Timestamp(start), pd.Timestamp(end)) & panel["eligible"].eq(True)
                  & panel["hist36"].eq(True) & ~panel["is_exit"].eq(True) & panel["mktcap"].gt(0)]
    p = p.sort_values(["date", "mktcap", "permno"], ascending=[True, False, True])
    p = p.loc[p.groupby("date").cumcount() < n_universe].copy()
    return p.sort_values(["date", "permno"]).reset_index(drop=True)


def industry_groups(u: pd.DataFrame, col: str = "ff12") -> pd.Series:
    """FF12 industry per row; `Unknown` is its own group; any group with fewer than 5 members at a date
    joins `Other`."""
    g = u[col].fillna("Unknown").astype(str)
    size = g.groupby(u["date"]).transform(lambda s: s.map(s.value_counts()))
    return g.where(size >= MIN_GROUP, "Other")


def neutralize(x: pd.Series, date: pd.Series, group: pd.Series, clip: float = CLIP) -> tuple[pd.Series, dict]:
    """z = (x - group mean) / sd over the date's universe of the demeaned values (ddof 1), then clipped to
    [-clip, clip]. Missing x stays missing. Returns z and counts (values, missing, clipped)."""
    keys = [date, group]
    d = x - x.groupby(keys).transform("mean")
    sd = d.groupby(date).transform(lambda s: s.std(ddof=1))
    z = d / sd
    clipped = z.abs().gt(clip)
    return z.clip(-clip, clip), {"values": int(x.notna().sum()), "missing": int(x.isna().sum()),
                                 "clipped": int(clipped.sum())}


def exposures(u: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add `group`, the raw oriented signals, their neutralized exposures and the diagnostic composite
    (the mean of the three neutralized exposures, defined only when all three exist).
    `u` needs date, permno, ff12, vol36, momentum, npy. Returns (frame, clip/missing counts by signal)."""
    out = u.copy()
    out["group"] = industry_groups(out)
    out["lowvol"] = -out["vol36"]
    rows = []
    for s in SIGNALS:
        out[f"{s}_z"], c = neutralize(out[s], out["date"], out["group"])
        rows.append({"signal": s, **c})
    out["composite_z"] = out[[f"{s}_z" for s in SIGNALS]].mean(axis=1, skipna=False)
    rows.append({"signal": "composite", "values": int(out["composite_z"].notna().sum()),
                 "missing": int(out["composite_z"].isna().sum()), "clipped": 0})
    return out, pd.DataFrame(rows)


def forward_returns(panel: pd.DataFrame, u: pd.DataFrame, horizons=range(1, 13)) -> pd.DataFrame:
    """Compounded `ret_hold` over t+1..t+h for each universe row (cohort fixed at t, delisted names kept).

    After a terminal (exit) month the position is cash and earns 0. A month after the end of the data, or a
    missing return before any exit, leaves the forward return missing. Also returns, per h, a flag for an
    exit inside the horizon. Index aligned with `u`."""
    permnos = np.sort(u["permno"].unique())
    dates = pd.DatetimeIndex(np.sort(panel["date"].unique()))
    sub = panel.loc[panel["permno"].isin(permnos), ["date", "permno", "ret_hold", "is_exit"]]
    R = sub.pivot(index="date", columns="permno", values="ret_hold").reindex(index=dates, columns=permnos)
    X = sub.pivot(index="date", columns="permno", values="is_exit").reindex(index=dates, columns=permnos)
    X = X.astype(float).fillna(0.0)
    after_exit = X.cumsum().shift(1).fillna(0.0).gt(0).to_numpy()
    r = np.array(R.to_numpy(float), copy=True)        # writable copy (pandas copy-on-write)
    r[after_exit] = 0.0                                   # cash after the exit month
    x = X.to_numpy() > 0
    ti = dates.get_indexer(u["date"])
    pj = np.searchsorted(permnos, u["permno"].to_numpy())
    out = pd.DataFrame(index=u.index)
    f = np.ones(len(u))
    ex = np.zeros(len(u), dtype=bool)
    for h in range(1, max(horizons) + 1):
        rows = ti + h
        ok = rows < len(dates)
        rr = np.full(len(u), np.nan)
        rr[ok] = r[rows[ok], pj[ok]]
        f = f * (1 + rr)
        ex = ex | np.where(ok, x[np.minimum(rows, len(dates) - 1), pj], False)
        if h in horizons:
            out[f"fwd_{h}"] = f - 1
            out[f"exit_within_{h}"] = ex
    return out


def industry_adjust(fwd: pd.Series, date: pd.Series, group: pd.Series) -> pd.Series:
    """Forward return minus the equal-weight forward return of the cohort's own group at that date."""
    return fwd - fwd.groupby([date, group]).transform("mean")


def spearman_by_date(df: pd.DataFrame, x: str, y: str, date: str = "date") -> pd.Series:
    """Spearman rank correlation of x and y at each date (average ranks for ties), on rows with both."""
    d = df[[date, x, y]].dropna()
    rx = d.groupby(date)[x].rank()
    ry = d.groupby(date)[y].rank()
    g = pd.DataFrame({"d": d[date], "a": rx, "b": ry, "ab": rx * ry, "aa": rx * rx, "bb": ry * ry}).groupby("d")
    s, n = g.sum(), g.size()
    cov = s["ab"] - s["a"] * s["b"] / n
    va, vb = s["aa"] - s["a"] ** 2 / n, s["bb"] - s["b"] ** 2 / n
    return (cov / np.sqrt(va * vb)).where(n >= 3).rename("ic")


def deciles(x: pd.Series, date: pd.Series, permno: pd.Series) -> pd.Series:
    """Equal-count deciles 1..10 of x within each date (ties by permno); missing x gets no decile."""
    d = pd.DataFrame({"x": x, "date": date, "permno": permno}).dropna(subset=["x"])
    d = d.sort_values(["date", "x", "permno"])
    n = d.groupby("date")["x"].transform("size")
    rank = d.groupby("date").cumcount()
    dec = (rank * 10 // n + 1).astype(int)
    return dec.reindex(x.index)


def nw_mean(series: pd.Series, lags: int) -> dict:
    """Mean of a time series with its Newey-West t-statistic (lags), and the literal mean/sd ratio."""
    from .stats import ols
    s = series.dropna()
    res = ols(s, pd.DataFrame(index=s.index), lags)
    sd = float(s.std(ddof=1))
    return {"mean": float(s.mean()), "sd": sd, "variance": sd ** 2, "mean_over_sd_literal": float(s.mean()) / sd,
            "t_nw": res["alpha_t_nw"], "nw_lags": lags, "months": len(s)}
