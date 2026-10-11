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
