"""Vectorized formation signals on the normalized panel.

Definitions match notebook Section 4 at formation month t:
  vol36        = sqrt(12) * sd(ret_total[t-35..t])                    (sample sd)
  momentum     = prod(1 + ret_price[t-11..t-1]) - 1                     (skips month t)
  div_yield    = sum(div_cash_adj[t-11..t]) / price_adj[t]
  net_issuance = shares_adj[t] / mean(shares_adj[t-23..t]) - 1          (mean includes month t)
  npy          = div_yield - net_issuance
Every window must consist of calendar-consecutive months with no missing input; otherwise NaN.
"""
import numpy as np
import pandas as pd

from .normalize import consecutive


def _window_sum(x: pd.Series, g: pd.Series, k: int) -> pd.Series:
    cs = x.fillna(0).groupby(g).cumsum()
    return cs - cs.groupby(g).shift(k).fillna(0)


def build_signals(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.sort_values(["permno", "date"]).reset_index(drop=True)
    g = p["permno"]
    out = p[["date", "permno"]].copy()

    r = p["ret_total"]
    ok36 = consecutive(p, r.notna(), 36)
    out["vol36"] = (r.groupby(g).rolling(36, min_periods=36).std(ddof=1)
                     .reset_index(level=0, drop=True).sort_index().where(ok36) * np.sqrt(12))

    rp = p["ret_price"]
    wiped = rp.le(-1)
    logs = np.log1p(rp.where(~wiped))
    ok11 = consecutive(p, rp.notna(), 11)
    lsum = _window_sum(logs, g, 11).groupby(g).shift(1)
    nwiped = _window_sum(wiped.astype(float), g, 11).groupby(g).shift(1)
    prev_ok = ok11.groupby(g).shift(1, fill_value=False) & p["date"].sub(p.groupby("permno")["date"].shift(1)).dt.days.le(31)
    out["momentum"] = np.where(nwiped.gt(0), -1.0, np.expm1(lsum)).astype(float)
    out["momentum"] = out["momentum"].where(prev_ok.astype(bool))

    d = p["div_cash_adj"]
    ok12 = consecutive(p, d.notna(), 12)
    out["div_yield"] = (_window_sum(d, g, 12) / p["price_adj"]).where(ok12)

    s = p["shares_adj"]
    ok24 = consecutive(p, s.notna(), 24)
    out["net_issuance"] = (s / (_window_sum(s, g, 24) / 24) - 1).where(ok24)
    out["npy"] = out["div_yield"] - out["net_issuance"]
    return out
