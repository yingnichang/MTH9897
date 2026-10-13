"""Independent reconstruction and the professor's payout/sector checks, added during final review.
No licensed observations are written to results; sector contributions are arithmetic, not compounded attribution.
"""
import json
import numpy as np
import pandas as pd
from crsp_pipeline import config
from research import engine, report, results, stats

NAME = "professor_checks"
DEPENDS = ("critical_tests",)
FIXED_END = "2024-12-31"
FILES = {k: {"description": d, "window": "1929-2024", "returns": "gross and net", "role": "check"} for k, d in {
    "independent_checks.csv": "Data hashes, independently calculated signals, portfolio returns and HAC statistics",
    "payout_comparison.csv": "Matched dividends-only counterfactual, genuine NPY baseline, and paired changes",
    "payout_components.csv": "Dividend and adjusted-share contribution among baseline holdings",
    "sector_quota_checks.csv": "Sector-by-sector 100-stock variant using count-proportional FF12 quotas",
    "sector_attribution.csv": "Exact monthly allocation, selection, and fixed-universe versus CRSP market bridge",
    "sector_exposures.csv": "Baseline and reference FF12 weights and active weights",
    "sector_monthly.csv": "Monthly attribution with cash and terminal events preserved"}.items()}


def independently_select(snapshot, payout="npy"):
    u = snapshot.loc[snapshot.eligible & snapshot.hist36 & ~snapshot.is_exit & snapshot.mktcap.gt(0)]
    u = u.sort_values(["mktcap", "permno"], ascending=[False, True]).iloc[:1000]
    pool = u.sort_values(["vol36", "permno"]).iloc[:len(u)//2].dropna(subset=["momentum", "npy"])
    score = (pool.momentum.rank(ascending=False)+pool[payout].rank(ascending=False))/2
    chosen = pool.assign(score=score).sort_values(["score", "permno"]).iloc[:100]
    return pd.Series(np.repeat(1/len(chosen), len(chosen)), index=chosen.permno.to_numpy()), u


def sector_quota_weights(universe):
    """Professor's count-proportional example: allocate 100 slots, select separately within FF12.
    Largest-remainder quotas; within each industry select its low-volatility half, then combined ranks.
    This changes the paper's global screen and is explicitly an exploratory robustness variant.
    """
    u = universe.assign(industry=universe.ff12.fillna("Unknown"))
    pools = {g: s.sort_values(["vol36", "permno"]).iloc[:max(1, (len(s)+1)//2)].dropna(subset=["momentum", "npy"])
             for g, s in u.groupby("industry")}
    share = u.industry.value_counts().sort_index()/len(u)
    desired = share*100
    quota = np.floor(desired).astype(int)
    if any(quota[g] > len(pools[g]) for g in quota.index):
        raise ValueError("Industry quota exceeds its eligible low-volatility pool")
    order = sorted(quota.index, key=lambda g: (-(desired[g]-quota[g]), g))
    while quota.sum() < 100:
        progressed = False
        for g in order:
            if quota[g] < len(pools[g]):
                quota[g] += 1
                progressed = True
                if quota.sum() == 100: break
        if not progressed: raise ValueError("Not enough eligible names for industry quotas")
    names = []
    for g, pool in pools.items():
        rank = (pool.momentum.rank(ascending=False)+pool.npy.rank(ascending=False))/2
        names.extend(pool.assign(score=rank).sort_values(["score", "permno"]).iloc[:quota[g]].permno)
    w = pd.Series(.01, index=names)
    return w, float((quota/100-share).abs().max())


def independent_path(panel, benchmark, targets, groups):
    """Dollar holdings and cash, rather than the engine's normalized-weight recursion."""
    monthly = {d: g.set_index("permno") for d, g in panel.groupby("date")}
    values, cash, records, sectors = pd.Series(dtype=float), 1.0, [], []
    for date in pd.date_range(config.FIRST_INVESTMENT, config.EXTRACT_END, freq="ME"):
        formation = date-pd.offsets.MonthEnd(1)
        nav = values.sum()+cash
        turnover = 0.0
        if formation in targets:
            target = targets[formation]
            turnover = float(
                (target.reindex(target.index.union(values.index), fill_value=0)
                 - values.reindex(target.index.union(values.index), fill_value=0)/nav).abs().sum())
            values, cash = target*nav, 0.0
            current_groups = groups[formation]
        rates = monthly[date].reindex(values.index)
        if rates.ret_hold.isna().any(): raise ValueError("Missing held return in independent reconstruction")
        r = rates.ret_hold
        cg = current_groups.reindex(values.index)
        if cg.isna().any(): raise ValueError("Missing formation industry")
        weights = values/nav
        sw = weights.groupby(cg).sum()
        sr = (weights*r).groupby(cg).sum()/sw
        sw.loc["Cash"], sr.loc["Cash"] = cash/nav, benchmark.loc[date, "rf"]
        sectors.extend({"date": date, "industry": g, "weight": sw[g], "return": sr[g]} for g in sw.index)
        grown = values*(1+r)
        next_cash = cash*(1+benchmark.loc[date, "rf"])+grown.loc[rates.is_exit].sum()
        values, cash = grown.loc[~rates.is_exit], next_cash
        gross = (values.sum()+cash)/nav-1
        records.append({"date": date, "gross": gross, "net30": (1-.003*turnover)*(1+gross)-1,
                        "traded_notional": turnover})
    return pd.DataFrame(records).set_index("date"), pd.DataFrame(sectors)


def run(ctx):
    p = pd.read_parquet(config.PANEL_FILE)
    b = pd.read_csv(config.BENCHMARK_FILE, parse_dates=["date"], index_col="date")
    sig = engine.attach_signals(p)
    checks = []
    def check(name, error, tolerance, n):
        checks.append({"check": name, "maximum_error": float(error), "tolerance": tolerance, "observations": n, "passed": error <= tolerance})
        assert error <= tolerance, checks[-1]
    man = json.loads(config.MANIFEST_FILE.read_text(encoding="utf-8"))
    items = {**man["raw_inputs"], **man["outputs"], **man["audits"]}
    check("Raw, normalized, and audit file hashes", sum(results.sha256(config.DATA/k) != h for k, h in items.items()), 0, len(items))
    check("Duplicate security months", p.duplicated(["date", "permno"]).sum(), 0, len(p))
    check("Duplicate eligible companies per month", p.loc[p.eligible].duplicated(["date", "permco"]).sum(), 0, int(p.eligible.sum()))
    sample = sig.loc[sig.hist36 & sig.npy.notna() & sig.momentum.notna()].sample(1200, random_state=9897)
    paths = {k: g.set_index("date").sort_index() for k, g in p.loc[p.permno.isin(sample.permno)].groupby("permno")}
    errors = {s: [] for s in ["vol36", "momentum", "div_yield", "net_issuance", "npy"]}
    for _, row in sample.iterrows():
        history = paths[row.permno].reindex(pd.date_range(row.date-pd.offsets.MonthEnd(35), row.date, freq="ME"))
        vol = history.ret_total.std(ddof=1)*np.sqrt(12)
        mom = np.prod(1+history.ret_price.iloc[-12:-1])-1
        dy = history.div_cash_adj.iloc[-12:].sum()/history.price_adj.iloc[-1]
        ni = history.shares_adj.iloc[-1]/history.shares_adj.iloc[-24:].mean()-1
        for key, v in zip(errors, [vol, mom, dy, ni, dy-ni]): errors[key].append(abs(row[key]-v))
    for key, err in errors.items(): check(f"Independent 36/12/24 month calculation: {key}", max(err), 1e-8, len(err))
    forms = engine.formation_dates(p.date, pd.Timestamp(config.FIRST_INVESTMENT), ctx.end)
    targets, div_targets, quota_targets, universe_targets, groups, components, quota_checks = {}, {}, {}, {}, {}, [], []
    mismatches = 0
    for f, s in sig.loc[sig.date.isin(forms)].groupby("date"):
        w, u = independently_select(s)
        reference, _ = engine.choose_weights(s, "Conservative")
        mismatches += len(set(w.index)^set(reference.index))
        targets[f] = w
        div_targets[f], _ = independently_select(s, "div_yield")
        quota_targets[f], quota_gap = sector_quota_weights(u)
        quota_checks.append({"formation": f, "holdings": len(quota_targets[f]), "sum_weights": quota_targets[f].sum(),
                             "max_abs_industry_weight_minus_universe_count_weight": quota_gap})
        universe_targets[f] = u.set_index("permno").mktcap/u.mktcap.sum()
        groups[f] = u.set_index("permno").ff12.fillna("Unknown")
        chosen = s.set_index("permno").loc[w.index]
        components.append({"date": f+pd.offsets.MonthEnd(1), "dividend_yield": chosen.div_yield.mean(),
                           "net_repurchase_proxy": -chosen.net_issuance.mean(), "npy": chosen.npy.mean(),
                           "buyback_fraction": chosen.net_issuance.lt(0).mean(),
                           "baseline_dividends_only_overlap": len(set(w.index)&set(div_targets[f].index))/100})
    check("Independent conservative selections", mismatches, 0, len(forms)*100)
    base, sector_p = independent_path(p, b, targets, groups)
    div, _ = independent_path(p, b, div_targets, groups)
    quota_run, _ = independent_path(p, b, quota_targets, groups)
    universe, sector_b = independent_path(p, b, universe_targets, groups)
    ref = pd.read_csv(ctx.result("critical_tests", "returns_monthly.csv"), parse_dates=["date"], index_col="date")
    for mine, theirs in [("gross", "Conservative | gross"), ("net30", "Conservative | net30")]:
        check(f"Independent dollar-holdings reconstruction: {mine}", np.max(np.abs(base[mine]-ref[theirs])), 1e-11, len(base))
    # Independent regression and HAC: direct double-lag products, checked against the project's routine.
    f = pd.read_csv(config.FACTORS_FILE, parse_dates=["date"], index_col="date")
    y = (base.gross-b.rf).loc["1929-01-31":"2016-12-31"]
    X = np.c_[np.ones(len(y)), f.loc[y.index, ["mktrf", "smb", "hml", "umd"]]]
    beta = np.linalg.solve(X.T@X, X.T@y.to_numpy())
    score = X*(y.to_numpy()-X@beta)[:, None]
    meat = score.T@score
    for lag in range(1, 13):
        cross = sum(np.outer(score[t], score[t-lag]) for t in range(lag, len(score)))
        meat += (1-lag/13)*(cross+cross.T)
    bread = np.linalg.inv(X.T@X)
    se = 12*np.sqrt((bread@meat@bread)[0, 0])
    official = stats.ols(y, f.loc[y.index, ["mktrf", "smb", "hml", "umd"]], 12)
    check("Independent Carhart alpha and Newey-West SE", max(abs(12*beta[0]-official["alpha_annual"]), abs(se-official["alpha_se_nw"])), 1e-11, len(y))
    s = sector_p.merge(sector_b, on=["date", "industry"], how="outer", suffixes=("_p", "_b"))
    s[["weight_p", "weight_b"]] = s[["weight_p", "weight_b"]].fillna(0)
    s.return_b = s.return_b.fillna(0)
    s.return_p = s.return_p.fillna(s.return_b)
    s["active_weight"] = s.weight_p-s.weight_b
    s["allocation"] = s.active_weight*s.return_b
    s["selection"] = s.weight_p*(s.return_p-s.return_b)
    attr = s.groupby("date")[["allocation", "selection"]].sum()
    attr["universe_minus_market"] = universe.gross-b.market_ret
    attr["baseline_minus_market"] = base.gross-b.market_ret
    check("Allocation + selection + universe bridge", (attr.allocation+attr.selection+attr.universe_minus_market-attr.baseline_minus_market).abs().max(), 1e-11, len(attr))
    periods = {"1929–2016": ("1929-01-31", "2016-12-31"), "1929–2024": ("1929-01-31", "2024-12-31"), **report.PERIODS}
    comparisons, attribution, exposure, comps = [], [], [], []
    components = pd.DataFrame(components).set_index("date")
    for label, (lo, hi) in periods.items():
        paired = stats.ols((base.net30-div.net30).loc[lo:hi], pd.DataFrame(index=base.loc[lo:hi].index), 12)
        for name, run in [("Baseline NPY", base), ("Dividends-only counterfactual", div), ("Sector quota variant", quota_run)]:
            st = report.statistics(run.gross.loc[lo:hi], b.rf)
            reb = report.rebalance_months(run.loc[lo:hi].index)
            reb = reb[reb > pd.Timestamp(config.FIRST_INVESTMENT)]
            comparisons.append({"period": label, "strategy": name, **st,
                                "net30_compounded": report.statistics(run.net30.loc[lo:hi], b.rf)["compounded"],
                                "turnover_quarter": float(.5*run.loc[reb, "traded_notional"].mean()),
                                "paired_npy_minus_div_net30_mean": paired["alpha_annual"],
                                "paired_ci_low": paired["alpha_ci95_low"], "paired_ci_high": paired["alpha_ci95_high"]})
        a = attr.loc[lo:hi]
        attribution.append({"period": label, "months": len(a), **{k+"_annual": 12*a[k].mean() for k in a.columns}})
        ss = s.loc[s.date.between(lo, hi)]
        for industry, rows in ss.groupby("industry"):
            exposure.append({"period": label, "industry": industry, "mean_portfolio_weight": rows.weight_p.mean(),
                             "mean_reference_weight": rows.weight_b.mean(), "mean_active_weight": rows.active_weight.mean(),
                             "max_portfolio_weight": rows.weight_p.max(), "allocation_annual": 12*rows.allocation.mean(),
                             "selection_annual": 12*rows.selection.mean()})
        comps.append({"period": label, **components.loc[lo:hi].mean().to_dict()})
    out = ctx.out(NAME)
    for name, frame in [("independent_checks", checks), ("payout_comparison", comparisons), ("payout_components", comps),
                        ("sector_attribution", attribution), ("sector_exposures", exposure)]:
        pd.DataFrame(frame).to_csv(out/f"{name}.csv", index=False)
    attr.rename_axis("date").to_csv(out/"sector_monthly.csv")
    pd.DataFrame(quota_checks).to_csv(out/"sector_quota_checks.csv", index=False)
    ctx.log(f"Professor checks: {len(checks)} passed; {len(base)} independently reconstructed months")
