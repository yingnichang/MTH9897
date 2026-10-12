"""Paper replication 1929-01 .. 2016-12: Tables 1 and 4, Figures 3 and 4, reconciliation, deviations, the pct10
sensitivity and DATA-011. Ported unchanged from the closed task 2026-10-10-paper-replication (rules fixed in its
comparison spec before any CRSP figure was read). The panel and benchmark are cut at 2016-12 on load.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from crsp_pipeline import config
from research import engine, report
from research.studies._common import DATA

NAME = 'replication'
DEPENDS = ()
FILES = {
    'returns_monthly.csv': {'description': 'Monthly gross returns of Conservative, Speculative and the standalone controls; Conservative and Speculative net of 10 and 30 bps; CRSP VW market; rf', 'window': '1929-01 .. 2016-12', 'returns': 'gross and net', 'role': 'primary'},
    'table1.csv': {'description': 'Table 1 statistics (compounded, arithmetic, volatility, Sharpe definitions, drawdown) by portfolio', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
    'decades.csv': {'description': 'Figure 4: compounded return by decade (partial decades labeled)', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
    'fig3.png': {'description': 'Figure 3: growth of $100 (Conservative, Speculative, CRSP VW)', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
    'fig4.png': {'description': 'Figure 4: returns by decade', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
    'table4.csv': {'description': 'Table 4: Conservative gross and net returns, one-way quarterly turnover, implied and engine cost drag', 'window': '1929-01 .. 2016-12', 'returns': 'gross and net', 'role': 'primary'},
    'reconciliation.csv': {'description': 'Paper targets (Tables 1 and 4) against ours, with explanations', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
    'deviations.csv': {'description': "Documented deviations from the paper's method, with direction or magnitude", 'window': '1929-01 .. 2016-12', 'returns': 'n/a', 'role': 'primary'},
    'formation_counts.csv': {'description': 'Per-formation universe, pool, missing-signal, selection and tie counts by strategy', 'window': 'formations 1928-12 .. 2016-09', 'returns': 'n/a', 'role': 'check'},
    'sensitivity_pct10.csv': {'description': 'DATA-001 sensitivity: Conservative with 10% of the universe instead of 100 names', 'window': '1929-01 .. 2016-12', 'returns': 'gross and net', 'role': 'exploratory'},
    'data011.csv': {'description': 'DATA-011: straddling missing-return gaps in Conservative holdings and the implied bias', 'window': '1929-01 .. 2016-12', 'returns': 'n/a', 'role': 'check'},
    'turnover_decomposition.csv': {'description': 'Turnover decomposition (names replaced, re-weighting, cash) by era (DATA-013)', 'window': '1929-01 .. 2016-12', 'returns': 'n/a', 'role': 'check'},
}
START, END = pd.Timestamp(config.FIRST_INVESTMENT), pd.Timestamp(config.PAPER_END)
PAPER = ["Conservative", "Speculative", "Standalone low-vol", "Standalone momentum", "Standalone NPY"]
LABELS = {"Standalone low-vol": "Low-vol", "Standalone momentum": "Momentum", "Standalone NPY": "NPY"}

def run(ctx):
    out_dir, log = ctx.out(NAME), ctx.log
    # --- Data -------------------------------------------------------------------------------------
    panel = pd.read_parquet(config.PANEL_FILE)
    panel = panel.loc[panel["date"].le(END)].reset_index(drop=True)
    bench = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"])
    bench = bench.loc[bench["date"].le(END)]
    panel, bench = engine.validate_inputs(panel, bench)
    sig = engine.attach_signals(panel)
    rf = bench["rf"]
    log(f"panel {len(panel):,} rows to {panel['date'].max().date()}")

    # --- Selection and backtests ------------------------------------------------------------------
    targets, counts = engine.formation_targets(sig, PAPER, start=START, last=END)
    targets_pct10, counts_pct10 = engine.formation_targets(sig, ["Conservative"], start=START, last=END, n_hold="pct10")
    counts.to_csv(out_dir / "formation_counts.csv", index=False, date_format="%Y-%m-%d")
    log(f"targets: {len(targets['Conservative'])} formations x {len(PAPER)} strategies")

    runs, trade_logs = {}, {}
    for name in PAPER:
        trade_logs[name] = []
        runs[(name, 0)] = engine.backtest(panel, bench, targets[name], START, END, 0, trade_log=trade_logs[name])
    for name in ["Conservative", "Speculative"]:
        for bps in (10, 30):
            runs[(name, bps)] = engine.backtest(panel, bench, targets[name], START, END, bps)
    runs[("Conservative pct10", 0)] = engine.backtest(panel, bench, targets_pct10["Conservative"], START, END, 0)
    runs[("Conservative pct10", 30)] = engine.backtest(panel, bench, targets_pct10["Conservative"], START, END, 30)
    assert all(len(r) == 1056 for r in runs.values()), {k: len(r) for k, r in runs.items()}
    for name in ["Conservative", "Speculative"]:       # gross does not depend on the cost level
        for bps in (10, 30):
            assert runs[(name, bps)]["gross"].equals(runs[(name, 0)]["gross"])
    log(f"backtests: {len(runs)} runs x 1,056 months")

    gross = {name: runs[(name, 0)]["gross"] for name in PAPER}
    market = bench["market_ret"].loc[START:END]
    monthly = pd.DataFrame({f"{n}_gross": gross[n] for n in PAPER})
    for name in ["Conservative", "Speculative"]:
        for bps in (10, 30):
            monthly[f"{name}_net{bps}"] = runs[(name, bps)]["net"]
    monthly["Market"] = market
    monthly["rf"] = rf.loc[START:END]
    monthly.index.name = "date"
    monthly.to_csv(out_dir / "returns_monthly.csv", date_format="%Y-%m-%d")
    assert len(monthly) == 1056 and not monthly.isna().any().any()

    # --- Table 1, decades, figures ------------------------------------------------------------------
    t1_series = {LABELS.get(n, n): gross[n] for n in PAPER} | {"Market (CRSP VW)": market}
    table1 = report.table(t1_series, rf)
    table1.index.name = "portfolio (gross)"
    table1.to_csv(out_dir / "table1.csv")

    decades = report.by_decade({"Conservative": gross["Conservative"], "Speculative": gross["Speculative"],
                                "Market (CRSP VW)": market})
    decades.to_csv(out_dir / "decades.csv")

    fig, ax = plt.subplots(figsize=(10, 5.5), layout="constrained")
    for name, s, color in [("Conservative", gross["Conservative"], "#176B87"),
                           ("Speculative", gross["Speculative"], "#C0504D"), ("Market (CRSP VW)", market, "#7F7F7F")]:
        w = pd.concat([pd.Series([100.0], index=[START - pd.offsets.MonthEnd(1)]), 100 * (1 + s).cumprod()])
        ax.plot(w.index, w, label=name, color=color, lw=1.6)
    ax.set_yscale("log")
    ax.set(ylabel="Value of $100 (log scale, gross)", title="Growth of $100, 1929–2016 (CRSP, gross of costs)")
    ax.legend()
    fig.savefig(out_dir / "fig3.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    cols = ["Conservative", "Speculative", "Market (CRSP VW)"]
    x = np.arange(len(decades))
    for i, (c, color) in enumerate(zip(cols, ["#176B87", "#C0504D", "#7F7F7F"])):
        ax.bar(x + (i - 1) * 0.27, 100 * decades[c], width=0.27, label=c, color=color)
    ax.set_xticks(x, decades.index, rotation=30, ha="right", fontsize=8)
    ax.axhline(0, color="black", lw=0.6)
    ax.set(ylabel="Compounded annual return (%)", title="Returns by decade (CRSP, gross); partial decades labeled")
    ax.legend()
    fig.savefig(out_dir / "fig4.png", dpi=150)
    plt.close(fig)

    # --- Table 4: turnover and cost reconciliation ------------------------------------------------
    rows = []
    for bps in (0, 10, 30):
        run = runs[("Conservative", bps)]
        series = run["gross"] if bps == 0 else run["net"]
        st = report.statistics(series, rf)
        rec = report.cost_reconciliation(runs[("Conservative", bps)], bps)
        rows.append({"series": "gross" if bps == 0 else f"net {bps} bps", "compounded": st["compounded"],
                     "arithmetic": st["arithmetic"], "volatility": st["volatility"],
                     "one_way_turnover_per_quarter": rec["one_way_per_quarter"],
                     "implied_annual_cost": rec["implied_annual_cost"],
                     "engine_arithmetic_drag": rec["engine_arithmetic_drag"],
                     "engine_compounded_drag": rec["engine_compounded_drag"],
                     "implied_minus_engine_arithmetic": rec["implied_annual_cost"] - rec["engine_arithmetic_drag"]})
    table4 = pd.DataFrame(rows).set_index("series")
    table4.to_csv(out_dir / "table4.csv")
    turn = report.quarterly_turnover(runs[("Conservative", 0)])
    log(f"Table 4: {turn['rebalances']} rebalances")

    # --- pct10 sensitivity ----------------------------------------------------------------------------
    cp = counts_pct10.set_index("formation")["selected_n"]
    sens = []
    for label, key in [("Conservative (100 names)", "Conservative"), ("Conservative (10% of universe)", "Conservative pct10")]:
        st = report.statistics(runs[(key, 0)]["gross"], rf)
        st30 = report.statistics(runs[(key, 30)]["net"], rf)
        sel = counts.loc[counts["strategy"].eq("Conservative")].set_index("formation")["selected_n"] if key == "Conservative" else cp
        sens.append({"portfolio": label, "compounded_gross": st["compounded"], "arithmetic_gross": st["arithmetic"],
                     "volatility": st["volatility"], "sharpe_paper": st["sharpe_paper"], "compounded_net30": st30["compounded"],
                     "one_way_turnover_per_quarter": report.quarterly_turnover(runs[(key, 0)])["one_way_per_quarter"],
                     "holdings_min": int(sel.min()), "holdings_max": int(sel.max()),
                     "holdings_1928_12": int(sel.loc[pd.Timestamp("1928-12-31")])})
    pd.DataFrame(sens).to_csv(out_dir / "sensitivity_pct10.csv", index=False)

    # --- DATA-011: straddling gaps in Conservative's actual holdings ------------------------------
    p = panel.sort_values(["permno", "date"]).reset_index(drop=True)
    pos = {k: i for i, k in enumerate(zip(p["permno"], p["date"]))}
    dist = pd.read_parquet(config.RAW / "msedist.parquet", columns=["permno", "distcd", "divamt", "exdt"])
    dist = dist.dropna(subset=["exdt", "distcd", "divamt"])
    code = dist["distcd"].astype(int)
    dist = dist.loc[(code // 1000).isin([1, 2]) & (code // 100 % 10).eq(2)].copy()     # ordinary + special cash
    dist["date"] = pd.to_datetime(dist["exdt"]) + pd.offsets.MonthEnd(0)
    dist = dist.groupby(["permno", "date"])["divamt"].sum()
    nan = p["ret_total"].isna().to_numpy()
    permno_arr = p["permno"].to_numpy()
    cases = []
    for tl in trade_logs["Conservative"][1:]:                 # rebalances after the initial purchase
        f = tl["formation"].iloc[0]
        for row in tl.loc[tl["pre_weight"].gt(0)].itertuples():
            i = pos.get((row.permno, f))
            if i is None or not nan[i]:
                continue                                     # not inside a missing-return run at the rebalance
            a = i
            while a - 1 >= 0 and permno_arr[a - 1] == row.permno and nan[a - 1]:
                a -= 1
            b = i
            while b + 1 < len(p) and permno_arr[b + 1] == row.permno and nan[b + 1]:
                b += 1
            before, resume = a - 1, b + 1
            has_before = before >= 0 and permno_arr[before] == row.permno
            has_resume = resume < len(p) and permno_arr[resume] == row.permno
            p0 = p.at[before, "price_adj"] if has_before else np.nan
            p1 = p.at[resume, "price_adj"] if has_resume else np.nan
            priced = bool(has_before and has_resume and p0 > 0 and p1 > 0)
            cash = 0.0
            if priced:
                for j in range(a, resume + 1):
                    d = p.at[j, "date"]
                    if (row.permno, d) in dist.index:
                        cf = p.at[j, "cfacpr"] if p.at[j, "cfacpr"] > 0 else p.at[before, "cfacpr"]
                        cash += dist.loc[(row.permno, d)] / cf
            cases.append({"formation": f, "pre_weight": row.pre_weight, "run_months": b - a + 1,
                          "months_after_rebalance": resume - i - 1, "priced": priced,
                          "price_move": p1 / p0 - 1 if priced else np.nan,
                          "lost_move": (p1 + cash) / p0 - 1 if priced else np.nan, "has_cash": cash > 0})
    cases = pd.DataFrame(cases)
    pr = cases.loc[cases["priced"]]
    years = 1056 / 12
    data011 = pd.DataFrame([{
        "straddling_positions": len(cases), "with_resumption_price": len(pr),
        "with_cash_distribution_in_gap": int(pr["has_cash"].sum()),
        "mean_lost_move": pr["lost_move"].mean(), "median_lost_move": pr["lost_move"].median(),
        "min_lost_move": pr["lost_move"].min(), "max_lost_move": pr["lost_move"].max(),
        "share_negative": pr["lost_move"].lt(0).mean(),
        "mean_pre_weight": pr["pre_weight"].mean(),
        "weighted_lost_move_sum": float((pr["pre_weight"] * pr["lost_move"]).sum()),
        "annual_bias_estimate": -float((pr["pre_weight"] * pr["lost_move"]).sum()) / years,
        "first_formation": cases["formation"].min().date() if len(cases) else None,
        "last_formation": cases["formation"].max().date() if len(cases) else None}])
    data011.to_csv(out_dir / "data011.csv", index=False)
    log(f"DATA-011: {len(cases)} straddling Conservative positions, {len(pr)} with a resumption price")

    # --- Reconciliation with the paper ----------------------------------------------------------------
    exp = json.loads((DATA / "replication_explanations.json").read_text(encoding="utf-8"))
    cons, mkt = table1.loc["Conservative"], table1.loc["Market (CRSP VW)"]
    targets_paper = [
        ("T1 Conservative return", "Table 1: compounded annual return, gross, 1929-2016", 0.151, cons["compounded"]),
        ("T1 Conservative volatility", "Table 1: annualized volatility of monthly returns", 0.165, cons["volatility"]),
        ("T1 Market return", "Table 1: compounded annual return of the US market (ours: CRSP VW incl. dividends)", 0.093, mkt["compounded"]),
        ("T1 Market volatility", "Table 1: annualized volatility of the market", 0.187, mkt["volatility"]),
        ("T4 Conservative gross return", "Table 4: annual gross return; the paper's definition is not stated (compounded shown; arithmetic in the explanation)", 0.1524, cons["compounded"]),
        ("T4 quarterly turnover", "Table 4: one-way, single-counted turnover per quarter, initial investment excluded", 0.32, turn["one_way_per_quarter"]),
    ]
    recon = pd.DataFrame([{"target": k, "definition": d, "paper": v, "ours": o, "difference": o - v,
                           "explanation": exp.get(k, "")} for k, d, v, o in targets_paper])
    recon.to_csv(out_dir / "reconciliation.csv", index=False)

    # --- Deviations table -----------------------------------------------------------------------------
    cc = counts.loc[counts["strategy"].eq("Conservative")]
    c_run = runs[("Conservative", 0)]
    d011 = data011.iloc[0]

    # Terminal events of names Conservative actually held (exit inside a holding quarter), by delisting source.
    exits = p.loc[p["is_exit"], ["permno", "date", "delist_source"]].set_index(["permno", "date"])["delist_source"]
    held_exit_sources = []
    for f, w in targets["Conservative"].items():
        for k in (1, 2, 3):
            keys = pd.MultiIndex.from_product([w.index, [f + pd.offsets.MonthEnd(k)]])
            held_exit_sources += exits.reindex(keys).dropna().tolist()
    held_exit_sources = pd.Series(held_exit_sources, dtype=object).value_counts().to_dict()

    # Turnover decomposition (diagnostic, single-counted): what the one-way turnover consists of.
    decomp = []
    for tl in trade_logs["Conservative"][1:]:
        f = tl["formation"].iloc[0]
        new, sold = tl["pre_weight"].eq(0) & tl["target_weight"].gt(0), tl["pre_weight"].gt(0) & tl["target_weight"].eq(0)
        kept = tl["pre_weight"].gt(0) & tl["target_weight"].gt(0)
        decomp.append({"formation": f, "one_way": 0.5 * tl["trade"].abs().sum(), "names_replaced": int(new.sum()),
                       "bought_new_names": tl.loc[new, "target_weight"].sum(), "sold_dropped_names": tl.loc[sold, "pre_weight"].sum(),
                       "reweight_kept_names": 0.5 * tl.loc[kept, "trade"].abs().sum(), "cash_reinvested": tl["pre_cash"].iloc[0]})
    decomp = pd.DataFrame(decomp)
    decomp["era"] = np.where(decomp["formation"] < pd.Timestamp("1964-06-30"), "1929-1964 (pool < 500)", "1964-2016 (pool 500)")
    turnover_decomp = decomp.groupby("era").agg(rebalances=("one_way", "size"), one_way=("one_way", "mean"),
                                                names_replaced=("names_replaced", "mean"), bought_new_names=("bought_new_names", "mean"),
                                                sold_dropped_names=("sold_dropped_names", "mean"),
                                                reweight_kept_names=("reweight_kept_names", "mean"), cash_reinvested=("cash_reinvested", "mean"))
    turnover_decomp.loc["all"] = [len(decomp), *decomp[turnover_decomp.columns[1:]].mean()]
    turnover_decomp.to_csv(out_dir / "turnover_decomposition.csv")
    deviations = pd.DataFrame([
        {"item": "Share-class selection", "ours": "largest common class of each PERMCO per month (shrcd 10/11)",
         "paper": "not specified", "direction_or_magnitude": "unknown sign; affects only multi-class companies"},
        {"item": "Size measure", "ours": "security market cap for the top-1,000 cut", "paper": "not specified (company cap likely)",
         "direction_or_magnitude": "unknown sign; changes membership at the margin of the top 1,000"},
        {"item": "Dividends", "ours": "implied from ret - retx (legacy retx includes non-ordinary distributions)",
         "paper": "cash dividends", "direction_or_magnitude": "NPY slightly higher where special distributions occur; agreement with msedist 98.6% in the universe"},
        {"item": "Missing-signal rule (NB-007)", "ours": "partition first; complete cases ranked",
         "paper": "not specified", "direction_or_magnitude": f"none: {int(cc['pool_missing_momentum_n'].sum() + cc['pool_missing_npy_n'].sum())} missing signals in the pool over 352 formations"},
        {"item": "Small early universe (DATA-001)", "ours": "all history-eligible names when < 1,000 (393 at 1928-12; 500-name pool from 1964-06)",
         "paper": "1,000 largest", "direction_or_magnitude": "100 of a 196-name pool in 1928 vs 100 of 500: less selective before 1964; see the pct10 sensitivity"},
        {"item": "Missing monthly returns (DATA-002/010)", "ours": "stale carry (0) or in-gap price ratio",
         "paper": "not specified", "direction_or_magnitude": f"{int(c_run['stale_held_n'].sum())} Conservative position-months; maximum weight {c_run['stale_weight'].max():.1%}"},
        {"item": "Straddling gaps (DATA-011)", "ours": "position traded at its last price at the rebalance",
         "paper": "n/a", "direction_or_magnitude": (f"{int(d011['with_resumption_price'])} of {int(d011['straddling_positions'])} straddling positions priced; "
                                                    f"mean lost move {d011['mean_lost_move']:+.1%}, median {d011['median_lost_move']:+.1%}; "
                                                    f"bias on the annual return about {d011['annual_bias_estimate']:+.3%} "
                                                    f"({'backtest optimistic' if d011['annual_bias_estimate'] > 0 else 'backtest pessimistic'})")},
        {"item": "Delisting imputation", "ours": "Shumway -30% / -55% for missing performance delisting returns",
         "paper": "not specified", "direction_or_magnitude": f"110 of 22,869 delistings imputed panel-wide; terminal events in Conservative holdings by source: {held_exit_sources}"},
        {"item": "Turnover measure", "ours": "0.5 x sum |target - drifted weight| per quarterly rebalance, incl. re-weighting kept names to equal weight",
         "paper": "32% per quarter, single-counted; computation not stated", "direction_or_magnitude": "see turnover_decomposition.csv: re-weighting of retained names is part of our figure"},
    ])
    deviations.to_csv(out_dir / "deviations.csv", index=False)
    log("done: " + ", ".join(sorted(f.name for f in out_dir.iterdir())))
