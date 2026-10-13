"""Confirmed paper targets (Tables 1, 2 and 4, 1929-2016) versus ours under the paper's own definitions, and the
Small control. Ported unchanged from the closed task 2026-10-11-paper-targets.
"""
import json

import numpy as np
import pandas as pd

from crsp_pipeline import config
from research import engine, report, stats
from research.studies._common import DATA

NAME = 'paper_targets'
DEPENDS = ('replication', 'attribution')
FILES = {
    'table1_vs_paper.csv': {'description': 'Table 1 against the paper under its definitions (Value excluded: no book equity)', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
    'table2_vs_paper.csv': {'description': 'Table 2 CMS rows of panels A and B against the paper (OLS and NW t); panels C and D excluded', 'window': '1929-01 .. 2016-12; panel B 1963-07 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
    'table4_vs_paper.csv': {'description': 'Table 4 against the paper on our compounded and arithmetic gross bases', 'window': '1929-01 .. 2016-12', 'returns': 'gross and net', 'role': 'primary'},
    'gaps.csv': {'description': 'Gaps above 1 pp (returns, alphas) or 5 pp (turnover), with explanations', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
    'small_monthly.csv': {'description': 'Small control (100 smallest universe members): monthly gross return, turnover, holdings', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
    'engine_unchanged.csv': {'description': 'Check: Conservative 1929-2016 re-run bit-identical to the replication series', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'check'},
}
START, END = pd.Timestamp("1929-01-31"), pd.Timestamp("2016-12-31")
EXCL_VALUE = "excluded: no book equity in the CRSP-only extract"
EXCL_CD = {"C": "excluded: q-factors not in our sources", "D": "excluded: AQR QMJ/BAB not in our sources"}

def run(ctx):
    out_dir = ctx.out("paper_targets")      # the body defines a local NAME table
    # --- Small (Table 1) and an engine check -----------------------------------------------------------------
    rep = pd.read_csv(ctx.result("replication", "returns_monthly.csv"), parse_dates=["date"], index_col="date", float_precision="round_trip")
    panel = pd.read_parquet(config.PANEL_FILE)
    panel = panel.loc[panel["date"].le(END)].reset_index(drop=True)
    bench = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"]).query("date <= @END")
    panel, bench = engine.validate_inputs(panel, bench)
    tg, counts = engine.formation_targets(engine.attach_signals(panel), ["Conservative", "Small"], start=START, last=END)
    cons = engine.backtest(panel, bench, tg["Conservative"], START, END, 0)["gross"]
    small = engine.backtest(panel, bench, tg["Small"], START, END, 0)
    same = bool(np.array_equal(cons.to_numpy(), rep["Conservative_gross"].to_numpy()) and cons.index.equals(rep.index))
    pd.DataFrame([{"check": "Conservative gross 1929-2016 re-run == replication series", "bit_identical": same,
                   "months": len(cons)}]).to_csv(out_dir / "engine_unchanged.csv", index=False)
    assert same
    small[["gross", "traded_notional", "holdings_n", "cash_weight"]].to_csv(out_dir / "small_monthly.csv")
    sc = counts.loc[counts["strategy"].eq("Small")]
    print(f"Small: {len(small)} months; selected {sc['selected_n'].min()}..{sc['selected_n'].max()}; "
          f"universe {sc['universe_n'].min()}..{sc['universe_n'].max()}; ties at cut {int(sc['score_ties_at_cut'].sum())}")

    # --- Table 1 ---------------------------------------------------------------------------------------------
    rf_annual = float(12 * rep["rf"].mean())
    cols = {"Formula": rep["Conservative_gross"], "Market": rep["Market"], "Small": small["gross"], "Value": None,
            "Momentum": rep["Standalone momentum_gross"], "Lowvol": rep["Standalone low-vol_gross"], "NPY": rep["Standalone NPY_gross"]}
    paper1 = {  # docs/DATA_CONVENTIONS.md -> "Paper tables", Table 1
        "Return (simple)": [0.155, 0.106, 0.158, 0.169, 0.182, 0.106, 0.156],
        "Return (compounded)": [0.151, 0.093, 0.120, 0.131, 0.159, 0.102, 0.145],
        "Difference (simple - comp.)": [0.004, 0.014, 0.038, 0.038, 0.023, 0.004, 0.011],
        "Volatility": [0.165, 0.187, 0.314, 0.317, 0.257, 0.133, 0.201],
        "De-risking factor": [1.00, 0.88, 0.52, 0.52, 0.64, 1.24, 0.82],
        "Sharpe (simple)": [0.94, 0.57, 0.50, 0.53, 0.71, 0.80, 0.78],
        "Return same risk": [0.155, 0.098, 0.099, 0.104, 0.129, 0.123, 0.134]}
    rows = []
    for j, (col, r) in enumerate(cols.items()):
        if r is not None:
            st = report.statistics(r.loc[START:END], rep["rf"])
            simple, comp, vol = st["arithmetic"], st["compounded"], st["volatility"]
            ours = {"Return (simple)": simple, "Return (compounded)": comp, "Difference (simple - comp.)": simple - comp,
                    "Volatility": vol, "De-risking factor": report.derisking_factor(vol),
                    "Sharpe (simple)": report.sharpe_simple(simple, vol),
                    "Return same risk": report.return_same_risk(simple, vol, rf_annual)}
        for row, pv in paper1.items():
            o = ours[row] if r is not None else np.nan
            rows.append({"row": row, "column": col, "paper": pv[j], "ours": o, "difference": o - pv[j],
                         "status": EXCL_VALUE if r is None else "compared",
                         "definition": {"Return (simple)": "12 x mean monthly return, gross",
                                        "Return (compounded)": "(prod(1 + r))^(12/T) - 1, gross",
                                        "Difference (simple - comp.)": "simple - compounded",
                                        "Volatility": "sqrt(12) x sd of monthly returns",
                                        "De-risking factor": "16.5% / volatility",
                                        "Sharpe (simple)": "simple return / volatility (no T-bill subtracted)",
                                        "Return same risk": f"rf + (simple - rf) x 16.5% / vol, rf = {rf_annual:.4%} "
                                                            "(12 x mean FF rf, 1929-2016)"}[row],
                         "months": 1056 if r is not None else np.nan})
    t1 = pd.DataFrame(rows)
    t1.to_csv(out_dir / "table1_vs_paper.csv", index=False)

    # --- Table 2 (CMS = R_cons - R_spec, gross, no rf subtracted) -------------------------------------------------
    fac = pd.read_csv(config.FACTORS_FILE, parse_dates=["date"], index_col="date")
    cms = (rep["Conservative_gross"] - rep["Speculative_gross"]).loc[START:END]
    B0 = pd.Timestamp("1963-07-31")
    FF5 = ["mktrf_ff5", "smb_ff5", "hml", "rmw", "cma"]
    specs = [  # (panel, model, sample start, our factors, paper alpha, paper t, paper loadings {name: (value, t)})
        ("A", "CAPM", START, ["mktrf"], 0.139, 7.07, {"Mkt": (-0.88, -29.45)}),
        ("A", "FF3", START, ["mktrf", "smb", "hml"], 0.165, 10.35, {"Mkt": (-0.65, None), "SMB": (-0.90, None), "HML": (-0.38, None)}),
        ("A", "Carhart", START, ["mktrf", "smb", "hml", "umd"], 0.088, 7.00,
         {"Mkt": (-0.50, None), "SMB": (-0.89, None), "HML": (-0.07, None), "MOM": (0.65, 27.03)}),
        ("B", "CAPM", B0, ["mktrf"], 0.140, 6.93, {"Mkt": (-0.74, None)}),
        ("B", "FF3", B0, ["mktrf", "smb", "hml"], 0.130, 7.29, {"Mkt": (-0.55, None), "SMB": (-0.60, None), "HML": (0.35, None)}),
        ("B", "FF5", B0, FF5, 0.088, 5.22,
         {"Mkt": (-0.44, None), "SMB": (-0.46, None), "HML": (0.03, None), "RMW": (0.59, None), "CMA": (0.75, None)}),
        ("B", "FF5 + MOM", B0, FF5 + ["umd"], 0.033, 2.95,
         {"Mkt": (-0.36, None), "SMB": (-0.51, None), "HML": (0.36, None), "RMW": (0.43, None), "CMA": (0.49, None), "MOM": (0.64, None)}),
    ]
    NAME = {"mktrf": "Mkt", "mktrf_ff5": "Mkt", "smb": "SMB", "smb_ff5": "SMB", "hml": "HML", "rmw": "RMW", "cma": "CMA", "umd": "MOM"}
    rows = []
    for panel_id, model, lo, fcols, pa, pt, pload in specs:
        y = cms.loc[lo:END]
        res = stats.ols(y, fac.loc[y.index, fcols], 12)
        base = {"panel": panel_id, "model": model, "sample": f"{y.index[0]:%Y-%m}..{y.index[-1]:%Y-%m}", "n": res["n"],
                "factors": "FF5 file's own Mkt and SMB" if "mktrf_ff5" in fcols else "FF3 file (Carhart MOM = umd)",
                "status": "compared"}
        rows.append({**base, "term": "alpha (annual)", "paper": pa, "paper_t": pt, "ours": res["alpha_annual"],
                     "ours_t_ols": res["alpha_t_ols"], "ours_t_nw": res["alpha_t_nw"], "difference": res["alpha_annual"] - pa})
        for k, f in enumerate(fcols):
            pv, ptt = pload[NAME[f]]
            rows.append({**base, "term": NAME[f], "paper": pv, "paper_t": ptt, "ours": float(res["betas"][k]),
                         "ours_t_ols": float(res["betas"][k] / res["se_ols"][k + 1]),
                         "ours_t_nw": float(res["betas"][k] / res["se_nw"][k + 1]), "difference": float(res["betas"][k]) - pv})
        rows.append({**base, "term": "adj. R2", "paper": np.nan, "paper_t": np.nan, "ours": res["adj_r2"],
                     "ours_t_ols": np.nan, "ours_t_nw": np.nan, "difference": np.nan})
    for panel_id, model, sample, pa, pt in [("C", "Hou-Xue-Zhang q", "1967..2016", 0.041, 2.39),
                                            ("D", "AQR (QMJ, BAB)", "1963..2016", 0.047, 3.21),
                                            ("D", "AQR + MOM", "1963..2016", 0.010, 0.97)]:
        rows.append({"panel": panel_id, "model": model, "sample": sample, "n": np.nan, "factors": "", "status": EXCL_CD[panel_id],
                     "term": "alpha (annual)", "paper": pa, "paper_t": pt, "ours": np.nan, "ours_t_ols": np.nan,
                     "ours_t_nw": np.nan, "difference": np.nan})
    t2 = pd.DataFrame(rows)
    t2.to_csv(out_dir / "table2_vs_paper.csv", index=False)
    # Consistency with the closed attribution task's gross CMS rows (panel A and FF5 + UMD).
    old = pd.read_csv(ctx.result("attribution", "table2.csv"), float_precision="round_trip")
    old = old.loc[old["returns"].eq("gross") & old["portfolio"].eq("CMS")].set_index("model")["alpha_annual"]
    for m_new, m_old in [("CAPM", "CAPM"), ("FF3", "FF3"), ("Carhart", "Carhart")]:
        v = t2.loc[t2["panel"].eq("A") & t2["model"].eq(m_new) & t2["term"].eq("alpha (annual)"), "ours"].iloc[0]
        assert np.isclose(v, old[m_old], rtol=0, atol=1e-12), (m_new, v, old[m_old])
    v = t2.loc[t2["model"].eq("FF5 + MOM") & t2["term"].eq("alpha (annual)"), "ours"].iloc[0]
    assert np.isclose(v, old["FF5+UMD"], rtol=0, atol=1e-12)

    # --- Table 4 ---------------------------------------------------------------------------------------------
    t4r = pd.read_csv(ctx.result("replication", "table4.csv"), float_precision="round_trip").set_index("series").loc["gross"]
    turn = float(t4r["one_way_turnover_per_quarter"])
    rows = []
    for basis, g in [("compounded", float(t4r["compounded"])), ("arithmetic", float(t4r["arithmetic"]))]:
        lo_c, hi_c = turn * 8 * 10e-4, turn * 8 * 30e-4
        ours = {"Gross return": g, "Quarterly turnover (single-counted)": turn, "Cost, low (10 bps)": lo_c,
                "Cost, high (30 bps)": hi_c, "Cost share of return (high)": hi_c / g, "Net return (high costs)": g - hi_c}
        paper4 = {"Gross return": 0.1524, "Quarterly turnover (single-counted)": 0.32, "Cost, low (10 bps)": 0.0026,
                  "Cost, high (30 bps)": 0.0077, "Cost share of return (high)": 0.050, "Net return (high costs)": 0.1447}
        for row, pv in paper4.items():
            rows.append({"row": row, "our_gross_basis": basis, "paper": pv, "ours": ours[row], "difference": ours[row] - pv,
                         "definition": {"Gross return": f"our {basis} gross return 1929-2016; the paper's 15.24% definition is unstated",
                                        "Quarterly turnover (single-counted)": "0.5 x sum |target - drifted| per quarterly rebalance, initial excluded",
                                        "Cost, low (10 bps)": "turnover x 8 x 10 bps (two sides x four quarters)",
                                        "Cost, high (30 bps)": "turnover x 8 x 30 bps",
                                        "Cost share of return (high)": "high cost / gross return",
                                        "Net return (high costs)": "gross - high cost"}[row]})
    t4 = pd.DataFrame(rows)
    t4.to_csv(out_dir / "table4_vs_paper.csv", index=False)

    # --- Gaps over the declared thresholds, each with an explanation ---------------------------------------------
    RET_ROWS = ["Return (simple)", "Return (compounded)", "Return same risk"]
    gaps = []
    for r in t1.loc[t1["status"].eq("compared") & t1["row"].isin(RET_ROWS)].itertuples():
        if abs(r.difference) > 0.01:
            gaps.append({"table": "1", "item": f"{r.column}: {r.row}", "paper": r.paper, "ours": r.ours, "difference": r.difference})
    for r in t2.loc[t2["status"].eq("compared") & t2["term"].eq("alpha (annual)")].itertuples():
        if abs(r.difference) > 0.01:
            gaps.append({"table": "2", "item": f"Panel {r.panel} {r.model}: CMS alpha", "paper": r.paper, "ours": r.ours, "difference": r.difference})
    for r in t4.itertuples():
        lim = 0.05 if r.row.startswith("Quarterly turnover") else 0.01
        if r.row in ("Gross return", "Net return (high costs)", "Quarterly turnover (single-counted)") and abs(r.difference) > lim:
            gaps.append({"table": "4", "item": f"{r.row} ({r.our_gross_basis} basis)", "paper": r.paper, "ours": r.ours, "difference": r.difference})
    gaps = pd.DataFrame(gaps).drop_duplicates(subset=["table", "item"])
    expl = json.loads((DATA / "paper_targets_explanations.json").read_text(encoding="utf-8"))
    gaps["explanation"] = gaps["item"].map(expl)
    gaps.to_csv(out_dir / "gaps.csv", index=False)
    print(gaps[["table", "item", "paper", "ours", "difference"]].to_string())
    missing = gaps.loc[gaps["explanation"].isna(), "item"].tolist()
    print("gaps without an explanation:", missing)
    assert not any("provisional" in str(v).lower() for f in ("table1_vs_paper.csv", "table2_vs_paper.csv", "table4_vs_paper.csv")
                   for v in pd.read_csv(out_dir / f).astype(str).to_numpy().ravel())
