"""Fixture tests of research.optimize (linear industry-constrained optimization) and the engine's
per-name cost and drift-aware target extensions."""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research import engine, optimize as opt  # noqa: E402


def universe(n=100, seed=0, groups=("A", "B", "C", "D")):
    rng = np.random.default_rng(seed)
    idx = pd.Index(np.arange(1, n + 1), name="permno")
    return pd.DataFrame({"alpha": rng.normal(0, 0.5, n), "group": rng.choice(groups, n),
                         "mktcap": rng.lognormal(10, 1, n), "vol36": rng.uniform(0.04, 0.2, n)}, index=idx)


def test_tcost_scaling_bounds():
    u = universe()
    c = opt.tcost(u, u, 10)
    med_v, med_c = u["vol36"].median(), u["mktcap"].median()
    raw = (u["vol36"] / med_v) * np.sqrt(med_c / u["mktcap"])
    assert np.allclose(c, 10e-4 * raw.clip(0.5, 5))
    assert c.min() >= 0.5 * 10e-4 - 1e-18 and c.max() <= 5 * 10e-4 + 1e-18
    assert np.allclose(opt.tcost(u, u, 30), 3 * c)
    assert np.allclose(opt.tcost(u, u, 30, scaled=False), 30e-4)
    # A small, volatile name costs more than a large, calm one; medians come from the universe argument.
    names = pd.DataFrame({"vol36": [0.4, 0.02, np.nan], "mktcap": [1.0, 1e9, 5.0]}, index=[901, 902, 903])
    cn = opt.tcost(names, u, 10)
    assert cn[901] == 5 * 10e-4 and cn[902] == 0.5 * 10e-4
    assert cn[903] == 5 * 10e-4                        # missing input: the upper clip (logged convention)


def test_lp_respects_industry_band_and_caps():
    u = universe()
    for delta in (0.02, 0.05):
        bounds = opt.industry_bounds(u["group"], u["mktcap"], delta)
        w, info = opt.solve(u["alpha"], pd.Series(dtype=float), opt.tcost(u, u, 10), u["group"], bounds, tau=None)
        assert info["status"] == "optimal"
        assert np.isclose(w.sum(), 1) and w.min() >= -1e-12 and w.max() <= 0.02 + 1e-12
        expo = w.groupby(u["group"].reindex(w.index)).sum().reindex(bounds.index, fill_value=0)
        assert ((expo - bounds["B"]).abs() <= delta + 1e-9).all()
    # Without a band the LP simply holds the 50 best alphas at the 2% cap.
    w, _ = opt.solve(u["alpha"], pd.Series(dtype=float), pd.Series(0.0, index=u.index), u["group"], None, tau=None)
    assert set(w[w > 1e-9].index) == set(u["alpha"].nlargest(50).index)


def test_band_relaxation_rule():
    # Group A has 20% of the cap weight but only 5 names: 5 x 2% = 10% < B_A - delta = 14%, so its lower bound
    # drops to 10%. B and C (40% each) can absorb the deficit within their +6% bands.
    g = pd.Series(["A"] * 5 + ["B"] * 50 + ["C"] * 45, index=pd.RangeIndex(1, 101, name="permno"))
    cap = pd.Series([4.0] * 5 + [0.8] * 50 + [40 / 45] * 45, index=g.index)
    b = opt.industry_bounds(g, cap, 0.06)
    assert np.isclose(b.loc["A", "B"], 0.2) and b.loc["A", "relaxed"] and np.isclose(b.loc["A", "lo"], 0.10)
    assert not b.loc["B", "relaxed"] and np.isclose(b.loc["B", "lo"], 0.34) and np.isclose(b.loc["B", "hi"], 0.46)
    assert np.isinf(opt.industry_bounds(g, cap, None)["hi"]).all()
    alpha = pd.Series(np.linspace(1, 0, 100), index=g.index)
    w, info = opt.solve(alpha, pd.Series(dtype=float), pd.Series(1e-3, index=g.index), g, b, tau=None)
    assert info["status"] == "optimal" and np.isclose(w.loc[1:5].sum(), 0.10)


def test_lp_turnover_budget_binding():
    u = universe()
    prev = pd.Series(0.02, index=u["alpha"].nsmallest(50).index)          # holding the worst names
    cost = opt.tcost(u, u, 10)
    free, fi = opt.solve(u["alpha"], prev, cost, u["group"], None, tau=None)
    assert fi["turnover"] > 0.5                                           # the unconstrained optimum trades a lot
    w, info = opt.solve(u["alpha"], prev, cost, u["group"], None, tau=0.2)
    assert info["status"] == "optimal" and not info["turnover_relaxed"]
    traded = w.reindex(w.index.union(prev.index), fill_value=0) - prev.reindex(w.index.union(prev.index), fill_value=0)
    assert np.isclose(traded.abs().sum(), 0.2) and np.isclose(info["turnover"], 0.2)
    assert (u["alpha"].reindex(w.index) * w).sum() < (u["alpha"].reindex(free.index) * free).sum()


def test_turnover_budget_relaxed_to_minimum_feasible():
    # 30% of NAV is cash after exits, and a held name has left the universe: it must be sold, and the cash invested.
    u = universe()
    prev = pd.Series(0.02, index=list(u.index[:30]) + [999])               # 0.62 invested; 999 is not in the universe
    w, info = opt.solve(u["alpha"], prev, opt.tcost(u, u, 10).reindex(list(u.index) + [999], fill_value=1e-3),
                        u["group"], None, tau=0.1)
    assert info["status"] == "optimal" and info["turnover_relaxed"]
    assert w.get(999, 0) == 0
    assert np.isclose(info["turnover_min"], 0.42) and np.isclose(info["tau_used"], info["turnover_min"], rtol=1e-6, atol=1e-9)
    assert np.isclose(w.sum(), 1)


def test_lp_costs_reduce_trading():
    # Alphas are close, so a higher cost per dollar makes some swaps unprofitable.
    rng = np.random.default_rng(3)
    u = universe()
    u["alpha"] = rng.normal(0, 0.002, len(u))
    prev = pd.Series(0.02, index=u.index[rng.permutation(len(u))[:50]])
    turn = []
    for c0 in (0, 5, 10, 30, 100):
        _, info = opt.solve(u["alpha"], prev, opt.tcost(u, u, c0) if c0 else pd.Series(0.0, index=u.index),
                            u["group"], opt.industry_bounds(u["group"], u["mktcap"], 0.05), tau=None)
        turn.append(info["turnover"])
    assert all(a >= b - 1e-9 for a, b in zip(turn, turn[1:])) and turn[0] > turn[-1]


def test_trailing_ic_uses_completed_horizons_only():
    d = pd.date_range("2000-01-31", periods=30, freq="ME")
    ic = pd.Series(np.arange(30, dtype=float), index=d)
    t = opt.trailing_ic(ic, h=3, min_obs=12)
    # At formation d[k], the completed ICs are those formed at d[0..k-3].
    assert t.loc[: d[13]].isna().all() and np.isclose(t.loc[d[14]], np.arange(12).mean())
    assert np.isclose(t.loc[d[29]], np.arange(27).mean())
    ic2 = ic.copy()
    ic2.loc[d[27]:] = 1e6                                                  # data not yet complete at d[29]
    assert opt.trailing_ic(ic2, h=3, min_obs=12).loc[d[29]] == t.loc[d[29]]
    z = pd.Series([1.0, -2.0]); v = pd.Series([0.1, 0.05])
    assert np.allclose(opt.grinold_alpha(z, v, 0.05, h=3), 0.05 * v * np.sqrt(3 / 12) * z)


# --- Engine extensions -------------------------------------------------------------------------

def demo(n=60):
    p, b = engine.make_demo(n_stocks=n)
    p, b = engine.validate_inputs(p, b)
    s = engine.attach_signals(p)
    start, end = pd.Timestamp("2003-01-31"), pd.Timestamp("2006-12-31")
    tg, _ = engine.formation_targets(s, ["Universe equal weight"], start=start, last=end, n_universe=40)
    return p, b, s, tg["Universe equal weight"], start, end


def test_engine_per_name_costs_reconcile():
    p, b, s, tg, start, end = demo()
    flat = engine.backtest(p, b, tg, start, end, 30)
    uni = engine.backtest(p, b, tg, start, end, 0, name_costs={f: pd.Series(30e-4, index=s.loc[s["date"].eq(f), "permno"])
                                                                 for f in tg})
    assert np.allclose(uni["net"], flat["net"], rtol=0, atol=1e-15) and (uni["gross"] == flat["gross"]).all()
    # Nonuniform: the charge is sum_i c_i |trade_i| from the trade log.
    rng = np.random.default_rng(1)
    costs = {f: pd.Series(rng.uniform(1e-4, 5e-3, s["date"].eq(f).sum()), index=s.loc[s["date"].eq(f), "permno"]) for f in tg}
    log = []
    run = engine.backtest(p, b, tg, start, end, 0, trade_log=log, name_costs=costs)
    for fr in log:
        f = fr["formation"].iloc[0]
        q = f + pd.offsets.MonthEnd(1)
        charge = float((fr["trade"].abs() * costs[f].reindex(fr["permno"]).to_numpy()).sum())
        assert np.isclose(run.loc[q, "cost_fraction"], charge, rtol=0, atol=1e-15)
        assert np.isclose(run.loc[q, "net"], (1 - charge) * (1 + run.loc[q, "gross"]) - 1, rtol=0, atol=1e-15)
    assert (run["gross"] == flat["gross"]).all()
    bad = {f: c.drop(tg[f].index[0]) for f, c in costs.items()}
    with pytest.raises(ValueError, match="No cost"):
        engine.backtest(p, b, tg, start, end, 0, name_costs=bad)
    with pytest.raises(ValueError, match="not both"):
        engine.backtest(p, b, tg, start, end, 10, name_costs=costs)


def test_engine_callable_target_gets_drifted_weights():
    p, b, s, tg, start, end = demo()
    seen = {}

    def make(f, w):
        def target(holdings, cash):
            seen[f] = (holdings.copy(), cash)
            return w
        return target

    log = []
    run = engine.backtest(p, b, {f: make(f, w) for f, w in tg.items()}, start, end, 10, trade_log=log)
    ref = engine.backtest(p, b, tg, start, end, 10)
    pd.testing.assert_frame_equal(run, ref)
    for fr in log:
        f = fr["formation"].iloc[0]
        h, cash = seen[f]
        pre = fr.set_index("permno")["pre_weight"]
        assert np.allclose(h.reindex(pre.index, fill_value=0), pre, rtol=0, atol=0) and cash == fr["pre_cash"].iloc[0]


def frame_hash(df):
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes()).hexdigest()


def test_baseline_unchanged():
    # Hashes recorded with the engine before the per-name-cost and callable-target extensions
    # (linear-optimization task, 2026-10-11): the Conservative demo run and its trade log are bit-identical.
    p, b = engine.make_demo()
    p, b = engine.validate_inputs(p, b)
    s = engine.attach_signals(p)
    start, end = pd.Timestamp("2003-01-31"), pd.Timestamp("2025-12-31")
    tg, _ = engine.formation_targets(s, ["Conservative"], start=start, last=end)
    log = []
    run = engine.backtest(p, b, tg["Conservative"], start, end, 30, trade_log=log)
    assert frame_hash(run) == "a1312701744f461f713bcf48e90ea96d71c3cff1d3bee24ebe76974523f5219e"
    assert frame_hash(pd.concat(log, ignore_index=True)) == "c0dbdcc66cd9f44b20d22db86c459bb5623f28715b350fe79cd9979aed2aa8ba"
