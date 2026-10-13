"""Headline numbers for the notebook prose and the slide deck, read only from `results/` through the loader.

Both deliverables quote numbers from `numbers()`, so their text cannot drift from the tracked results. Values are
raw floats (decimal returns, t-statistics, counts); `pct`, `pp`, `num` and `ci` format them. Statements about
intervals (`intervals_vs_zero`, `significance`) are derived from the stored bounds, never written by hand.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research import results

NET_LONG_DIFF = "CMS, difference of net long-only returns (not a cost-inclusive spread)"
PERIODS = ["1929–1962", "1963–1989", "1990–2016", "2017–2024", "1990–2024"]


def pct(x: float, d: int = 1) -> str:
    """0.1234 -> '12.3%' (a minus sign for negatives)."""
    return f"{100 * x:.{d}f}%".replace("-", "−")


def pp(x: float, d: int = 1) -> str:
    """Signed percentage-point difference: 0.012 -> '+1.2 pp'."""
    return f"{100 * x:+.{d}f} pp".replace("-", "−")


def num(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace("-", "−")


def ci(lo: float, hi: float, d: int = 1) -> str:
    """Interval of decimal returns in percent: '[−2.9%, 4.5%]'."""
    return f"[{pct(lo, d)}, {pct(hi, d)}]"


def ci_num(lo: float, hi: float, d: int = 2) -> str:
    """Interval of plain numbers (Sharpe ratios): '[0.33, 1.10]'."""
    return f"[{num(lo, d)}, {num(hi, d)}]"


WORDS = ["none", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]


def _word(n: int) -> str:
    return WORDS[n] if 0 <= n < len(WORDS) else f"{n:,}"


def excludes_zero(lo, hi) -> np.ndarray:
    """True where a confidence interval [lo, hi] lies entirely above or entirely below zero."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    return (lo > 0) | (hi < 0)


def zero_count(lo, hi) -> tuple[int, int]:
    """(number of intervals that exclude zero, number of intervals)."""
    m = excludes_zero(lo, hi)
    return int(m.sum()), int(m.size)


def intervals_vs_zero(lo, hi) -> str:
    """The inference a set of 95% intervals supports, counted from their bounds: e.g. 'three of the four 95% intervals
    exclude zero'."""
    k, n = zero_count(lo, hi)
    if n == 1:
        return "the 95% interval excludes zero" if k else "the 95% interval includes zero"
    if k == 0:
        return f"none of the {_word(n)} 95% intervals excludes zero"
    if k == n:
        return "both 95% intervals exclude zero" if n == 2 else f"all {_word(n)} 95% intervals exclude zero"
    return f"{_word(k)} of the {_word(n)} 95% intervals {'excludes' if k == 1 else 'exclude'} zero"


def significance(lo: float, hi: float) -> str:
    """'significantly positive', 'significantly negative' (5% level, from the 95% interval) or neither."""
    if lo > 0:
        return "significantly positive"
    if hi < 0:
        return "significantly negative"
    return "not significantly different from zero"


def one(df: pd.DataFrame, **cond) -> pd.Series:
    """The single row of `df` matching every column == value condition (raises otherwise)."""
    m = np.ones(len(df), bool)
    for k, v in cond.items():
        m &= df[k].to_numpy() == v
    rows = df.loc[m]
    if len(rows) != 1:
        raise KeyError(f"{len(rows)} rows match {cond}")
    return rows.iloc[0]


def numbers(root: Path = results.RESULTS) -> dict:
    """Every number quoted in the prose of the notebook and the deck."""
    L = lambda s, n, **k: results.load(s, n, root=root, **k)[0]
    N: dict = {}

    # Replication, 1929-2016 (gross).
    t1 = L("replication", "table1.csv").set_index("portfolio (gross)")
    for key, row in [("cons", "Conservative"), ("spec", "Speculative"), ("mkt", "Market (CRSP VW)")]:
        for col in ("compounded", "arithmetic", "volatility", "max_drawdown"):
            N[f"rep_{key}_{col}"] = float(t1.loc[row, col])
    tp = L("paper_targets", "table1_vs_paper.csv")
    for key, col in [("cons", "Formula"), ("mkt", "Market"), ("small", "Small")]:
        for row, tag in [("Return (compounded)", "compounded"), ("Return (simple)", "simple"), ("Volatility", "volatility")]:
            r = one(tp, row=row, column=col)
            N[f"paper_{key}_{tag}"], N[f"t1_{key}_{tag}"] = float(r.paper), float(r.ours)
    t4 = L("replication", "table4.csv").set_index("series")
    N["rep_turnover"] = float(t4.loc["gross", "one_way_turnover_per_quarter"])
    N["rep_cons_net30_compounded"] = float(t4.loc["net 30 bps", "compounded"])
    t4p = L("paper_targets", "table4_vs_paper.csv")
    N["paper_turnover"] = float(one(t4p, row="Quarterly turnover (single-counted)", our_gross_basis="compounded").paper)
    N["paper_t4_gross"] = float(one(t4p, row="Gross return", our_gross_basis="compounded").paper)
    dec = L("replication", "decades.csv")
    N["decades_n"] = len(dec)
    N["decades_cons_beats_mkt"] = int((dec["Conservative"] > dec["Market (CRSP VW)"]).sum())

    # Factor attribution (Table 2) and the paper's panels.
    t2 = L("attribution", "table2.csv")
    for p, tag in [("Conservative", "cons"), ("CMS", "cms")]:
        for m, mt in [("CAPM", "capm"), ("Carhart", "carhart"), ("FF5+UMD", "ff5umd")]:
            r = one(t2, returns="gross", portfolio=p, model=m)
            N[f"att_{tag}_{mt}_alpha"], N[f"att_{tag}_{mt}_t"] = float(r.alpha_annual), float(r.alpha_t_nw)
            N[f"att_{tag}_{mt}_n"] = int(r.n)
    r = one(t2, returns="net 30 bps", portfolio="CMS", model="Carhart")
    N["att_cms_carhart_net30_alpha"], N["att_cms_carhart_net30_t"] = float(r.alpha_annual), float(r.alpha_t_nw)
    tq = L("paper_targets", "table2_vs_paper.csv")
    for panel, model, tag in [("A", "CAPM", "a_capm"), ("A", "Carhart", "a_carhart"), ("B", "CAPM", "b_capm"),
                              ("B", "FF3", "b_ff3"), ("B", "FF5", "b_ff5"), ("B", "FF5 + MOM", "b_ff5mom")]:
        r = one(tq, panel=panel, model=model, term="alpha (annual)")
        N[f"t2_{tag}_paper"], N[f"t2_{tag}_ours"], N[f"t2_{tag}_n"] = float(r.paper), float(r.ours), int(r.n)

    # Critical tests (RS-006).
    sp = L("critical_tests", "subperiods.csv")
    for per in PERIODS:
        for kind in ("gross", "net10", "net30"):
            r = one(sp, period=per, portfolio="Conservative", returns=kind)
            k = f"{per}|{kind}"
            N[f"ct_excess|{k}"] = float(r.excess_vs_market)
            N[f"ct_excess_lo|{k}"], N[f"ct_excess_hi|{k}"] = float(r.excess_ci95_low), float(r.excess_ci95_high)
            N[f"ct_alpha|{k}"], N[f"ct_alpha_t|{k}"] = float(r.carhart_alpha), float(r.carhart_t_nw)
            N[f"ct_alpha_lo|{k}"], N[f"ct_alpha_hi|{k}"] = float(r.carhart_ci95_low), float(r.carhart_ci95_high)
            N[f"ct_ff5_alpha|{k}"] = float(r.ff5umd_alpha) if pd.notna(r.get("ff5umd_alpha")) else np.nan
            N[f"ct_ff5_t|{k}"] = float(r.ff5umd_t_nw) if pd.notna(r.get("ff5umd_t_nw")) else np.nan
            for c in ("lo", "hi"):
                v = r.get(f"ff5umd_ci95_{'low' if c == 'lo' else 'high'}")
                N[f"ct_ff5_alpha_{c}|{k}"] = float(v) if pd.notna(v) else np.nan
            for col, tag in [("compounded", "comp"), ("volatility", "vol"), ("sharpe_paper", "sharpe"),
                             ("sharpe_excess", "sharpe_x")]:
                N[f"ct_{tag}|{k}"] = float(r[col])
                N[f"ct_{tag}_lo|{k}"], N[f"ct_{tag}_hi|{k}"] = float(r[f"{col}_ci95_low"]), float(r[f"{col}_ci95_high"])
            N[f"ct_months|{per}"] = int(r.months)
        g = one(sp, period=per, portfolio="Conservative", returns="gross")
        m = one(sp, period=per, portfolio="Market (CRSP VW)", returns="gross")
        N[f"ct_cons_compounded|{per}"], N[f"ct_cons_vol|{per}"] = float(g.compounded), float(g.volatility)
        N[f"ct_mkt_compounded|{per}"], N[f"ct_mkt_vol|{per}"] = float(m.compounded), float(m.volatility)
        for col, tag in [("compounded", "comp"), ("volatility", "vol")]:
            N[f"ct_mkt_{tag}_lo|{per}"], N[f"ct_mkt_{tag}_hi|{per}"] = float(m[f"{col}_ci95_low"]), float(m[f"{col}_ci95_high"])
        c = one(sp, period=per, portfolio="CMS", returns="net30")
        N[f"ct_cms_net30_alpha|{per}"], N[f"ct_cms_net30_t|{per}"] = float(c.carhart_alpha), float(c.carhart_t_nw)
        N[f"ct_cms_net30_lo|{per}"], N[f"ct_cms_net30_hi|{per}"] = float(c.carhart_ci95_low), float(c.carhart_ci95_high)
        c = one(sp, period=per, portfolio="CMS", returns="gross")
        N[f"ct_cms_gross_alpha|{per}"], N[f"ct_cms_gross_t|{per}"] = float(c.carhart_alpha), float(c.carhart_t_nw)
    be = L("critical_tests", "breakeven.csv")
    for per in PERIODS:
        for meas, tag in [("net arithmetic excess over the market", "excess"), ("net Carhart alpha", "alpha")]:
            r = one(be, period=per, measure=meas)
            N[f"be_{tag}|{per}"] = float(r.breakeven_bps) if r.status == "found" else np.nan
            N[f"be_{tag}_status|{per}"] = str(r.status)
        N[f"be_turnover|{per}"] = float(r.one_way_turnover_per_quarter)
    freeze = L("critical_tests", "freeze_record.json")
    N["freeze_utc"] = freeze["data_loaded_utc"]

    # Diagnostics and factor-mimicking portfolios.
    ic = L("diagnostics", "ic.csv")
    r = one(ic, exposure="composite_z", h=1)
    N["ic_comp_h1"], N["ic_comp_h1_t"] = float(r["mean"]), float(r.t_nw)
    ds = L("diagnostics", "deciles_subperiods.csv")
    for per in PERIODS[:4]:
        r = one(ds, sample=per, exposure="composite_z", h=1, decile="D10-D1")
        N[f"dec_comp_spread|{per}"], N[f"dec_comp_t|{per}"] = float(r.mean_er), float(r.t_nw)
    pm = L("fmp", "paper_metrics.csv")
    for K in (1, 12):
        r = one(pm, K=K, weighting="equal", period="1929–2024")
        N[f"fmp_ir_K{K}"], N[f"fmp_turn_K{K}"] = float(r.ir), float(r.turnover_one_way_monthly)
    N["fmp_ir_2017_K1"] = float(one(pm, K=1, weighting="equal", period="2017–2024").ir)

    # Long/short, optimization, rank buffer.
    nx = L("longshort", "nxc.csv")
    r = one(nx, convention="monthly re-weighted (JT)", n=3, cost_bps=10, borrow="with")
    N["ls_er"], N["ls_ir"], N["ls_mdd"], N["ls_corr"] = float(r.er_over_rf_annual), float(r.ir), float(r.max_drawdown), float(r.corr_crsp_vw)
    N["ls_borrow"] = float(r.borrow_annual)
    rec = L("longshort", "ledger_reconciliation.csv")
    hold = rec.loc[rec["convention"].eq("buy-and-hold") & rec["borrow"] & rec["n"].isin([3, 6, 12])]
    N["ls_ruin_dates"] = sorted(set(hold["ruined_at"].dropna().astype(str)))
    capt = L("longshort", "capacity.csv")
    N["ls_capacity_2020s"] = float(one(capt, convention="monthly re-weighted (JT)", decade="2020s").capacity_aum_2024usd_p95_at_10pct)
    gs = L("optimization", "grid_subperiods.csv")
    spec = gs.loc[gs["cost_model"].eq("scaled") & gs["alpha"].eq("z") & gs["c0_bps"].eq(30)]
    best = spec.loc[spec["delta"].isin(["2%", "5%"]) & spec["tau"].isin(["20%", "40%"]) & spec["period"].eq("1990–2024")]
    N["opt_alpha_9024_min"], N["opt_alpha_9024_max"] = float(best.carhart_alpha_annual.min()), float(best.carhart_alpha_annual.max())
    a1724 = spec.loc[spec["period"].eq("2017–2024"), "carhart_alpha_annual"]
    N["opt_alpha_1724_min"], N["opt_alpha_1724_max"] = float(a1724.min()), float(a1724.max())
    # Interval inferences, counted from the stored bounds (nominal 95%, not adjusted for selection across the grid).
    for tag, rows in [("9024", best), ("1724", spec.loc[spec["period"].eq("2017–2024")])]:
        lo, hi = rows["carhart_alpha_ci95_low"], rows["carhart_alpha_ci95_high"]
        N[f"opt_ci_{tag}_excl"], N[f"opt_ci_{tag}_n"] = zero_count(lo, hi)
        N[f"opt_ci_{tag}_text"] = intervals_vs_zero(lo, hi)
    N["opt_runs_spec"] = int(len(spec.loc[spec["period"].eq("1990–2024")]) * 2)
    v = L("rank_buffer", "verdict.csv").iloc[0]
    N["buf_verdict"] = str(v.verdict)
    N["buf_turn_base"], N["buf_turn_buf"], N["buf_turn_red"] = float(v.turnover_baseline), float(v.turnover_buffer), float(v.turnover_reduction)
    N["buf_diff"], N["buf_lo"], N["buf_hi"] = float(v.net30_mean_diff_annual), float(v.net30_ci95_low), float(v.net30_ci95_high)
    pr = L("rank_buffer", "paired.csv")
    r = one(pr, returns="net30", period="1990–2024")
    N["buf_alpha"], N["buf_alpha_t"] = float(r.carhart_alpha_diff_annual), float(r.carhart_alpha_diff_t_nw)
    N["buf_gross_diff"] = float(one(pr, returns="gross", period="1990–2024").mean_diff_annual)
    return N
