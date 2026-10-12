"""Table 2 factor attribution 1929-01 .. 2016-12 (gross and net of 30 bps). Ported unchanged from the closed task
2026-10-10-factor-attribution. Uses the replication's portfolio series; no 2017+ month is used.
"""
import json

import pandas as pd

from crsp_pipeline import config
from research import stats
from research.studies._common import DATA

NAME = 'attribution'
DEPENDS = ('replication',)
FILES = {
    'table2.csv': {'description': 'Table 2: CAPM, FF3, Carhart and FF5+UMD regressions of Conservative, Speculative and CMS (NW 12); gross, net 30 (cost-inclusive CMS) and the labeled difference of net long-only returns', 'window': '1929-01 .. 2016-12 (FF5+UMD from 1963-07)', 'returns': 'gross and net', 'role': 'primary'},
    'reconciliation_table2.csv': {'description': 'Table 2A CMS alphas against the paper, with explanations', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'primary'},
}


def run(ctx):
    out_dir = ctx.out(NAME)
    END = pd.Timestamp(config.PAPER_END)

    ret = pd.read_csv(ctx.result("replication", "returns_monthly.csv"),
                      parse_dates=["date"], index_col="date")
    assert len(ret) == 1056 and ret.index.max() == END
    fac = pd.read_csv(config.FACTORS_FILE, parse_dates=["date"], index_col="date").loc[:END]
    rf = ret["rf"]
    assert rf.equals(fac["rf"].reindex(rf.index)), "rf in the return file and the factor file differ"

    NET_LONG_DIFF = "net 30 bps, difference of net long-only returns (not a cost-inclusive spread)"
    tables = []
    for kind, returns in [
            ("gross", {"Conservative": ret["Conservative_gross"], "Speculative": ret["Speculative_gross"]}),
            # Primary net rows (decisions.md 2026-10-11): CMS pays trading costs on both legs; no borrow or financing cost.
            ("net 30 bps", {"Conservative": ret["Conservative_net30"], "Speculative": ret["Speculative_net30"],
                            "CMS": stats.cms_net_both_legs(ret["Conservative_net30"], ret["Speculative_gross"],
                                                           ret["Speculative_net30"])}),
            (NET_LONG_DIFF, {"Conservative": ret["Conservative_net30"], "Speculative": ret["Speculative_net30"]})]:
        t = stats.attribute(returns, fac, rf, portfolios=("CMS",) if kind == NET_LONG_DIFF else ("Conservative", "Speculative", "CMS"),
                            label={"returns": kind})
        tables.append(t)
    table2 = pd.concat(tables, ignore_index=True)
    table2.to_csv(out_dir / "table2.csv", index=False)
    assert table2.loc[table2["model"].eq("FF5+UMD"), "n"].eq(642).all()
    assert table2.loc[table2["model"].ne("FF5+UMD"), "n"].eq(1056).all()

    exp = json.loads((DATA / "attribution_explanations.json").read_text(encoding="utf-8"))
    g = table2.loc[table2["returns"].eq("gross") & table2["portfolio"].eq("CMS")].set_index("model")
    recon = pd.DataFrame([
        {"target": "T2A CMS CAPM alpha", "definition": "Table 2A: annualized CAPM alpha of Conservative minus Speculative, gross, 1929-2016",
         "paper": 0.139, "ours": g.loc["CAPM", "alpha_annual"], "ours_t_nw": g.loc["CAPM", "alpha_t_nw"]},
        {"target": "T2A CMS four-factor alpha", "definition": "Table 2A: annualized Carhart (FF3 + UMD) alpha of CMS, gross, 1929-2016",
         "paper": 0.088, "ours": g.loc["Carhart", "alpha_annual"], "ours_t_nw": g.loc["Carhart", "alpha_t_nw"]},
    ])
    recon["difference"] = recon["ours"] - recon["paper"]
    recon["explanation"] = recon["target"].map(exp).fillna("")
    recon.to_csv(out_dir / "reconciliation_table2.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(table2[["returns", "portfolio", "model", "alpha_annual", "alpha_t_nw", "alpha_t_ols", "beta_mktrf", "adj_r2", "n"]]
          .round(4).to_string(index=False))
    print(recon[["target", "paper", "ours", "difference", "ours_t_nw"]].round(4).to_string(index=False))
