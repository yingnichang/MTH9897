"""Fixture tests of research.longshort (overlapping-cohort long/short with a trade ledger)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research import longshort as ls  # noqa: E402

F0 = pd.Timestamp("1999-12-31")
MONTHS = pd.date_range("2000-01-31", periods=8, freq="ME")


def flat_returns(permnos, r=0.0, months=MONTHS):
    return pd.DataFrame([(m, p, r, False) for m in months for p in permnos],
                        columns=["date", "permno", "ret_hold", "is_exit"])


def monthly_cohorts(long=(1, 2), short=(3, 4), rate=0.0):
    forms = [F0] + list(MONTHS[:-1])
    return {f: ls.Cohort(f, np.array(long), np.array(short), np.full(len(short), rate)) for f in forms}


def test_borrow_cost_by_cap_decile():
    assert np.isclose(ls.borrow_rate(1), 25e-4) and np.isclose(ls.borrow_rate(10), 2e-4)
    r = [ls.borrow_rate(d) for d in range(1, 11)]
    assert np.allclose(np.diff(r), -(23 / 9) * 1e-4)                       # linear in the decile
    # Charged per month held on the short position's value.
    rf = pd.Series(0.0, index=MONTHS)
    cohorts = {F0: ls.Cohort(F0, np.array([1]), np.array([2]), np.array([ls.borrow_rate(1)]))}
    rec, _, _ = ls.simulate(cohorts, flat_returns([1, 2]), rf, MONTHS[:2], n=2, borrow=True)
    # n = 2: the short leg is 1/2 of NAV; in month 2 it is rescaled by 1/(1 + gross), gross = -borrow of month 1.
    assert np.allclose(rec["borrow"], [0.5 * 25e-4, 0.5 / (1 - 0.5 * 25e-4) * 25e-4], rtol=0, atol=1e-15)
    rec0, _, _ = ls.simulate(cohorts, flat_returns([1, 2]), rf, MONTHS[:2], n=2, borrow=False)
    assert (rec0["borrow"] == 0).all()


def test_dollar_neutral_with_rf_collateral():
    rf = pd.Series(0.004, index=MONTHS)
    rec, ledger, _ = ls.simulate(monthly_cohorts(), flat_returns([1, 2, 3, 4]), rf, MONTHS, n=3, borrow=False)
    # Zero stock returns: the strategy earns exactly rf on its collateral.
    assert np.allclose(rec["gross"], 0.004)
    opens = ledger.loc[ledger["action"].eq("open")]
    by = opens.groupby(["cohort", "side"])["notional"].sum().unstack()
    assert np.allclose(by["long"], 1 / 3) and np.allclose(by["short"], -1 / 3)   # long 1/n, short 1/n at formation
    full = rec.loc[rec["live_cohorts"].eq(3)]
    # Dollar-neutral; older cohorts shrink relative to NAV as the collateral earns rf, so gross exposure is just under 1.
    assert np.allclose(full["long_exposure"], full["short_exposure"]) and full["long_exposure"].between(0.99, 1.0).all()


def test_cohort_overlap_and_unwind():
    rng = np.random.default_rng(0)
    ret = flat_returns([1, 2, 3, 4]).assign(ret_hold=lambda d: rng.normal(0, 0.03, len(d)))
    rec, ledger, _ = ls.simulate(monthly_cohorts(), ret, pd.Series(0.0, index=MONTHS), MONTHS, n=3, borrow=False)
    assert rec["live_cohorts"].max() == 3 and rec["live_cohorts"].tolist()[:4] == [1, 2, 3, 3]
    for cohort, g in ledger.groupby("cohort"):
        opened = g.loc[g["action"].eq("open"), "date"].unique()
        closed = g.loc[g["action"].eq("close"), "date"].unique()
        assert len(opened) == 1 and opened[0] == cohort + pd.offsets.MonthEnd(1)       # traded at the formation close
        if len(closed):
            assert closed[0] == cohort + pd.offsets.MonthEnd(4)                        # unwound after 3 months held


def test_ledger_reconciles_turnover_and_pnl():
    rng = np.random.default_rng(1)
    ret = flat_returns([1, 2, 3, 4]).assign(ret_hold=lambda d: rng.normal(0.01, 0.05, len(d)))
    rf = pd.Series(0.002, index=MONTHS)
    cohorts = monthly_cohorts(rate=ls.borrow_rate(4))
    rec, ledger, pnl = ls.simulate(cohorts, ret, rf, MONTHS, n=3, borrow=True)
    traded = ledger.loc[ledger["action"].isin(["open", "close"])].groupby("date")["notional"].apply(lambda x: x.abs().sum())
    assert np.allclose(traded.reindex(rec.index, fill_value=0), rec["traded"], atol=1e-12)
    by_month = pnl.groupby("date")["pnl"].sum()
    assert np.allclose(by_month.reindex(rec.index), rec["long_pnl"] - rec["short_pnl"], atol=1e-12)
    assert np.allclose(rec["gross"], rec["long_pnl"] - rec["short_pnl"] + rf - rec["borrow"], atol=1e-12)
    net = ls.net_return(rec, 10)
    assert np.allclose(net, (1 - 10e-4 * rec["traded"]) * (1 + rec["gross"]) - 1)
    assert np.allclose(ledger["cost_10bps"], 10e-4 * ledger["notional"].abs().where(ledger["action"].ne("exit"), 0))


def test_exit_settles_once():
    m = MONTHS[:4]
    ret = flat_returns([1, 2], months=m)
    ret.loc[ret["date"].eq(m[1]) & ret["permno"].eq(1), ["ret_hold", "is_exit"]] = [-0.5, True]
    ret = ret.loc[~(ret["date"].gt(m[1]) & ret["permno"].eq(1))]               # no rows after the exit month
    cohorts = {F0: ls.Cohort(F0, np.array([1]), np.array([2]), np.array([0.0]))}
    rec, ledger, pnl = ls.simulate(cohorts, ret, pd.Series(0.0, index=m), m, n=3, borrow=False)
    p1 = pnl.loc[pnl["permno"].eq(1)]
    assert len(p1) == 2 and np.isclose(p1["pnl"].sum(), -0.5 / 3)           # earned 0 then the -50% exit return once
    ex = ledger.loc[ledger["permno"].eq(1)]
    assert ex["action"].tolist() == ["open", "exit"] and ex.loc[ex["action"].eq("exit"), "cost_10bps"].iloc[0] == 0
    assert not ((ledger["permno"] == 1) & ledger["action"].eq("close")).any()   # not closed again at the unwind
    with pytest.raises(ValueError, match="Missing return"):
        ls.simulate(cohorts, ret.loc[ret["permno"].ne(2) | ret["date"].le(m[0])], pd.Series(0.0, index=m), m, n=3, borrow=False)


def test_ruin_stops_accounting():
    # n = 1: the short name triples; the month's loss exceeds NAV, so the strategy is ruined and stops there.
    ret = flat_returns([1, 2])
    ret.loc[ret["date"].eq(MONTHS[1]) & ret["permno"].eq(2), "ret_hold"] = 2.0
    rec, ledger, _ = ls.simulate(monthly_cohorts(long=(1,), short=(2,)), ret, pd.Series(0.0, index=MONTHS), MONTHS,
                                 n=1, borrow=False)
    assert rec.attrs["ruined_at"] == MONTHS[1] and len(rec) == 2 and rec["gross"].iloc[-1] <= -1
    assert ledger["date"].max() <= MONTHS[1]
    ok, _, _ = ls.simulate(monthly_cohorts(long=(1,), short=(2,)), flat_returns([1, 2]), pd.Series(0.0, index=MONTHS),
                           MONTHS, n=1, borrow=False)
    assert ok.attrs["ruined_at"] is None and len(ok) == len(MONTHS)


def test_monthly_reweighting_resets_each_cohort_to_one_over_n():
    rng = np.random.default_rng(2)
    ret = flat_returns([1, 2, 3, 4]).assign(ret_hold=lambda d: rng.normal(0.01, 0.08, len(d)))
    rf = pd.Series(0.001, index=MONTHS)
    rec, ledger, pnl = ls.simulate(monthly_cohorts(), ret, rf, MONTHS, n=3, borrow=False, rebalance="monthly")
    full = rec.loc[rec["live_cohorts"].eq(3)]
    assert np.allclose(full["long_exposure"], 1.0) and np.allclose(full["short_exposure"], 1.0)  # 1/n per leg per cohort
    assert ledger["action"].eq("rebalance").any()
    traded = ledger.loc[ledger["action"].isin(["open", "close", "rebalance"])].groupby("date")["notional"].apply(lambda x: x.abs().sum())
    assert np.allclose(traded.reindex(rec.index, fill_value=0), rec["traded"], atol=1e-12)
    assert np.allclose(pnl.groupby("date")["pnl"].sum(), rec["long_pnl"] - rec["short_pnl"], atol=1e-12)
    # The month's long/short P&L is then the average of the live cohorts' equal-weight leg returns, divided by n.
    m = MONTHS[3]
    r = ret.loc[ret["date"].eq(m)].set_index("permno")["ret_hold"]
    assert np.isclose(rec.loc[m, "long_pnl"] - rec.loc[m, "short_pnl"], r[[1, 2]].mean() - r[[3, 4]].mean())
    with pytest.raises(ValueError, match="rebalance"):
        ls.simulate(monthly_cohorts(), ret, rf, MONTHS, n=3, rebalance="weekly")


def test_contributions_reconcile_unequal_exposure_nonzero_rf():
    # Drift makes the legs unequal (the long name gains 20% in month 1); rf and borrow are nonzero.
    m = MONTHS[:3]
    f = m[0] - pd.offsets.MonthEnd(1)
    cohorts = {f: ls.Cohort(f, np.array([1]), np.array([2]), np.array([ls.borrow_rate(3)]))}
    ret = flat_returns([1, 2], months=m)
    ret.loc[ret["date"].eq(m[0]) & ret["permno"].eq(1), "ret_hold"] = 0.2
    ret.loc[ret["date"].eq(m[1]) & ret["permno"].eq(2), "ret_hold"] = 0.05
    rec, _, _ = ls.simulate(cohorts, ret, pd.Series(0.01, index=m), m, n=2, borrow=True)
    assert (rec["long_exposure"] - rec["short_exposure"]).abs().max() > 0.05      # the fixture really is unequal
    for bps in (0, 10, 30):
        s = ls.contributions(rec, bps)
        assert np.allclose(s["long"] + s["short"] + s["collateral_rf"], rec["gross"] - bps * 1e-4 * rec["traded"],
                           rtol=0, atol=1e-15)
        assert np.allclose(s["collateral_rf"], rec["rf"] * (1 + rec["long_exposure"] - rec["short_exposure"]), rtol=0, atol=1e-15)
        # The multiplicative cost haircut's interaction with the gross return is its own column.
        assert np.allclose(s["additive_total"] + s["cost_interaction"], s["net"], rtol=0, atol=1e-15)
        assert np.allclose(s["cost_interaction"], -bps * 1e-4 * rec["traded"] * rec["gross"], rtol=0, atol=1e-15)
    assert np.allclose(ls.contributions(rec, 0)["additive_total"], ls.net_return(rec, 0), rtol=0, atol=1e-15)


def test_capacity_invariant_to_cohort_splitting():
    d = MONTHS[0]
    dv = pd.DataFrame({"date": [d, d, d], "permno": [1, 2, 3], "dollar_volume": [1e6, 2e6, 0.0]})
    defl = pd.Series(0.5, index=[d])
    one = pd.DataFrame({"date": [d] * 4, "permno": [1, 2, 1, 3], "side": ["long", "long", "short", "short"],
                        "value": [0.03, 0.01, 0.02, 0.01]})
    # The same book split into three identical cohorts (three fragments per security and side).
    split = pd.DataFrame([(r.date, r.permno, r.side, r.value / 3) for r in one.itertuples() for _ in range(3)],
                         columns=one.columns)
    a, b = ls.participation_per_dollar(one, dv, defl), ls.participation_per_dollar(split, dv, defl)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) == 4                                     # one row per (date, security, side): no netting across sides
    assert int(a["covered"].sum()) == 3                    # zero dollar volume is excluded and counted, not dropped
    x = a.loc[a["permno"].eq(1) & a["side"].eq("long"), "per_dollar_aum"].iloc[0]
    assert np.isclose(x, 0.03 * 0.5 / 1e6)
    assert ls.capacity_aum(a.loc[a["covered"], "per_dollar_aum"]) == ls.capacity_aum(b.loc[b["covered"], "per_dollar_aum"])
    assert np.isclose(ls.capacity_aum(pd.Series([2e-9] * 5)), 0.10 / 2e-9)


def test_hit_rate_ignores_data_after_window():
    forms = pd.date_range("1999-11-30", periods=8, freq="ME")
    rng = np.random.default_rng(5)
    u = pd.DataFrame([(f, p, dec) for f in forms for p, dec in [(1, 10), (2, 10), (3, 1), (4, 1), (5, 5)]],
                     columns=["date", "permno", "dec"])
    u["adj_3"] = rng.normal(0, 0.05, len(u))
    first, last = pd.Timestamp("2000-01-31"), pd.Timestamp("2000-05-31")
    h = ls.stock_hit_rates(u, 3, first, last)
    # Cohorts held entirely inside the window: formed 1999-12 (held 2000-01..03) through 2000-02 (held 03..05).
    inside = u["date"].between(pd.Timestamp("1999-12-31"), pd.Timestamp("2000-02-29")) & u["dec"].isin([1, 10])
    w = u.loc[inside]
    win = np.where(w["dec"].eq(10), w["adj_3"] > 0, w["adj_3"] < 0)
    assert h["stock_names"] == 12 and np.isclose(h["stock_hit_rate"], win.mean())
    assert np.isclose(h["stock_hit_rate_long"], (w.loc[w["dec"].eq(10), "adj_3"] > 0).mean())
    assert np.isclose(h["stock_hit_rate_short"], (w.loc[w["dec"].eq(1), "adj_3"] < 0).mean())
    # Changing data for cohorts whose horizon ends after the window (or that start before it) changes nothing.
    v = u.copy()
    outside = ~v["date"].between(pd.Timestamp("1999-12-31"), pd.Timestamp("2000-02-29"))
    v.loc[outside & v["dec"].eq(10), "adj_3"] = 1.0
    v.loc[outside & v["dec"].eq(1), "adj_3"] = -1.0
    assert ls.stock_hit_rates(v, 3, first, last) == h
