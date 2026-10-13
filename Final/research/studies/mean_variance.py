"""Review-added mean-variance extension: two fixed risk aversions, 5% FF12 bands, 40% turnover, 30bps.
Heuristics are exploratory and introduced after the baseline was observed; no claim of out-of-sample tuning.
"""
import numpy as np
import pandas as pd
from crsp_pipeline import config
from research import engine, diagnostics as dg, mean_variance as mv, optimize as opt, report, stats, longshort as ls

NAME = "mean_variance"
DEPENDS = ("diagnostics",)
FIXED_END = "2024-12-31"
FILES = {k: {"description": d, "window": "1929-2024", "returns": "net of scaled 30bps and gross",
             "role": "exploratory"} for k, d in {
    "summary.csv": "Mean-variance metrics at risk aversion 5 and 20, by sample",
    "returns_monthly.csv": "Monthly QP returns, costs and traded notional",
    "solver_checks.csv": "Maximum violations, relaxations and predicted risk",
    "capacity.csv": "QP holding capacity at 10% volume participation (no impact model)"}.items()}


def run(ctx):
    p, b = engine.validate_inputs(pd.read_parquet(config.PANEL_FILE),
                                 pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"]))
    e = pd.read_parquet(ctx.universe_cache(), columns=["date", "permno", "ff12", "mktcap", "vol36", "composite_z", "adj_3"])
    ic = opt.trailing_ic(dg.spearman_by_date(e, "composite_z", "adj_3"), 3, 12)
    forms = engine.formation_dates(p.date, pd.Timestamp(config.FIRST_INVESTMENT), ctx.end)
    history = p.pivot(index="date", columns="permno", values="ret_total")
    sig = engine.attach_signals(p)
    snapshots = {f: s.set_index("permno") for f, s in sig.loc[sig.date.isin(forms)].groupby("date")}
    universe = {f: u.set_index("permno") for f, u in e.loc[e.date.isin(forms)].groupby("date")}
    factors = pd.read_csv(config.FACTORS_FILE, parse_dates=["date"], index_col="date")
    rows, checks, monthly, capacity = [], [], {}, []
    dv = p[["date", "permno"]].assign(dollar_volume=p.vol*100*p.prc.abs())
    msi = pd.read_parquet(config.RAW / "msi.parquet")
    tot = msi.assign(date=pd.to_datetime(msi.date)+pd.offsets.MonthEnd(0)).set_index("date").totval
    deflator = tot/tot.loc[pd.Timestamp("2024-12-31")]
    for gamma in [5.0, 20.0]:
        targets, costs, info, positions = {}, {}, [], []
        for f in forms:
            u = universe[f]
            alpha = opt.grinold_alpha(u.composite_z.fillna(0), u.vol36, float(ic.get(f)) if pd.notna(ic.get(f)) else 0.0, 3)
            c = opt.tcost(snapshots[f], u, 30)
            costs[f] = c
            bounds = opt.industry_bounds(u.ff12, u.mktcap, 0.05)
            hist = history.loc[f-pd.offsets.MonthEnd(35):f, u.index]
            def target(previous, cash, f=f, u=u, alpha=alpha, c=c, bounds=bounds, hist=hist):
                try:
                    w, rec = mv.solve(alpha, hist, previous, c, u.ff12, bounds,
                                      None if f == forms[0] else 0.4, risk_aversion=gamma)
                except ValueError as exc:
                    raise ValueError(f"QP formation {f.date()}, gamma {gamma:g}: {exc}") from exc
                info.append({"formation": f, "risk_aversion": gamma, "bands_relaxed": int(bounds.relaxed.sum()),
                             "latest_risk_observation": hist.index.max(), **rec})
                positions.append(pd.DataFrame({"date": f+pd.offsets.MonthEnd(1), "permno": w.index,
                                               "side": "long", "value": w.to_numpy()}))
                if len(info) % 96 == 0: ctx.log(f"QP gamma {gamma:g}: {len(info)}/{len(forms)} formations")
                return w
            targets[f] = target
        run = engine.backtest(p, b, targets, config.FIRST_INVESTMENT, ctx.end, name_costs=costs)
        chk = pd.DataFrame(info)
        recon = np.abs(run.loc[chk.formation+pd.offsets.MonthEnd(1), "traded_notional"].to_numpy()-chk.turnover.to_numpy()).max()
        assert recon < 1e-8 and (chk.latest_risk_observation <= chk.formation).all()
        checks.append({"risk_aversion": gamma, "formations": len(chk), "max_constraint_violation": chk.max_violation.max(),
                       "turnover_relaxations": int(chk.turnover_relaxed.sum()), "industry_lower_bound_relaxations": int(chk.bands_relaxed.sum()),
                       "traded_notional_reconciliation": recon, "mean_predicted_vol_annual": chk.predicted_vol_annual.mean(),
                       "risk_window_lookahead_violations": 0})
        checks[-1].update(non_solved_statuses=int(chk.solver_status.ne("solved").sum()),
                          maximum_dual_residual=chk.dual_residual.max(), solver="Clarabel")
        for col in ["gross", "net", "cost_fraction", "traded_notional"]: monthly[f"gamma{gamma:g}_{col}"] = run[col]
        for label, (lo, hi) in {"1929–2024": (config.FIRST_INVESTMENT, str(ctx.end.date())), **report.PERIODS}.items():
            r = run.loc[lo:hi]
            active = r.net-b.loc[r.index, "market_ret"]
            reg = stats.ols(r.net-b.loc[r.index, "rf"], factors.loc[r.index, ["mktrf", "smb", "hml", "umd"]], 12)
            reb = report.rebalance_months(r.index)
            reb = reb[reb > pd.Timestamp(config.FIRST_INVESTMENT)]
            rows.append({"risk_aversion": gamma, "period": label, **report.statistics(r.net, b.rf),
                         "gross_compounded": report.statistics(r.gross, b.rf)["compounded"],
                         "excess_return_annual": 12*active.mean(), "ir": np.sqrt(12)*active.mean()/active.std(),
                         "hit_ratio": (active > 0).mean(), "skew_active": active.skew(), "kurtosis_active": active.kurt(),
                         "corr_market": r.net.corr(b.loc[r.index, "market_ret"]),
                         "turnover_quarter": float(.5*r.loc[reb, "traded_notional"].mean()),
                         "cost_annual": 12*r.cost_fraction.mean(), "carhart_alpha": reg["alpha_annual"],
                         "alpha_ci_low": reg["alpha_ci95_low"], "alpha_ci_high": reg["alpha_ci95_high"]})
        x = ls.participation_per_dollar(pd.concat(positions, ignore_index=True), dv, deflator)
        for dec, g in list(x.groupby((x.date.dt.year//10*10).astype(str)+"s")) + [("all", x)]:
            capacity.append({"risk_aversion": gamma, "decade": dec, "positions": len(g), "covered": int(g.covered.sum()),
                             "aum_2024usd_p95_at_10pct": ls.capacity_aum(g.loc[g.covered, "per_dollar_aum"])})
        ctx.log(f"QP risk aversion {gamma:g} finished; max constraint violation {chk.max_violation.max():.2g}")
    out = ctx.out(NAME)
    pd.DataFrame(rows).to_csv(out/"summary.csv", index=False)
    pd.DataFrame(checks).to_csv(out/"solver_checks.csv", index=False)
    pd.DataFrame(monthly).rename_axis("date").to_csv(out/"returns_monthly.csv")
    pd.DataFrame(capacity).to_csv(out/"capacity.csv", index=False)
