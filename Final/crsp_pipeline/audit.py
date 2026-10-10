"""Coverage, exclusion, missingness, delisting, dividend and worked-example audits.

All tables are written to data/audit/ by `build.py`; each function returns a DataFrame so the
notebook can display the same results.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .signals import build_signals


def formation_dates(panel: pd.DataFrame, start: str = "1928-12-31") -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(sorted(panel["date"].unique()))
    return dates[(dates >= pd.Timestamp(start)) & dates.month.isin([3, 6, 9, 12])]


def universe_members(snap: pd.DataFrame, n: int | None = None) -> pd.DataFrame:
    """Paper ordering: history screen first, then the n largest by security market cap."""
    n = config.UNIVERSE_SIZE if n is None else n
    pool = snap.loc[snap["eligible"] & snap["hist36"]]
    return pool.sort_values(["mktcap", "permno"], ascending=[False, True]).head(n)


def formation_coverage(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for date, snap in panel.loc[panel["date"].isin(formation_dates(panel))].groupby("date"):
        elig = snap.loc[snap["eligible"]]
        uni = universe_members(snap)
        cap_first = elig.sort_values(["mktcap", "permno"], ascending=[False, True]).head(config.UNIVERSE_SIZE)
        rows.append({
            "date": date, "eligible_n": len(elig), "eligible_hist36_n": int(elig["hist36"].sum()),
            "universe_n": len(uni),
            "cap_first_top_without_hist36": int((~cap_first["hist36"]).sum()),
            "history_first_members_outside_cap_first": int((~uni["permno"].isin(cap_first["permno"])).sum()),
            "universe_cap_share_of_eligible": uni["mktcap"].sum() / elig["mktcap"].sum(),
            "universe_min_mktcap_musd": uni["mktcap"].min(),
            "universe_median_mktcap_musd": uni["mktcap"].median(),
            "universe_unknown_industry_n": int(uni["ff12"].eq("Unknown").sum()),
            "universe_industries_n": uni.loc[uni["ff12"].ne("Unknown"), "ff12"].nunique(),
        })
    return pd.DataFrame(rows)


def _decade(s: pd.Series) -> pd.Series:
    return (s.dt.year // 10 * 10).astype(str) + "s"


def exclusions_by_decade(panel: pd.DataFrame) -> pd.DataFrame:
    q = panel.loc[panel["date"].isin(formation_dates(panel, config.EXTRACT_START))]
    reason = q["exclusion"].replace("", "eligible")
    t = pd.crosstab(_decade(q["date"]), reason)
    t.index.name, t.columns.name = "decade", None
    return t


def missingness_by_decade(panel: pd.DataFrame) -> pd.DataFrame:
    e = panel.loc[panel["eligible"]]
    cols = {"ret_total": "ret_total", "ret_price": "ret_price", "div_cash_adj": "div_cash_adj",
            "shares_adj": "shares_adj"}
    out = e.groupby(_decade(e["date"])).agg(
        eligible_rows=("permno", "size"),
        **{f"missing_{k}": (v, lambda x: x.isna().mean()) for k, v in cols.items()},
        unknown_industry=("ff12", lambda x: x.eq("Unknown").mean()),
        hist36_share=("hist36", "mean"))
    out.index.name = "decade"
    return out


def delisting_summary(delist_log: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    d = delist_log.copy()
    d["category"] = (d["dlstcd"] // 100 * 100).astype(int).map(
        {200: "200 merger", 300: "300 exchange change", 400: "400 liquidation",
         500: "500 dropped (performance and other)", 600: "600 expired", 900: "900 foreign"}).fillna("other")
    # Was the security in the formation universe at the last quarter-end before delisting?
    members = []
    for date, snap in panel.loc[panel["date"].isin(formation_dates(panel))].groupby("date"):
        members.append(universe_members(snap)[["permno"]].assign(fdate=date))
    members = pd.concat(members, ignore_index=True)
    last_q = d["date"] - pd.offsets.QuarterEnd(1)
    key = pd.MultiIndex.from_arrays([d["permno"], last_q])
    d["in_universe_prior_quarter"] = key.isin(pd.MultiIndex.from_frame(members[["permno", "fdate"]]))
    out = (d.groupby(["category", "delist_source", "placement"])
             .agg(events=("permno", "size"), in_universe=("in_universe_prior_quarter", "sum"),
                  rows_after_dropped=("rows_dropped", "sum"), mean_dlret_used=("dlret_used", "mean"))
             .reset_index())
    return out


def dividend_reconciliation(panel: pd.DataFrame, dist: pd.DataFrame, rel_tol: float = 0.01) -> pd.DataFrame:
    """Compare implied dividends (ret - retx) with msedist cash distributions on ex-dates.

    `msedist` amounts are per share on the basis in force on the ex-date; dividing by that month's
    cfacpr converts them to the adjusted basis used by `div_cash_adj`. Two candidate cash
    definitions are reported so that the distribution-code convention is verified empirically.
    `agree_*` counts zero/zero rows as agreement; `*_given_distribution` columns condition on
    rows where either side reports a positive amount, which is the informative comparison.
    """
    x = dist.dropna(subset=["exdt", "distcd", "divamt"]).copy()
    x["date"] = pd.to_datetime(x["exdt"]) + pd.offsets.MonthEnd(0)
    code = x["distcd"].astype(int)
    first, payment = code // 1000, code // 100 % 10
    x["ordinary_cash"] = x["divamt"].where((first == 1) & (payment == 2), 0.0)
    x["ordinary_special_cash"] = x["divamt"].where(first.isin([1, 2]) & (payment == 2), 0.0)
    x["any_cash_amount"] = x["divamt"]
    per_month = x.groupby(["permno", "date"])[["ordinary_cash", "ordinary_special_cash", "any_cash_amount"]].sum()

    e = panel.loc[panel["eligible"] & panel["div_cash_adj"].notna(),
                  ["permno", "date", "div_cash_adj", "cfacpr"]].join(per_month, on=["permno", "date"])
    e[per_month.columns] = e[per_month.columns].fillna(0.0).div(e["cfacpr"], axis=0)
    rows = []
    for decade, grp in e.groupby(_decade(e["date"])):
        row = {"decade": decade, "rows": len(grp), "implied_positive": int(grp["div_cash_adj"].gt(0).sum())}
        for col in ["ordinary_cash", "ordinary_special_cash", "any_cash_amount"]:
            diff = (grp["div_cash_adj"] - grp[col]).abs()
            scale = grp[["div_cash_adj", col]].max(axis=1)
            agree = diff.le(rel_tol * scale) | diff.lt(1e-6)
            row[f"agree_{col}"] = agree.mean()
            active = grp["div_cash_adj"].gt(1e-6) | grp[col].gt(1e-6)
            row[f"n_with_distribution_{col}"] = int(active.sum())
            row[f"agree_{col}_given_distribution"] = agree[active].mean() if active.any() else np.nan
            row[f"implied_only_{col}"] = (grp["div_cash_adj"].gt(1e-6) & grp[col].le(1e-6)).mean()
            row[f"dist_only_{col}"] = (grp["div_cash_adj"].le(1e-6) & grp[col].gt(1e-6)).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def benchmark_check(bench: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    b = bench.merge(factors[["date", "mktrf"]], on="date")
    b["ff_market"] = b["mktrf"] + b["rf"]
    out = b.groupby(_decade(b["date"])).apply(lambda g: pd.Series({
        "months": len(g), "corr_crsp_vw_vs_ff_market": g["market_ret"].corr(g["ff_market"]),
        "mean_abs_diff": (g["market_ret"] - g["ff_market"]).abs().mean(),
        "ann_crsp_vw": (1 + g["market_ret"]).prod() ** (12 / len(g)) - 1,
        "ann_rf": (1 + g["rf"]).prod() ** (12 / len(g)) - 1}), include_groups=False)
    out.index.name = "decade"
    return out


WORKED_COLS = ["example", "date", "permno", "permco", "ticker", "comnam", "eligible", "exclusion",
               "prc", "shrout", "cfacpr", "cfacshr", "ret", "retx", "ret_total", "price_adj",
               "shares_adj", "div_cash_adj", "div_yield", "net_issuance", "npy", "mktcap",
               "dlstcd", "dlret", "delist_source", "is_exit"]


def worked_examples(panel: pd.DataFrame, delist_log: pd.DataFrame) -> pd.DataFrame:
    sig = build_signals(panel)
    p = panel.merge(sig[["date", "permno", "div_yield", "net_issuance", "npy"]], on=["date", "permno"], how="left")
    picks: list[tuple[str, list[int], str, str]] = []

    def by_ticker(label, ticker, at, lo, hi, whole_permco=False):
        hit = p.loc[p["ticker"].eq(ticker) & p["date"].eq(pd.Timestamp(at))]
        if hit.empty:
            return
        permnos = (p.loc[p["permco"].isin(hit["permco"]) & p["date"].eq(pd.Timestamp(at)), "permno"].tolist()
                   if whole_permco else hit["permno"].tolist())
        picks.append((label, permnos, lo, hi))

    by_ticker("dividend payer (IBM)", "IBM", "2012-12-31", "2011-10-31", "2012-12-31")
    by_ticker("4-for-1 split, August 2020 (AAPL)", "AAPL", "2020-08-31", "2020-05-31", "2020-12-31")
    by_ticker("non-payer with two share classes (Berkshire)", "BRK", "2015-12-31", "2015-07-31",
              "2015-12-31", whole_permco=True)

    def extreme(label, at, col, largest):
        snap = p.loc[p["date"].eq(pd.Timestamp(at)) & p["eligible"]].nlargest(500, "mktcap").dropna(subset=[col])
        if snap.empty:
            return
        row = snap.loc[snap[col].idxmax() if largest else snap[col].idxmin()]
        t = pd.Timestamp(at)
        picks.append((label, [int(row["permno"])], str((t - pd.offsets.MonthEnd(24)).date()), at))

    extreme("largest net issuer among top 500, 2009Q2", "2009-06-30", "net_issuance", True)
    extreme("largest net repurchaser among top 500, 2007Q4", "2007-12-31", "net_issuance", False)

    last_cap = p.loc[p["mktcap"].notna()].sort_values("date").groupby("permno")["mktcap"].last()
    for label, mask in [("largest performance delisting", delist_log["dlstcd"].isin(config.PERFORMANCE_DELIST_CODES)),
                        ("largest merger delisting", delist_log["dlstcd"].between(200, 299))]:
        ev = delist_log.loc[mask].assign(cap=lambda x: x["permno"].map(last_cap)).dropna(subset=["cap"])
        if not ev.empty:
            top = ev.loc[ev["cap"].idxmax()]
            picks.append((label, [int(top["permno"])], str((top["date"] - pd.offsets.MonthEnd(5)).date()),
                          str(top["date"].date())))

    frames = [p.loc[p["permno"].isin(permnos) & p["date"].between(pd.Timestamp(lo), pd.Timestamp(hi))]
               .assign(example=label) for label, permnos, lo, hi in picks]
    if not frames:
        return pd.DataFrame(columns=WORKED_COLS)
    return pd.concat(frames, ignore_index=True)[WORKED_COLS]
