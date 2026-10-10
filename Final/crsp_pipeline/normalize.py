"""Turn raw legacy CRSP tables into the notebook's security-month panel and benchmark file.

Conventions (each is audited in `audit.py`):

* Dates are calendar month ends. CRSP stamps monthly rows with the last trading day.
* Names, share codes, exchanges and SIC codes are attached point in time from `msenames`
  (namedt <= date <= nameendt). No header (current) codes are used.
* Legacy `msf.ret` excludes delisting returns. The delisting return is compounded into the
  delisting month exactly once; if CRSP has no monthly row in that month, one is appended.
  Rows after a delisting month are dropped and counted.
* `price_adj = |prc| / cfacpr`, `shares_adj = shrout * cfacshr`, so splits change neither the
  adjusted price path nor the adjusted share count.
* Dividends are implied from CRSP returns: `div_cash_adj = (ret - retx) * price_adj[t-1]`.
  Equal `ret` and `retx` is a confirmed zero; a missing return or a calendar gap is unknown (NaN).
* `eligible` requires: a name record, share code 10/11, exchange code 1/2/3, positive price and
  shares, a nonterminal row, and being the largest common-stock class of its PERMCO that month.
* `hist36` marks 36 calendar-consecutive non-missing total returns ending this month, the
  paper's history requirement (paper p. 4) that must be applied before the capitalization cut.
* `ret_hold` is the holding return for the backtest (stale-price carry, DATA-002 and DATA-010). It
  equals `ret_total` where observed (`ret_hold_source = crsp`, every exit row included). A non-exit
  row with a missing return after the PERMNO's first row earns the price-only ratio to its last
  positive price when CRSP reports a positive price this month and the last one is at most
  `PRICE_RATIO_MAX_LOOKBACK_MONTHS` earlier (`price_ratio`; distributions in the gap are unknown);
  otherwise 0 (`stale_carry`: held at the last price). A first row without a return stays NaN
  (`no_prior_row`). `ret_total`, `hist36` and the signals keep the NaN, so a gap still breaks every window.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .industries import ff12

NAME_COLS = ["shrcd", "exchcd", "siccd", "ticker", "comnam", "shrcls"]


def month_end(s) -> pd.Series:
    return pd.to_datetime(s) + pd.offsets.MonthEnd(0)


def month_index(s: pd.Series) -> pd.Series:
    return s.dt.year * 12 + s.dt.month


def attach_names(msf: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    left = msf.assign(_d=pd.to_datetime(msf["date"])).sort_values("_d")
    right = names.assign(namedt=pd.to_datetime(names["namedt"]),
                         nameendt=pd.to_datetime(names["nameendt"])).sort_values("namedt")
    out = pd.merge_asof(left, right[["permno", "namedt", "nameendt", *NAME_COLS]],
                        left_on="_d", right_on="namedt", by="permno", direction="backward")
    stale = out["namedt"].isna() | (out["nameendt"].notna() & (out["_d"] > out["nameendt"]))
    out.loc[stale, NAME_COLS] = np.nan
    out["has_name"] = ~stale
    return out.drop(columns=["_d", "namedt", "nameendt"])


def apply_delistings(panel: pd.DataFrame, delist: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compound delisting returns into the delisting month; return (panel, per-event log)."""
    d = delist.dropna(subset=["dlstcd"]).copy()
    d = d.loc[d["dlstcd"].ne(config.DELIST_ACTIVE_CODE)]
    d["date"] = month_end(d["dlstdt"])
    d = d.sort_values(["permno", "date"]).drop_duplicates("permno", keep="last")

    last = panel.groupby("permno").agg(last_date=("date", "max"), last_exchcd=("exchcd", "last"))
    d = d.join(last, on="permno").dropna(subset=["last_date"])

    # Missing delisting returns: flagged imputation.
    perf = d["dlstcd"].isin(config.PERFORMANCE_DELIST_CODES)
    nasdaq = d["last_exchcd"].eq(3)
    d["delist_source"] = np.where(d["dlret"].notna(), "observed",
                                  np.where(perf, "imputed_shumway", "missing_set_zero"))
    impute = np.where(nasdaq, config.DELIST_IMPUTE_NASDAQ, config.DELIST_IMPUTE_NYSE_AMEX)
    d["dlret_used"] = d["dlret"].where(d["dlret"].notna(), np.where(perf, impute, 0.0))
    d["dlretx_used"] = d["dlretx"].where(d["dlretx"].notna(), d["dlret_used"])
    # Rows strictly after the delisting month contradict the event; drop and count them.
    after = panel.merge(d[["permno", "date"]].rename(columns={"date": "dl_date"}), on="permno", how="left")
    drop = after["dl_date"].notna() & after["date"].gt(after["dl_date"])
    d["rows_dropped"] = d["permno"].map(after.loc[drop].groupby("permno").size()).fillna(0).astype(int)
    panel = panel.loc[~drop.to_numpy()].copy()

    # Append a row when the delisting month has no monthly record.
    keys = pd.MultiIndex.from_frame(panel[["permno", "date"]])
    d["has_month_row"] = pd.MultiIndex.from_frame(d[["permno", "date"]]).isin(keys)
    d["placement"] = np.where(d["has_month_row"], "same_month", "appended_month")
    app = d.loc[~d["has_month_row"]]
    carry = panel.sort_values("date").groupby("permno").last()
    new = pd.DataFrame({"permno": app["permno"].to_numpy(), "date": app["date"].to_numpy()})
    for col in ["permco", "has_name", *NAME_COLS, "cfacpr", "cfacshr"]:
        new[col] = new["permno"].map(carry[col])
    new["appended_delist_row"] = True
    panel["appended_delist_row"] = False
    panel = pd.concat([panel, new], ignore_index=True)

    ev = d.set_index(["permno", "date"])[["dlstcd", "dlret", "dlret_used", "dlretx_used", "delist_source"]]
    panel = panel.join(ev, on=["permno", "date"])
    panel["is_exit"] = panel["dlstcd"].notna()
    ex = panel["is_exit"]
    base_ret, base_retx = panel["ret"], panel["retx"]
    panel["ret_total"] = base_ret
    panel["ret_price"] = base_retx
    panel.loc[ex, "ret_total"] = (1 + base_ret[ex].fillna(0)) * (1 + panel.loc[ex, "dlret_used"]) - 1
    panel.loc[ex, "ret_price"] = (1 + base_retx[ex].fillna(0)) * (1 + panel.loc[ex, "dlretx_used"]) - 1
    panel.loc[ex, "delist_ret_without_monthly"] = base_ret[ex].isna()
    return panel, d.reset_index(drop=True)


def consecutive(panel: pd.DataFrame, valid: pd.Series, k: int) -> pd.Series:
    """True where `valid` holds for k calendar-consecutive months ending at the row.

    Requires `panel` sorted by permno, date with unique rows.
    """
    m = month_index(panel["date"])
    g = panel["permno"]
    run = valid.astype(int).groupby(g).cumsum()
    lag_run = run.groupby(g).shift(k).fillna(0)
    lag_m = m.groupby(g).shift(k - 1)
    span_ok = (m - lag_m).eq(k - 1)
    return valid & span_ok & (run - lag_run).eq(k)


HOLD_SOURCES = ("crsp", "price_ratio", "stale_carry", "no_prior_row")


def add_holding_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """Add `ret_hold` and `ret_hold_source` without touching any existing column.

    Requires `panel` sorted by permno, date.
    """
    out = panel.copy()
    g = out["permno"]
    observed = out["ret_total"].notna()
    first = ~g.duplicated()
    missing = ~observed & ~out["is_exit"].fillna(False).astype(bool) & ~first

    # Last positive price strictly before this row, and how many calendar months back it is.
    priced = out["price_adj"].gt(0)
    m = month_index(out["date"])
    last_price = out["price_adj"].where(priced).groupby(g).ffill().groupby(g).shift(1)
    last_month = m.where(priced).groupby(g).ffill().groupby(g).shift(1)
    ratio = missing & priced & (m - last_month).le(config.PRICE_RATIO_MAX_LOOKBACK_MONTHS)
    stale = missing & ~ratio

    out["ret_hold"] = out["ret_total"].where(observed, np.nan)
    out.loc[ratio, "ret_hold"] = out.loc[ratio, "price_adj"] / last_price[ratio] - 1
    out.loc[stale, "ret_hold"] = 0.0
    out["ret_hold_source"] = np.select([observed, ratio, stale], list(HOLD_SOURCES[:3]), HOLD_SOURCES[3])
    return out


def build_panel(raw: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    msf = raw["msf"].copy()
    msf = attach_names(msf, raw["msenames"])
    msf["date"] = month_end(msf["date"])
    if msf.duplicated(["permno", "date"]).any():
        raise ValueError("Duplicate PERMNO-months after month-end conversion")

    panel, delist_log = apply_delistings(msf, raw["msedelist"])
    panel = panel.sort_values(["permno", "date"]).reset_index(drop=True)
    g = panel["permno"]

    panel["price_adj"] = panel["prc"].abs().where(panel["prc"].ne(0)) / panel["cfacpr"].where(panel["cfacpr"].gt(0))
    panel["shares_adj"] = panel["shrout"].where(panel["shrout"].gt(0)) * panel["cfacshr"].where(panel["cfacshr"].gt(0))
    panel["mktcap"] = panel["prc"].abs().where(panel["prc"].ne(0)) * panel["shrout"].where(panel["shrout"].gt(0)) / 1e3

    # Implied dividends on the adjusted-share basis; previous month must be the calendar prior month.
    prev_ok = (month_index(panel["date"]) - month_index(panel["date"]).groupby(g).shift(1)).eq(1)
    div_ret = panel["ret"] - panel["retx"]
    div_ret = div_ret.mask(div_ret.between(-config.DIV_NEGATIVE_TOL, 0, inclusive="left"), 0.0)
    panel["div_negative_unknown"] = div_ret.lt(-config.DIV_NEGATIVE_TOL)
    div_ret = div_ret.mask(panel["div_negative_unknown"])
    panel["div_cash_adj"] = (div_ret * panel["price_adj"].groupby(g).shift(1)).where(prev_ok)
    panel.loc[panel["appended_delist_row"], "div_cash_adj"] = np.nan

    # Point-in-time security screens and the reason a row is not eligible.
    common = panel["shrcd"].isin(config.COMMON_SHARE_CODES)
    listed = panel["exchcd"].isin(config.EXCHANGE_CODES)
    priced = panel["mktcap"].gt(0) & panel["price_adj"].gt(0) & panel["shares_adj"].gt(0)
    candidate = panel["has_name"] & common & listed & priced & ~panel["is_exit"]
    cap_candidates = panel["mktcap"].where(panel["has_name"] & common & priced)
    panel["mktcap_company"] = cap_candidates.groupby([panel["permco"], panel["date"]]).transform("sum")
    rank = (panel.assign(_c=panel["mktcap"].where(candidate))
                 .sort_values(["permco", "date", "_c", "permno"], ascending=[True, True, False, True]))
    primary_idx = rank.loc[rank["_c"].notna()].drop_duplicates(["permco", "date"]).index
    panel["primary_class"] = panel.index.isin(primary_idx)
    panel["eligible"] = candidate & panel["primary_class"]
    panel["exclusion"] = np.select(
        [~panel["has_name"], ~common, ~listed, panel["is_exit"], ~priced, ~panel["primary_class"]],
        ["no_name_record", "share_code", "exchange", "terminal_row", "missing_price_or_shares",
         "secondary_share_class"], "")

    panel["hist36"] = consecutive(panel, panel["ret_total"].notna(), config.HISTORY_MONTHS)
    panel["ff12"] = ff12(panel["siccd"])
    panel = add_holding_returns(panel)

    keep = ["date", "permno", "permco", "ticker", "comnam", "shrcd", "exchcd", "siccd", "ff12",
            "ret_total", "ret_price", "ret_hold", "ret_hold_source", "price_adj", "div_cash_adj", "shares_adj", "mktcap",
            "mktcap_company", "eligible", "is_exit", "hist36", "primary_class", "exclusion",
            "ret", "retx", "prc", "shrout", "cfacpr", "cfacshr", "vol",
            "dlstcd", "dlret", "delist_source", "appended_delist_row", "delist_ret_without_monthly",
            "div_negative_unknown"]
    out = panel[keep].copy()
    for col in ["eligible", "is_exit", "hist36", "primary_class", "appended_delist_row", "div_negative_unknown"]:
        out[col] = out[col].fillna(False).astype(bool)
    out["delist_ret_without_monthly"] = out["delist_ret_without_monthly"].astype("boolean")
    return out, delist_log


def build_benchmark(msi: pd.DataFrame, ff: pd.DataFrame, start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    m = msi.assign(date=month_end(msi["date"]))[["date", "vwretd"]].dropna()
    f = ff.rename(columns={"dateff": "date"}).assign(date=lambda x: month_end(x["date"]))
    f = f[["date", "mktrf", "smb", "hml", "umd", "rf"]].dropna(subset=["rf"])
    if f["rf"].abs().max() > 0.5 or f["mktrf"].abs().max() > 2:
        raise ValueError("Fama-French factors look like percentages; expected decimal monthly returns")
    bench = m.merge(f[["date", "rf"]], on="date", how="inner").rename(columns={"vwretd": "market_ret"})
    bench = bench.loc[bench["date"].between(pd.Timestamp(start), pd.Timestamp(end))]
    bench = bench.sort_values("date").reset_index(drop=True)
    expected = pd.date_range(start, end, freq="ME")
    if not expected.equals(pd.DatetimeIndex(bench["date"])):
        missing = expected.difference(pd.DatetimeIndex(bench["date"]))
        raise ValueError(f"Benchmark does not cover {start}..{end}; missing {len(missing)} months, "
                         f"first {list(missing[:3].date)}")
    return bench, f.sort_values("date").reset_index(drop=True)
