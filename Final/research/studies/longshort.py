"""Decile long/short on the diagnostic composite with overlapping cohorts (Trading 1A-C, 4-6), CRSP 1929-2024.
Ported unchanged from the closed task 2026-10-11-long-short-construction. Monthly re-weighted cohorts are primary,
a convention chosen after the buy-and-hold ruin was observed (decisions.md); buy-and-hold is the pre-specified
convention and its ruin stays reported. Trade ledgers go to output/ledger_n*_<mode>.parquet (git-ignored).
"""
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from crsp_pipeline import config
from research import diagnostics as dg, engine, longshort as ls, stats
from research.studies._common import FINAL

NAME = 'longshort'
DEPENDS = ('replication', 'diagnostics')
FIXED_END = "2024-12-31"                       # sample fixed at 2024-12: run_all rejects another --end
FILES = {
    'nxc.csv': {'description': 'Joint n x cost table (n = 1, 3, 6, 12; 0-30 bps; with and without borrow) for both cohort conventions: monthly re-weighted primary (chosen after the buy-and-hold ruin was observed), buy-and-hold pre-specified (ruined)', 'window': '1929-01 .. 2024-12', 'returns': 'gross and net', 'role': 'primary'},
    'subperiods_n3_c10.csv': {'description': 'n = 3, 10 bps, by RS-006 period (fresh capital per period), both conventions', 'window': 'RS-006 periods', 'returns': 'net', 'role': 'primary'},
    'industry_attribution.csv': {'description': 'Industry attribution (bonus): regression on 12 EW industry excess returns, residual alpha (NW 12)', 'window': '1929-01 .. 2024-12', 'returns': 'gross and net', 'role': 'exploratory'},
    'capacity.csv': {'description': 'Capacity: participation in monthly dollar volume by decade, positions aggregated by security and side (2024 dollars; no impact model)', 'window': '1929-01 .. 2024-12', 'returns': 'n/a', 'role': 'primary'},
    'ledger_reconciliation.csv': {'description': 'Check: trade ledger reconciles to turnover and P&L for every run (ledgers in output/)', 'window': '1929-01 .. 2024-12', 'returns': 'n/a', 'role': 'check'},
    'engine_unchanged.csv': {'description': 'Check: paper engine Conservative 1929-2016 bit-identical to the replication series', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'check'},
    'fig_longshort.png': {'description': 'Long/short wealth (monthly re-weighted, 10 bps, borrow) and IR by n and cost', 'window': '1929-01 .. 2024-12', 'returns': 'net', 'role': 'primary'},
}
NS, COSTS = [1, 3, 6, 12], [0, 5, 10, 20, 30]
CONVS = {"buy-and-hold": "hold", "monthly re-weighted (JT)": "monthly"}
ROLE = {"monthly re-weighted (JT)": "primary (chosen after the buy-and-hold ruin was observed)",
        "buy-and-hold": "pre-specified (ruined for n >= 3)"}
TRADES = ["open", "close", "rebalance"]
PERIODS = {"1929–1962": ("1929-01-31", "1962-12-31"), "1963–1989": ("1963-01-31", "1989-12-31"),
           "1990–2016": ("1990-01-31", "2016-12-31"), "2017–2024": ("2017-01-31", "2024-12-31")}
AUMS = {"$10M": 1e7, "$100M": 1e8, "$1B": 1e9, "$10B": 1e10}

def run(ctx):
    out_dir, log = ctx.out(NAME), ctx.log
    LEDGERS = Path(ctx.output)
    LEDGERS.mkdir(parents=True, exist_ok=True)
    assert pd.Timestamp(ctx.end) == pd.Timestamp("2024-12-31"), "this study's sample is fixed at 2024-12"
    e = pd.read_parquet(ctx.universe_cache())
    panel = pd.read_parquet(config.PANEL_FILE, columns=["date", "permno", "ret_hold", "is_exit", "vol", "prc"])
    bench = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"], index_col="date")
    months = pd.date_range("1929-01-31", "2024-12-31", freq="ME")
    rf, mkt = bench["rf"].reindex(months), bench["market_ret"].reindex(months)
    assert rf.notna().all() and mkt.notna().all()

    # --- Cohorts: top and bottom composite deciles; borrow rate from the universe cap decile at formation ----
    e["dec"] = dg.deciles(e["composite_z"], e["date"], e["permno"])
    e["cap_dec"] = dg.deciles(e["mktcap"], e["date"], e["permno"])
    cohorts = {}
    for f, g in e.groupby("date"):
        lo, hi = g.loc[g["dec"].eq(1)], g.loc[g["dec"].eq(10)]
        cohorts[f] = ls.Cohort(f, hi["permno"].to_numpy(), lo["permno"].to_numpy(),
                               np.array([ls.borrow_rate(int(d)) for d in lo["cap_dec"]]))
    names = np.unique(np.concatenate([np.r_[c.long, c.short] for c in cohorts.values()]))
    rets = panel.loc[panel["permno"].isin(names) & panel["date"].between(months[0], months[-1])]
    log(f"{len(cohorts)} cohorts, {len(names):,} distinct names")

    # Stock-level hit rates (long names beating their industry over the n-month holding period, short names lagging it)
    # are computed per reported window in metrics(): only cohorts held entirely inside it count (R3).
    hit_frame = e[["date", "dec"] + [f"adj_{n}" for n in NS]]

    # --- Simulations, ledgers, reconciliation ---------------------------------------------------------------------
    runs, recon, positions = {}, [], {}
    for conv, mode in CONVS.items():
        for n in NS:
            for borrow in (True, False):
                out = ls.simulate(cohorts, rets, rf, months, n, borrow=borrow, keep_positions=(n == 3 and borrow), rebalance=mode)
                rec, led, pnl = out[:3]
                if n == 3 and borrow:
                    positions[conv] = out[3]
                runs[(conv, n, borrow)] = rec
                t = led.loc[led["action"].isin(TRADES)].groupby("date")["notional"].apply(lambda x: x.abs().sum())
                d_trade = float((t.reindex(rec.index, fill_value=0) - rec["traded"]).abs().max())
                d_pnl = float((pnl.groupby("date")["pnl"].sum().reindex(rec.index, fill_value=0)
                               - (rec["long_pnl"] - rec["short_pnl"])).abs().max())
                ruined = rec.attrs["ruined_at"]
                recon.append({"convention": conv, "n": n, "borrow": borrow, "months_run": len(rec),
                              "ruined_at": ruined.date() if ruined is not None else None, "ledger_rows": len(led),
                              "max_abs_turnover_diff": d_trade, "max_abs_pnl_diff": d_pnl,
                              "exits_settled": int(led["action"].eq("exit").sum())})
                assert d_trade < 1e-10 and d_pnl < 1e-10, (conv, n, borrow, d_trade, d_pnl)
                if borrow:
                    led.to_parquet(LEDGERS / f"ledger_n{n}_{mode}.parquet", index=False)
                log(f"{conv} n={n} borrow={borrow}: {len(rec)} months"
                    + (f" RUINED {ruined.date()}" if ruined is not None else "")
                    + f"; ledger {len(led):,} rows, reconciliation {d_trade:.1e} / {d_pnl:.1e}")
    pd.DataFrame(recon).to_csv(out_dir / "ledger_reconciliation.csv", index=False)
    if LEDGERS.resolve().is_relative_to(FINAL.resolve()):            # inside the repository: must be ignored
        ign = subprocess.run(["git", "check-ignore", "-v", str(LEDGERS / "ledger_n3_hold.parquet")], cwd=FINAL, capture_output=True, text=True)
        assert ign.returncode == 0, "ledger is not git-ignored"


    def metrics(rec, bps, first_month, n):
        """Metrics from `first_month` (all n cohorts live) to the end of the run, or to the ruin month."""
        sample = rec.index[rec.index >= first_month]
        net = ls.net_return(rec, bps).loc[sample]
        ruin_m = net.index[(1 + net) <= 0]
        if len(ruin_m):                                   # a cost can bring ruin forward
            net = net.loc[: ruin_m[0]]
            sample = net.index
        ex = net - rf.loc[sample]
        wealth = (1 + net).cumprod()
        dd = float((wealth / wealth.cummax().clip(lower=1) - 1).min())
        con = ls.contributions(rec, bps).loc[sample]
        sd = ex.std(ddof=1)
        return {"months": len(ex), "first": sample[0].date(), "last": sample[-1].date(),
                "ruined": bool(len(ruin_m)), "er_over_rf_annual": float(12 * ex.mean()),
                "vol_annual": float(np.sqrt(12) * sd), "ir": float(np.sqrt(12) * ex.mean() / sd),
                "hit_rate_months": float((ex > 0).mean()), "max_drawdown": max(dd, -1.0),
                "skew": float(ex.skew()), "excess_kurtosis": float(ex.kurt()),
                "turnover_one_way_monthly": float(0.5 * rec.loc[sample, "traded"].mean()),
                "corr_crsp_vw": float(ex.corr(mkt.loc[sample])),
                "long_contribution_annual": float(12 * con["long"].mean()),
                "short_contribution_annual": float(12 * con["short"].mean()),
                "collateral_rf_annual": float(12 * con["collateral_rf"].mean()),
                "borrow_annual": float(12 * rec.loc[sample, "borrow"].mean()),
                "cost_interaction_annual": float(12 * con["cost_interaction"].mean()),
                **ls.stock_hit_rates(hit_frame, n, sample[0], sample[-1])}


    rows = []
    for conv in CONVS:
        for n in NS:
            for borrow in (True, False):
                for c in COSTS:
                    rows.append({"convention": conv, "role": ROLE[conv], "n": n, "cost_bps": c,
                                 "borrow": "with" if borrow else "without", **metrics(runs[(conv, n, borrow)], c, months[n - 1], n)})
    nxc = pd.DataFrame(rows)
    nxc.to_csv(out_dir / "nxc.csv", index=False)

    # Subperiods (n = 3, 10 bps): each period starts with fresh capital, from cohorts formed in the period.
    sub = []
    for conv, mode in CONVS.items():
        for borrow in (True, False):
            for pname, (lo, hi) in PERIODS.items():
                pm = months[(months >= lo) & (months <= hi)]
                co = {f: c for f, c in cohorts.items() if pm[0] - pd.offsets.MonthEnd(1) <= f < pm[-1]}
                rec = ls.simulate(co, rets, rf, pm, 3, borrow=borrow, rebalance=mode)[0]
                sub.append({"convention": conv, "role": ROLE[conv], "n": 3, "cost_bps": 10,
                            "borrow": "with" if borrow else "without", "period": pname, "ruined_at": rec.attrs["ruined_at"],
                            **metrics(rec, 10, pm[2], 3)})
    pd.DataFrame(sub).to_csv(out_dir / "subperiods_n3_c10.csv", index=False)
    log("metrics done")

    # --- Industry attribution (bonus): 12 EW industry excess returns of the universe ----------------------------
    ind = e.loc[e["ff12"].ne("Unknown")].groupby(["date", "ff12"])["fwd_1"].mean().unstack()
    ind.index = ind.index + pd.offsets.MonthEnd(1)
    ind = ind.reindex(months).sub(rf, axis=0)
    att = []
    for conv in CONVS:
        for label, borrow, c in [("n = 3, 10 bps, with borrow", True, 10), ("n = 3, gross (0 bps, no borrow)", False, 0)]:
            net = ls.net_return(runs[(conv, 3, borrow)], c).loc[months[2]:]
            if (1 + net).le(0).any():
                net = net.loc[: net.index[(1 + net) <= 0][0]]
            y = net - rf.reindex(net.index)
            res = stats.ols(y, ind.loc[y.index], 12)
            r2 = 1 - (1 - res["adj_r2"]) * (res["n"] - 1 - 12) / (res["n"] - 1)
            att.append({"convention": conv, "series": label, "first": y.index.min().date(), "last": y.index.max().date(),
                        "r2": r2, "adj_r2": res["adj_r2"], "residual_alpha_annual": res["alpha_annual"],
                        "alpha_t_nw": res["alpha_t_nw"], "alpha_t_ols": res["alpha_t_ols"], "n": res["n"],
                        **{f"beta_{k}": res[f"beta_{k}"] for k in ind.columns}})
    pd.DataFrame(att).to_csv(out_dir / "industry_attribution.csv", index=False)

    # --- Capacity (n = 3, with borrow): participation of each position in its monthly dollar volume -------------
    # Cohort fragments are summed by (date, security, side) first; long and short of one security are not netted (R2).
    msi = pd.read_parquet(config.RAW / "msi.parquet")
    tot = msi.assign(date=pd.to_datetime(msi["date"]) + pd.offsets.MonthEnd(0)).set_index("date")["totval"]
    defl = (tot / tot.loc[pd.Timestamp("2024-12-31")]).reindex(months)
    dv = panel[["date", "permno"]].assign(dollar_volume=panel["vol"] * 100 * panel["prc"].abs())  # vol in hundreds of shares
    cap = []
    for conv in CONVS:
        pos = ls.participation_per_dollar(positions[conv], dv, defl)
        decade = lambda d: (d.dt.year // 10 * 10).astype(str) + "s"
        pos["decade"] = decade(pos["date"])
        frags = decade(positions[conv]["date"]).value_counts()
        for dec, g in list(pos.groupby("decade")) + [("all", pos)]:
            x = g.loc[g["covered"], "per_dollar_aum"]
            row = {"convention": conv, "role": ROLE[conv], "decade": dec,
                   "cohort_fragments": int(frags.sum() if dec == "all" else frags[dec]), "positions": len(g), "with_dollar_volume": int(g["covered"].sum()),
                   "capacity_aum_2024usd_p95_at_10pct": ls.capacity_aum(x)}
            for k, a in AUMS.items():
                row[f"median_participation_{k}"] = float(a * x.median()) if len(x) else np.nan
                row[f"p95_participation_{k}"] = float(a * x.quantile(0.95)) if len(x) else np.nan
            cap.append(row)
    pd.DataFrame(cap).to_csv(out_dir / "capacity.csv", index=False)
    log("attribution and capacity done")

    # --- The paper engine is unchanged: Conservative 1929-2016 is bit-identical to the replication ----------------
    p16 = pd.read_parquet(config.PANEL_FILE)
    p16 = p16.loc[p16["date"].le("2016-12-31")].reset_index(drop=True)
    b16 = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"]).query("date <= '2016-12-31'")
    p16, b16 = engine.validate_inputs(p16, b16)
    tg, _ = engine.formation_targets(engine.attach_signals(p16), ["Conservative"], start=pd.Timestamp("1929-01-31"),
                                     last=pd.Timestamp("2016-12-31"))
    cons = engine.backtest(p16, b16, tg["Conservative"], pd.Timestamp("1929-01-31"), pd.Timestamp("2016-12-31"), 0)["gross"]
    ref = pd.read_csv(ctx.result("replication", "returns_monthly.csv"),
                      parse_dates=["date"], index_col="date", float_precision="round_trip")["Conservative_gross"]
    identical = bool(np.array_equal(cons.to_numpy(), ref.to_numpy()) and cons.index.equals(ref.index))
    pd.DataFrame([{"check": "Conservative gross 1929-2016 re-run == replication series", "bit_identical": identical,
                   "months": len(cons)}]).to_csv(out_dir / "engine_unchanged.csv", index=False)
    assert identical
    log(f"paper engine unchanged: {identical}")

    # --- Figures ---------------------------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), layout="constrained")
    colors = dict(zip(NS, ["#176B87", "#C0504D", "#7F7F7F", "#9BBB59"]))
    for n in NS:
        rec = runs[("monthly re-weighted (JT)", n, True)]
        w = (1 + ls.net_return(rec, 10).loc[months[n - 1]:]).cumprod()
        axes[0].plot(w.index, w, lw=1.1, color=colors[n], label=f"n = {n}")
        for conv, style in [("monthly re-weighted (JT)", "-"), ("buy-and-hold", ":")]:
            r = nxc.loc[nxc["n"].eq(n) & nxc["borrow"].eq("with") & nxc["convention"].eq(conv)]
            axes[1].plot(r["cost_bps"], r["ir"], marker="o", ls=style, color=colors[n],
                         label=f"n = {n}" if conv.startswith("monthly") else None)
    axes[0].set(yscale="log", ylabel="Wealth (log)",
                title="Decile long/short (composite), monthly re-weighted cohorts, 10 bps, with borrow")
    axes[1].set(xlabel="Cost per dollar traded per side (bps)", ylabel="IR (excess over rf), with borrow",
                title="IR by n and cost (solid: monthly re-weighted; dotted: buy-and-hold, up to ruin)")
    axes[1].axhline(0, color="black", lw=0.6)
    for ax in axes:
        ax.legend(fontsize=8)
    fig.savefig(out_dir / "fig_longshort.png", dpi=150)
    plt.close(fig)
    log("done: " + ", ".join(sorted(p.name for p in out_dir.iterdir())))
