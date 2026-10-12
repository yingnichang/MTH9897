"""RS-006 critical tests: fixed subperiods, costs and break-even, rolling 120-month excess return and alpha.
Ported unchanged from the closed task 2026-10-10-critical-tests (rules frozen before 2017+ data were loaded).
`run_meta.json` records this run; `freeze_record.json` is the original record of the first 2017+ load.
"""
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from crsp_pipeline import config
from research import engine, report, stats
from research.studies._common import DATA, FINAL

NAME = 'critical_tests'
DEPENDS = ('replication',)
FILES = {
    'returns_monthly.csv': {'description': 'Monthly Conservative, Speculative and CMS series (gross, net 10, net 30; cost-inclusive CMS and the labeled difference of net long-only returns), CRSP VW, rf', 'window': '1929-01 .. 2024-12', 'returns': 'gross and net', 'role': 'primary'},
    'subperiods.csv': {'description': 'RS-006 headline statistics by fixed period: returns, block-bootstrap CIs, excess over the market, Carhart and FF5+UMD alphas (NW 12)', 'window': '1929-01 .. 2024-12; RS-006 periods', 'returns': 'gross and net', 'role': 'primary'},
    'breakeven.csv': {'description': 'Break-even cost per dollar traded for the excess return and the Carhart alpha, by period', 'window': '1929-01 .. 2024-12; RS-006 periods', 'returns': 'net', 'role': 'primary'},
    'rolling.csv': {'description': 'Rolling 120-month excess return and Carhart alpha of Conservative', 'window': 'windows ending 1938-12 .. 2024-12', 'returns': 'gross and net', 'role': 'primary'},
    'fig_rolling.png': {'description': 'Rolling 120-month excess return and Carhart alpha', 'window': 'windows ending 1938-12 .. 2024-12', 'returns': 'gross and net', 'role': 'primary'},
    'run_meta.json': {'description': 'This run: data load time, end month, source hashes and the 1929-2016 identity check', 'window': 'run record', 'returns': 'n/a', 'role': 'check'},
    'freeze_record.json': {'description': 'Freeze record: the first load of 2017+ data (2026-10-11T00:50:37Z), copied unchanged from the original run', 'window': 'run record', 'returns': 'n/a', 'role': 'check'},
    'rerun_record_2026-10-11T145121.json': {'description': 'Record of the reporting rerun of 2026-10-11 (bootstrap CIs, cost-inclusive CMS), copied unchanged', 'window': 'run record', 'returns': 'n/a', 'role': 'check'},
}


def run(ctx):
    out_dir = ctx.out(NAME)
    START, END = pd.Timestamp(config.FIRST_INVESTMENT), pd.Timestamp(ctx.end)
    COSTS = (10, 30)
    SOURCES = sorted([*(FINAL / "research").glob("*.py"), *(FINAL / "crsp_pipeline").glob("*.py"), Path(__file__).resolve()])
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    meta = {"end": str(END.date()), "data_loaded_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "post_2016_data": bool(END > pd.Timestamp(config.PAPER_END)),
            "source_sha256": {str(p.relative_to(FINAL)).replace("\\", "/"): sha(p) for p in SOURCES},
            "manifest_sha256": sha(config.MANIFEST_FILE)}
    print(f"loading data to {END.date()} at {meta['data_loaded_utc']} (post-2016: {meta['post_2016_data']})", flush=True)

    # --- One engine run, 1929-01 .. END -------------------------------------------------------------
    panel = pd.read_parquet(config.PANEL_FILE)
    panel = panel.loc[panel["date"].le(END)].reset_index(drop=True)
    bench = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"])
    bench = bench.loc[bench["date"].le(END)]
    panel, bench = engine.validate_inputs(panel, bench)
    fac = pd.read_csv(config.FACTORS_FILE, parse_dates=["date"], index_col="date").loc[:END]
    sig = engine.attach_signals(panel)
    targets, _ = engine.formation_targets(sig, ["Conservative", "Speculative"], start=START, last=END)
    runs = {n: engine.backtest(panel, bench, targets[n], START, END, 0) for n in ["Conservative", "Speculative"]}
    months = len(pd.date_range(START, END, freq="ME"))
    assert all(len(r) == months for r in runs.values()), {n: len(r) for n, r in runs.items()}
    for n, run in runs.items():                    # the closed-form net series equals the engine's own net runs
        for bps in COSTS:
            eng = engine.backtest(panel, bench, targets[n], START, END, bps)["net"]
            assert np.allclose(report.net_from_gross(run, bps), eng, rtol=0, atol=1e-14), (n, bps)
    rf, mkt = bench["rf"].loc[START:END], bench["market_ret"].loc[START:END]
    assert rf.equals(fac["rf"].reindex(rf.index))

    series = {}
    for n, run in runs.items():
        series[(n, "gross")] = run["gross"]
        for bps in COSTS:
            series[(n, f"net{bps}")] = report.net_from_gross(run, bps)
    # CMS (decisions.md 2026-10-11): gross = Cons - Spec; net = cost-inclusive spread, both legs pay their trading
    # costs (no borrow or financing cost). The difference of net long-only returns is kept, labeled as not a spread.
    NET_LONG_DIFF = "CMS, difference of net long-only returns (not a cost-inclusive spread)"
    series[("CMS", "gross")] = series[("Conservative", "gross")] - series[("Speculative", "gross")]
    for bps in COSTS:
        k = f"net{bps}"
        series[("CMS", k)] = stats.cms_net_both_legs(series[("Conservative", k)], series[("Speculative", "gross")],
                                                     series[("Speculative", k)])
        series[(NET_LONG_DIFF, k)] = series[("Conservative", k)] - series[("Speculative", k)]
    series[("Market (CRSP VW)", "gross")] = mkt
    pd.DataFrame({f"{n} | {k}": v for (n, k), v in series.items()}).assign(rf=rf).rename_axis("date").to_csv(
        out_dir / "returns_monthly.csv", date_format="%Y-%m-%d")      # exact float repr; read with float_precision="round_trip"

    # Extending the sample must not change any earlier month: compare with the replication task's series.
    rep = pd.read_csv(ctx.result("replication", "returns_monthly.csv"),
                      parse_dates=["date"], index_col="date", float_precision="round_trip")   # exact float64 values
    cut = pd.Timestamp(config.PAPER_END)
    identical = {}
    for col, key in [("Conservative_gross", ("Conservative", "gross")), ("Speculative_gross", ("Speculative", "gross")),
                     ("Conservative_net10", ("Conservative", "net10")), ("Conservative_net30", ("Conservative", "net30")),
                     ("Speculative_net10", ("Speculative", "net10")), ("Speculative_net30", ("Speculative", "net30")),
                     ("Market", ("Market (CRSP VW)", "gross")), ("rf", None)]:
        ours = (rf if key is None else series[key]).loc[:cut]
        identical[col] = bool(np.array_equal(ours.to_numpy(), rep[col].loc[:cut].to_numpy())
                              and ours.index.equals(rep.index[rep.index <= cut]))
    assert all(identical.values()), identical
    meta["slice_1929_2016_identical_to_replication"] = identical
    meta["months"] = months
    print(f"engine run: {months} months; 1929-2016 slice identical to the replication series: {all(identical.values())}", flush=True)

    # --- Subperiod table ------------------------------------------------------------------------------
    periods = [p for p, (lo, hi) in report.PERIODS.items() if pd.Timestamp(hi) <= END]
    zero = pd.Series(0.0, index=rf.index)
    rows = []
    for period in periods:
        for (name, kind), s in series.items():
            r = report.period_slice(s, period)
            is_cms = name.startswith("CMS")
            st = report.statistics(r, zero if is_cms else rf)        # CMS is a zero-investment return: no rf
            row = {"period": period, "portfolio": name, "returns": kind, **st}
            boot = report.bootstrap_statistics(r, zero if is_cms else rf, block=12, reps=5000, seed=9897)
            row.update(boot)
            row["max_drawdown_interval"] = "none (path statistic)"
            if is_cms:
                row["sharpe_excess"] = np.nan                         # identical to sharpe_paper without rf
                for k in ["sharpe_excess_se", "sharpe_excess_ci95_low", "sharpe_excess_ci95_high"]:
                    row[k] = np.nan
            if not is_cms and not name.startswith("Market"):
                ex = stats.ols(r - report.period_slice(mkt, period), pd.DataFrame(index=r.index), 12)
                row.update({"excess_vs_market": ex["alpha_annual"], "excess_se_nw": ex["alpha_se_nw"],
                            "excess_t_nw": ex["alpha_t_nw"], "excess_ci95_low": ex["alpha_ci95_low"],
                            "excess_ci95_high": ex["alpha_ci95_high"]})
            y = r if is_cms else r - report.period_slice(rf, period)
            for model, tag in [("Carhart", "carhart"), ("FF5+UMD", "ff5umd")]:
                f = fac.reindex(y.index)[stats.MODELS[model]].dropna()
                if len(f) < 24:
                    continue                                          # FF5 + UMD: no coverage before 1963-07
                res = stats.ols(y.loc[f.index], f, 12)
                row.update({f"{tag}_alpha": res["alpha_annual"], f"{tag}_se_nw": res["alpha_se_nw"],
                            f"{tag}_t_nw": res["alpha_t_nw"], f"{tag}_t_ols": res["alpha_t_ols"],
                            f"{tag}_ci95_low": res["alpha_ci95_low"], f"{tag}_ci95_high": res["alpha_ci95_high"],
                            f"{tag}_n": res["n"]})
            rows.append(row)
    sub = pd.DataFrame(rows)
    sub.to_csv(out_dir / "subperiods.csv", index=False)

    # --- Break-even cost, Conservative ---------------------------------------------------------------
    cons = runs["Conservative"]
    be_rows = []
    for period in periods:
        run_p = report.period_slice(cons, period)
        m_p, rf_p = report.period_slice(mkt, period), report.period_slice(rf, period)
        f_c = fac.reindex(run_p.index)[stats.MODELS["Carhart"]]
        excess = lambda c: 12 * float((report.net_from_gross(run_p, c) - m_p).mean())
        alpha = lambda c: stats.ols(report.net_from_gross(run_p, c) - rf_p, f_c, 12)["alpha_annual"]
        rebal = report.rebalance_months(run_p.index)
        rebal = rebal[rebal != START]                 # the initial purchase in 1929-01 is not turnover
        turnover = 0.5 * float(run_p.loc[rebal, "traded_notional"].mean())
        for measure, fn in [("net arithmetic excess over the market", excess), ("net Carhart alpha", alpha)]:
            be = report.breakeven(fn)
            be_rows.append({"period": period, "measure": measure, "status": be["status"], "breakeven_bps": be["bps"],
                            "gross_value": be["value_at_zero_cost"], "value_at_10bps": fn(10), "value_at_30bps": fn(30),
                            "one_way_turnover_per_quarter": turnover})
    pd.DataFrame(be_rows).to_csv(out_dir / "breakeven.csv", index=False)

    # --- Rolling 120-month excess return and Carhart alpha (Conservative) ------------------------------
    roll = []
    ends = cons.index[119:]
    for kind in ["gross", "net30"]:
        s = series[("Conservative", kind)]
        for e in ends:
            w = s.loc[:e].iloc[-120:]
            f = fac.reindex(w.index)[stats.MODELS["Carhart"]]
            res = stats.ols(w - rf.reindex(w.index), f, 12)
            roll.append({"window_end": e, "returns": kind, "excess_vs_market": 12 * float((w - mkt.reindex(w.index)).mean()),
                         "carhart_alpha": res["alpha_annual"], "carhart_t_nw": res["alpha_t_nw"]})
    roll = pd.DataFrame(roll)
    roll.to_csv(out_dir / "rolling.csv", index=False, date_format="%Y-%m-%d")

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, layout="constrained")
    for kind, ls in [("gross", "-"), ("net30", "--")]:
        r = roll.loc[roll["returns"].eq(kind)]
        axes[0].plot(r["window_end"], 100 * r["excess_vs_market"], ls, color="#176B87", lw=1.3, label=f"Conservative, {kind}")
        axes[1].plot(r["window_end"], 100 * r["carhart_alpha"], ls, color="#176B87", lw=1.3, label=f"Conservative, {kind}")
    for ax, lab in zip(axes, ["Excess return over CRSP VW (%/yr)", "Carhart alpha (%/yr)"]):
        ax.axhline(0, color="black", lw=0.6)
        for b in ["1963-01-31", "1990-01-31", "2017-01-31"]:
            ax.axvline(pd.Timestamp(b), color="#999999", lw=0.8, ls=":")
        ax.set_ylabel(lab)
        ax.legend(fontsize=8, loc="upper left")
    axes[0].set_title(f"Rolling 120-month windows ending {ends[0].date()} to {ends[-1].date()} (CRSP); "
                      "dotted lines: 1963, 1990, 2017 period boundaries", fontsize=10)
    fig.savefig(out_dir / "fig_rolling.png", dpi=150)
    plt.close(fig)

    meta["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    meta_path = out_dir / "run_meta.json"
    if meta_path.exists() and meta["post_2016_data"]:        # keep the original freeze record; reruns log separately
        meta_path = out_dir / f"run_meta_rerun_{meta['data_loaded_utc'][:19].replace(':', '')}.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"done: periods {periods}; outputs in {out_dir}", flush=True)

    # The original freeze record (first load of 2017+ data) and the later rerun record are kept unchanged.
    shutil.copyfile(DATA / "critical_tests_freeze_record.json", out_dir / "freeze_record.json")
    shutil.copyfile(DATA / "critical_tests_rerun_record_2026-10-11T145121.json", out_dir / "rerun_record_2026-10-11T145121.json")
