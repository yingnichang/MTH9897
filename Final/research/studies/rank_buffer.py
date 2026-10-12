"""Phase 5 declared improvement: the rank buffer ("Conservative buffer", buffer = 150, the only value run).
Ported unchanged from the closed task 2026-10-11-rank-buffer. 2017-2024 data were already seen: not a holdout.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from crsp_pipeline import config
from research import engine, report, stats

NAME = 'rank_buffer'
DEPENDS = ('critical_tests', 'diagnostics')
FIXED_END = "2024-12-31"                       # sample fixed at 2024-12: run_all rejects another --end
FILES = {
    'paired.csv': {'description': 'Paired monthly difference, buffer (150) minus baseline: mean, NW SE and CI, Carhart alpha of the difference, by period (2017-2018 and 2019-2024 seen, not a holdout)', 'window': '1929-01 .. 2024-12; primary 1990-2024', 'returns': 'gross and net', 'role': 'primary'},
    'verdict.csv': {'description': 'Verdict against the declared trade-off (turnover down 25% and positive net-30 difference, 1990-2024)', 'window': '1990-01 .. 2024-12', 'returns': 'net', 'role': 'primary'},
    'turnover_concentration.csv': {'description': 'Turnover, holding period, FF12 concentration and names per industry, baseline and buffer, by period', 'window': '1929-01 .. 2024-12; primary 1990-2024', 'returns': 'n/a', 'role': 'primary'},
    'fig_paired_cum.png': {'description': 'Cumulative paired difference and turnover per rebalance', 'window': '1929-01 .. 2024-12; primary 1990-2024', 'returns': 'gross and net', 'role': 'primary'},
    'baseline_unchanged.csv': {'description': 'Check: baseline Conservative 1929-2024 bit-identical to the critical-tests series', 'window': '1929-01 .. 2024-12', 'returns': 'gross and net', 'role': 'check'},
}
START, END = pd.Timestamp("1929-01-31"), pd.Timestamp("2024-12-31")
BASE, BUF = "Conservative", "Conservative buffer"
PERIODS = {"1929–2024": ("1929-01-31", "2024-12-31"), **report.PERIODS,
           "2017–2018 (seen; not a holdout)": ("2017-01-31", "2018-12-31"),
           "2019–2024 (seen; not a holdout)": ("2019-01-31", "2024-12-31")}
PRIMARY = "1990–2024"
CARHART = ["mktrf", "smb", "hml", "umd"]

def run(ctx):
    out_dir, log = ctx.out(NAME), ctx.log
    assert pd.Timestamp(ctx.end) == pd.Timestamp("2024-12-31"), "this study's sample is fixed at 2024-12"
    assert engine.BUFFER_N == 150, "the declared buffer is 150; no other value is run"
    log(f"buffer_n = {engine.BUFFER_N} (declared; the only value run)")
    panel = pd.read_parquet(config.PANEL_FILE)
    bench = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"])
    panel, bench = engine.validate_inputs(panel.loc[panel["date"].le(END)].reset_index(drop=True), bench.loc[bench["date"].le(END)])
    sig = engine.attach_signals(panel)
    tg, counts = engine.formation_targets(sig, [BASE, BUF], start=START, last=END)
    runs = {s: engine.backtest(panel, bench, tg[s], START, END, 0) for s in (BASE, BUF)}
    fac = pd.read_csv(config.FACTORS_FILE, parse_dates=["date"], index_col="date")
    log("targets and backtests done")

    # --- The baseline is unchanged: bit-identical to the critical-tests series (1929-2024) -------------------------
    ref = pd.read_csv(ctx.result("critical_tests", "returns_monthly.csv"),
                      parse_dates=["date"], index_col="date", float_precision="round_trip")
    chk = []
    for lvl in ("gross", "net10", "net30"):
        mine = runs[BASE]["gross"] if lvl == "gross" else report.net_from_gross(runs[BASE], int(lvl[3:]))
        theirs = ref[f"Conservative | {lvl}"]
        chk.append({"series": f"Conservative {lvl} 1929-2024", "bit_identical":
                    bool(np.array_equal(mine.to_numpy(), theirs.to_numpy()) and mine.index.equals(theirs.index)), "months": len(mine)})
    pd.DataFrame(chk).to_csv(out_dir / "baseline_unchanged.csv", index=False)
    assert all(c["bit_identical"] for c in chk), chk
    log("baseline bit-identical to the critical-tests series")

    # --- Paired differences -----------------------------------------------------------------------------------
    series = {lvl: {s: (runs[s]["gross"] if lvl == "gross" else report.net_from_gross(runs[s], int(lvl[3:])))
                    for s in (BASE, BUF)} for lvl in ("gross", "net10", "net30")}
    rows = []
    for lvl, ss in series.items():
        d = (ss[BUF] - ss[BASE]).rename("diff")
        for pname, (lo, hi) in PERIODS.items():
            x = d.loc[lo:hi]
            assert len(x) == len(pd.date_range(lo, hi, freq="ME"))
            m = stats.ols(x, pd.DataFrame(index=x.index), 12)
            car = stats.ols(x, fac.loc[x.index, CARHART], 12)
            mkt = bench.loc[x.index, "market_ret"]
            rows.append({"returns": lvl, "period": pname, "months": len(x), "first": x.index[0].date(), "last": x.index[-1].date(),
                         "mean_diff_annual": m["alpha_annual"], "se_nw_annual": m["alpha_se_nw"], "t_nw": m["alpha_t_nw"],
                         "ci95_low": m["alpha_ci95_low"], "ci95_high": m["alpha_ci95_high"],
                         "ci_excludes_0": bool(m["alpha_ci95_low"] > 0 or m["alpha_ci95_high"] < 0),
                         "carhart_alpha_diff_annual": car["alpha_annual"], "carhart_alpha_diff_t_nw": car["alpha_t_nw"],
                         "carhart_alpha_diff_ci95_low": car["alpha_ci95_low"], "carhart_alpha_diff_ci95_high": car["alpha_ci95_high"],
                         "baseline_er_over_market_annual": float(12 * (ss[BASE].loc[x.index] - mkt).mean()),
                         "buffer_er_over_market_annual": float(12 * (ss[BUF].loc[x.index] - mkt).mean()),
                         "months_buffer_better": float((x > 0).mean())})
    paired = pd.DataFrame(rows)
    paired.to_csv(out_dir / "paired.csv", index=False)

    # --- Turnover, holding period and industry concentration ------------------------------------------------------
    e = pd.read_parquet(ctx.universe_cache(), columns=["date", "permno", "ff12"])
    ind = e.set_index(["date", "permno"])["ff12"]
    INDS = sorted(e["ff12"].unique())


    def spell_table(targets):
        forms = sorted(targets)
        pos = {f: i for i, f in enumerate(forms)}
        start, rows = {}, []
        for f in forms:
            names = set(targets[f].index)
            for p in [p for p in start if p not in names]:
                rows.append((start[p], pos[f] - pos[start[p]], False))
                del start[p]
            for p in names:
                start.setdefault(p, f)
        rows += [(s, len(forms) - pos[s], True) for s in start.values()]
        return pd.DataFrame(rows, columns=["start", "quarters", "censored"])


    tc = []
    for s in (BASE, BUF):
        run, targets = runs[s], tg[s]
        sp = spell_table(targets)
        sp["first_month"] = sp["start"] + pd.offsets.MonthEnd(1)
        conc = []
        for f, w in targets.items():
            g = ind.reindex(pd.MultiIndex.from_product([[f], w.index]))
            assert g.notna().all(), f"industry missing for holdings at {f.date()}"
            share = w.groupby(g.to_numpy()).sum()
            conc.append({"first_month": f + pd.offsets.MonthEnd(1), "hhi": float((share ** 2).sum()), "max_industry": float(share.max()),
                         **{f"names_{k}": int((g.to_numpy() == k).sum()) for k in INDS}})
        conc = pd.DataFrame(conc).set_index("first_month")
        for pname, (lo, hi) in PERIODS.items():
            r = run.loc[lo:hi]
            reb = report.rebalance_months(r.index)
            reb = reb[reb > START]
            c = conc.loc[lo:hi]
            spp = sp.loc[sp["first_month"].between(pd.Timestamp(lo), pd.Timestamp(hi))]
            k = counts.loc[counts["strategy"].eq(s) & (counts["formation"] + pd.offsets.MonthEnd(1)).between(pd.Timestamp(lo), pd.Timestamp(hi))]
            tc.append({"strategy": s, "period": pname, "rebalances": len(reb),
                       "turnover_one_way_per_quarter": float(0.5 * r.loc[reb, "traded_notional"].mean()),
                       "mean_holding_quarters": float(spp["quarters"].mean()), "spells": len(spp),
                       "censored_spells": int(spp["censored"].sum()),
                       "mean_kept_by_buffer": float(k["buffer_kept_n"].mean()) if "buffer_kept_n" in k and s == BUF else np.nan,
                       "hhi_ff12": float(c["hhi"].mean()), "effective_industries": float((1 / c["hhi"]).mean()),
                       "max_industry_weight": float(c["max_industry"].mean()),
                       **{col: float(c[col].mean()) for col in c.columns if col.startswith("names_")}})
    tcf = pd.DataFrame(tc)
    tcf.to_csv(out_dir / "turnover_concentration.csv", index=False)

    # --- Verdict against the declared trade-off (no new parameter) -------------------------------------------------
    t_b = tcf.set_index(["strategy", "period"]).loc[(BASE, PRIMARY), "turnover_one_way_per_quarter"]
    t_u = tcf.set_index(["strategy", "period"]).loc[(BUF, PRIMARY), "turnover_one_way_per_quarter"]
    p = paired.set_index(["returns", "period"]).loc[("net30", PRIMARY)]
    a = bool((t_b - t_u) / t_b >= 0.25)
    b = bool(p["mean_diff_annual"] > 0)
    verdict = ("succeeds" if a and b else "fails" if (not a) or (p["ci95_high"] < 0) else "inconclusive")
    pd.DataFrame([{"period": PRIMARY, "turnover_baseline": t_b, "turnover_buffer": t_u, "turnover_reduction": (t_b - t_u) / t_b,
                   "condition_a_turnover_down_25pct": a, "net30_mean_diff_annual": p["mean_diff_annual"],
                   "net30_ci95_low": p["ci95_low"], "net30_ci95_high": p["ci95_high"], "condition_b_positive": b,
                   "ci_excludes_0": p["ci_excludes_0"], "verdict": verdict}]).to_csv(out_dir / "verdict.csv", index=False)
    log(f"verdict: {verdict} (turnover {t_b:.3f} -> {t_u:.3f}; net30 diff {p['mean_diff_annual']:.4%})")

    # --- Figure ------------------------------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), layout="constrained")
    for lvl, col in [("gross", "#7F7F7F"), ("net30", "#176B87")]:
        d = series[lvl][BUF] - series[lvl][BASE]
        axes[0].plot(d.index, d.cumsum(), color=col, lw=1.1, label=f"{lvl}: cumulative sum of monthly differences")
    axes[0].axvspan(pd.Timestamp("1990-01-31"), END, color="#C0504D", alpha=0.08, label="1990–2024 (primary)")
    axes[0].axhline(0, color="black", lw=0.5)
    axes[0].set(title="Rank buffer (150) minus baseline, paired monthly differences", ylabel="Cumulative difference (sum)")
    axes[0].legend(fontsize=8)
    for s, col in [(BASE, "#7F7F7F"), (BUF, "#176B87")]:
        r = runs[s]
        reb = report.rebalance_months(r.index)
        reb = reb[reb > START]
        one = 0.5 * r.loc[reb, "traded_notional"]
        axes[1].plot(one.index, one.rolling(20).mean(), color=col, lw=1.1, label=f"{s} (5-year moving average)")
    axes[1].set(title="One-way turnover per quarterly rebalance", ylabel="Turnover")
    axes[1].legend(fontsize=8)
    fig.savefig(out_dir / "fig_paired_cum.png", dpi=150)
    log("done")
