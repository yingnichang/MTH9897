"""Linear industry-constrained optimization on CRSP (Trading 2 and 4), quarterly, 1929-01 .. 2024-12.
Ported unchanged from the closed task 2026-10-11-linear-optimization. A course extension, not the paper's rule: the
alpha is the diagnostic composite exposure. Runs: delta x tau x c0 (24) with size/volatility-scaled costs (the spec),
the same 24 with flat costs (comparison), and the same 24 with a Grinold-scaled alpha (a post-spec sensitivity).
"""
import itertools
import multiprocessing as mp
import time

import numpy as np
import pandas as pd

from crsp_pipeline import config
from research import diagnostics as dg, engine, longshort as ls, optimize as opt, report, stats

NAME = "optimization"
DEPENDS = ("replication", "diagnostics")
FIXED_END = "2024-12-31"                       # sample fixed at 2024-12: run_all rejects another --end
FILES = {
    'grid.csv': {'description': 'Optimization grid, full sample: delta x tau x c0 for the spec (z-score alpha, size/volatility costs), the flat-cost comparison and the Grinold-alpha sensitivity (post-spec; see the role column)', 'window': '1929-01 .. 2024-12', 'returns': 'net', 'role': 'primary'},
    'grid_subperiods.csv': {'description': 'Optimization grid by RS-006 period', 'window': 'RS-006 periods', 'returns': 'net', 'role': 'primary'},
    'capacity.csv': {'description': 'Capacity of each run by decade (positions at formation; 2024 dollars; no impact model)', 'window': '1929-01 .. 2024-12', 'returns': 'n/a', 'role': 'primary'},
    'relaxations.csv': {'description': 'Check: band and turnover-budget relaxations per run, solver tolerances, LP vs engine turnover', 'window': 'formations 1928-12 .. 2024-09', 'returns': 'n/a', 'role': 'check'},
    'trailing_ic.csv': {'description': 'Composite 3-month rank IC and its trailing (completed-horizon) mean used by the Grinold sensitivity', 'window': 'formations 1928-12 .. 2024-11', 'returns': 'gross', 'role': 'exploratory'},
    'engine_unchanged.csv': {'description': 'Check: paper engine Conservative 1929-2016 bit-identical to the replication series', 'window': '1929-01 .. 2016-12', 'returns': 'gross', 'role': 'check'},
    'fig_frontier.png': {'description': 'IR against realized turnover by industry band, cost level and variant', 'window': '1929-01 .. 2024-12', 'returns': 'net', 'role': 'primary'},
}
START, END = pd.Timestamp("1929-01-31"), pd.Timestamp("2024-12-31")
DELTAS = {"2%": 0.02, "5%": 0.05, "none": None}
TAUS = {"20%": 0.20, "40%": 0.40, "80%": 0.80, "none": None}
C0S = [10, 30]
VARIANTS = [("scaled", "z"), ("flat", "z"), ("scaled", "grinold")]   # (cost model, alpha); the first is the spec
IC_H, IC_MIN = 3, 12
CARHART = ["mktrf", "smb", "hml", "umd"]
G = {}                                                               # per-process data


def load(cache):
    """Data shared by every run (loaded once per process)."""
    panel = pd.read_parquet(config.PANEL_FILE)
    bench = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"])
    panel, bench = engine.validate_inputs(panel.loc[panel["date"].le(END)].reset_index(drop=True),
                                          bench.loc[bench["date"].le(END)])
    e = pd.read_parquet(cache,
                        columns=["date", "permno", "ff12", "mktcap", "vol36", "composite_z", "adj_3"])
    forms = engine.formation_dates(panel["date"], START, END)
    ic = dg.spearman_by_date(e, "composite_z", f"adj_{IC_H}")
    tic = opt.trailing_ic(ic, IC_H, IC_MIN)
    uni = {}
    for f, g in e.loc[e["date"].isin(forms)].groupby("date"):
        uni[f] = g.set_index("permno")[["ff12", "mktcap", "vol36", "composite_z"]]
    assert sorted(uni) == forms, "universe cache lacks a formation"
    snap = panel.loc[panel["date"].isin(forms), ["date", "permno", "mktcap"]]
    vol = engine.attach_signals(panel)[["date", "permno", "vol36"]]
    snap = snap.merge(vol, on=["date", "permno"], how="left")
    names = {f: g.set_index("permno")[["vol36", "mktcap"]] for f, g in snap.groupby("date")}
    G.update(panel=panel, bench=bench, forms=forms, uni=uni, names=names, tic=tic, ic=ic)


def run_one(key):
    """One configuration: LP targets inside the engine (drift-aware), per-name costs. Returns its frames."""
    if not G:
        raise RuntimeError("load(cache) first (the pool initializer does this)")
    cost_model, alpha_kind, dname, tname, c0 = key
    delta, tau = DELTAS[dname], TAUS[tname]
    t0 = time.time()
    targets, name_costs, infos, positions = {}, {}, [], []
    for i, f in enumerate(G["forms"]):
        u = G["uni"][f]
        ic_f = G["tic"].get(f, np.nan)
        if alpha_kind == "z":
            alpha = u["composite_z"]
        else:                                    # Grinold: IC x sigma_3m x z; no completed IC history yet -> alpha 0
            alpha = opt.grinold_alpha(u["composite_z"], u["vol36"], 0.0 if np.isnan(ic_f) else ic_f, IC_H)
        cost = opt.tcost(G["names"][f], u, c0, scaled=(cost_model == "scaled"))
        name_costs[f] = cost
        bounds = opt.industry_bounds(u["ff12"], u["mktcap"], delta)

        def target(holdings, cash, f=f, alpha=alpha, cost=cost, bounds=bounds, groups=u["ff12"], first=(i == 0)):
            w, info = opt.solve(alpha, holdings, cost, groups, bounds, None if first else tau)
            infos.append({"formation": f, "universe_n": len(alpha), "cash_before": cash, "ic_used": ic_f,
                          "bands_relaxed": int(bounds["relaxed"].sum()), "holdings_n": len(w),
                          **{k: info[k] for k in ("names", "held_outside_universe", "turnover", "turnover_lp", "turnover_min",
                                                  "tau_used", "turnover_relaxed", "alpha_exposure")}})
            positions.append(pd.DataFrame({"date": f + pd.offsets.MonthEnd(1), "permno": w.index, "side": "long",
                                           "value": w.to_numpy()}))
            return w
        targets[f] = target
    run = engine.backtest(G["panel"], G["bench"], targets, START, END, 0, name_costs=name_costs)
    info = pd.DataFrame(infos)
    # The LP's turnover is the engine's traded notional at each rebalance.
    reb = run.loc[[f + pd.offsets.MonthEnd(1) for f in info["formation"]], "traded_notional"].to_numpy()
    recon = float(np.abs(reb - info["turnover"].to_numpy()).max())
    return key, run, info, pd.concat(positions, ignore_index=True), recon, time.time() - t0


def metrics(run, bench, fac, lo, hi):
    r = run.loc[lo:hi]
    net, gross = r["net"], r["gross"]
    mkt, rf = bench.loc[r.index, "market_ret"], bench.loc[r.index, "rf"]
    act = net - mkt
    reb = report.rebalance_months(r.index)
    reb = reb[reb > START]                                     # the initial investment is excluded
    car = stats.ols(net - rf, fac.loc[r.index, CARHART], 12)
    return {"months": len(r), "first": r.index[0].date(), "last": r.index[-1].date(),
            "er_over_bench_annual": float(12 * act.mean()), "ir": float(np.sqrt(12) * act.mean() / act.std(ddof=1)),
            "tracking_error": float(np.sqrt(12) * act.std(ddof=1)), "hit_rate_months": float((act > 0).mean()),
            "max_drawdown": report.max_drawdown(net), "skew_active": float(act.skew()),
            "excess_kurtosis_active": float(act.kurt()), "net_arithmetic": float(12 * net.mean()),
            "gross_er_over_bench_annual": float(12 * (gross - mkt).mean()),
            "cost_annual": float(12 * r["cost_fraction"].mean()),
            "turnover_one_way_per_quarter": float(0.5 * r.loc[reb, "traded_notional"].mean()) if len(reb) else np.nan,
            "corr_market": float(net.corr(mkt)), "carhart_alpha_annual": car["alpha_annual"],
            "carhart_alpha_t_nw": car["alpha_t_nw"], "carhart_alpha_ci95_low": car["alpha_ci95_low"],
            "carhart_alpha_ci95_high": car["alpha_ci95_high"], "beta_mktrf": car["beta_mktrf"],
            "mean_holdings": float(r["holdings_n"].mean())}


def run(ctx, probe=False):
    log = ctx.log
    out_dir = ctx.out(NAME)
    assert pd.Timestamp(ctx.end) == pd.Timestamp("2024-12-31"), "this study's sample is fixed at 2024-12"
    cache = ctx.universe_cache()
    keys = [(cm, ak, d, t, c) for cm, ak in VARIANTS for d, t, c in itertools.product(DELTAS, TAUS, C0S)]
    if probe:
        load(cache)
        log("data loaded")
        for k in [("scaled", "z", "2%", "20%", 10), ("scaled", "grinold", "5%", "none", 30)]:
            _, run, info, pos, recon, sec = run_one(k)
            log(f"probe {k}: {sec:.0f}s, recon {recon:.1e}, band relaxations {info['bands_relaxed'].sum()}, "
                f"turnover relaxed {info['turnover_relaxed'].sum()}, mean holdings {info['holdings_n'].mean():.1f}, "
                f"ER {12 * (run['net'] - G['bench'].loc[run.index, 'market_ret']).mean():.4f}")
        print(G["tic"].loc[G["forms"]].describe())
        return
    with mp.Pool(3, initializer=load, initargs=(cache,)) as pool:                 # memory-bound: each worker holds the panel
        results = {}
        for key, run, info, pos, recon, sec in pool.imap_unordered(run_one, keys):
            results[key] = (run, info, pos, recon)
            log(f"{key}: {sec:.0f}s, recon {recon:.1e}, relaxed bands {int(info['bands_relaxed'].sum())} / "
                f"turnover {int(info['turnover_relaxed'].sum())}")
    load(cache)
    bench = G["bench"]
    fac = pd.read_csv(config.FACTORS_FILE, parse_dates=["date"], index_col="date")
    rows, sub, relax, cap = [], [], [], []
    msi = pd.read_parquet(config.RAW / "msi.parquet")
    tot = msi.assign(date=pd.to_datetime(msi["date"]) + pd.offsets.MonthEnd(0)).set_index("date")["totval"]
    defl = tot / tot.loc[pd.Timestamp("2024-12-31")]
    p = G["panel"]
    dv = p[["date", "permno"]].assign(dollar_volume=p["vol"] * 100 * p["prc"].abs()) if "vol" in p else None
    if dv is None:
        raw = pd.read_parquet(config.PANEL_FILE, columns=["date", "permno", "vol", "prc"])
        dv = raw[["date", "permno"]].assign(dollar_volume=raw["vol"] * 100 * raw["prc"].abs())
    for key in keys:
        run, info, pos, recon = results[key]
        cm, ak, d, t, c = key
        lab = {"cost_model": cm, "alpha": ak, "role": "spec" if (cm, ak) == VARIANTS[0] else
               ("comparison: flat costs" if cm == "flat" else "sensitivity: Grinold alpha (not in spec)"),
               "delta": d, "tau": t, "c0_bps": c}
        tr = info.iloc[1:]                                       # rebalances with a budget (initial excluded)
        relax_row = {**lab, "formations": len(info), "formations_with_band_relaxed": int(info["bands_relaxed"].gt(0).sum()),
                     "band_relaxations": int(info["bands_relaxed"].sum()),
                     "turnover_relaxed": int(tr["turnover_relaxed"].sum()),
                     "mean_relaxed_turnover": float(tr.loc[tr["turnover_relaxed"], "turnover"].mean())
                     if tr["turnover_relaxed"].any() else np.nan,
                     "held_outside_universe_mean": float(info["held_outside_universe"].mean()),
                     "max_abs_traded_vs_engine_turnover": recon,
                     "max_abs_traded_vs_lp_bs": float((info["turnover"] - info["turnover_lp"]).abs().max()),
                     "max_budget_overshoot": float((tr["turnover"] - pd.to_numeric(tr["tau_used"], errors="coerce")).max())}
        relax.append(relax_row)
        rows.append({**lab, **metrics(run, bench, fac, START, END),
                     "band_relaxations": relax_row["band_relaxations"], "turnover_relaxed": relax_row["turnover_relaxed"]})
        for pname in report.PERIODS:
            lo, hi = report.PERIODS[pname]
            sub.append({**lab, "period": pname, **metrics(run, bench, fac, pd.Timestamp(lo), pd.Timestamp(hi))})
        x = ls.participation_per_dollar(pos, dv, defl)
        x["decade"] = (x["date"].dt.year // 10 * 10).astype(str) + "s"
        for dec, g in list(x.groupby("decade")) + [("all", x)]:
            cv = g.loc[g["covered"], "per_dollar_aum"]
            cap.append({**lab, "decade": dec, "positions": len(g), "with_dollar_volume": int(g["covered"].sum()),
                        "capacity_aum_2024usd_p95_at_10pct": ls.capacity_aum(cv),
                        "median_participation_$1B": float(1e9 * cv.median()), "p95_participation_$1B": float(1e9 * cv.quantile(0.95))})
        assert recon < 1e-8, (key, recon)
    grid = pd.DataFrame(rows)
    grid.to_csv(out_dir / "grid.csv", index=False)
    pd.DataFrame(sub).to_csv(out_dir / "grid_subperiods.csv", index=False)
    pd.DataFrame(relax).to_csv(out_dir / "relaxations.csv", index=False)
    pd.DataFrame(cap).to_csv(out_dir / "capacity.csv", index=False)
    G["tic"].rename("trailing_ic").to_frame().join(G["ic"].rename("ic_h3")).to_csv(out_dir / "trailing_ic.csv")
    log("tables written")

    # The paper engine is unchanged: Conservative 1929-2016 re-run is bit-identical to the replication series.
    p16 = pd.read_parquet(config.PANEL_FILE)
    p16 = p16.loc[p16["date"].le("2016-12-31")].reset_index(drop=True)
    b16 = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"]).query("date <= '2016-12-31'")
    p16, b16 = engine.validate_inputs(p16, b16)
    tg, _ = engine.formation_targets(engine.attach_signals(p16), ["Conservative"], start=START, last=pd.Timestamp("2016-12-31"))
    cons = engine.backtest(p16, b16, tg["Conservative"], START, pd.Timestamp("2016-12-31"), 0)["gross"]
    ref = pd.read_csv(ctx.result("replication", "returns_monthly.csv"),
                      parse_dates=["date"], index_col="date", float_precision="round_trip")["Conservative_gross"]
    same = bool(np.array_equal(cons.to_numpy(), ref.to_numpy()) and cons.index.equals(ref.index))
    pd.DataFrame([{"check": "Conservative gross 1929-2016 re-run == replication series", "bit_identical": same,
                   "months": len(cons)}]).to_csv(out_dir / "engine_unchanged.csv", index=False)
    assert same
    log(f"paper engine unchanged: {same}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), layout="constrained", sharey=True)
    colors = {"2%": "#176B87", "5%": "#C0504D", "none": "#7F7F7F"}
    for ax, (cm, ak) in zip(axes, VARIANTS):
        for d in DELTAS:
            for c, mk in zip(C0S, ["o", "s"]):
                g = grid.loc[grid["cost_model"].eq(cm) & grid["alpha"].eq(ak) & grid["delta"].eq(d) & grid["c0_bps"].eq(c)]
                ax.plot(g["turnover_one_way_per_quarter"], g["ir"], marker=mk, color=colors[d], lw=0.8,
                        label=f"δ = {d}, c0 = {c} bps")
        ax.set(xlabel="Realized one-way turnover per quarter", title=f"{cm} costs, {ak} alpha"
               + (" (spec)" if (cm, ak) == VARIANTS[0] else ""))
        ax.axhline(0, color="black", lw=0.5)
    axes[0].set_ylabel("IR (net, over CRSP VW), 1929–2024")
    axes[0].legend(fontsize=7)
    fig.suptitle("Linear industry-constrained optimization (course extension; diagnostic composite alpha)")
    fig.savefig(out_dir / "fig_frontier.png", dpi=150)
    log("done")
