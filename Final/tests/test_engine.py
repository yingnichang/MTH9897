"""Fixture tests of the research engine (selection, holdings rule, backtest). Run from Final/:  python -m pytest tests -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research import checks, engine  # noqa: E402

FORMATION = pd.Timestamp("2019-12-31")


def snapshot(n, **cols):
    """n universe candidates, permno 1..n; vol36 rises and mktcap falls with permno by default."""
    base = {"date": FORMATION, "permno": np.arange(1, n + 1), "eligible": True, "hist36": True,
            "is_exit": False, "mktcap": np.arange(n, 0, -1) * 10.0, "vol36": np.arange(1, n + 1) / 100,
            "momentum": np.linspace(0.3, 0.0, n), "npy": np.linspace(0.05, 0.0, n)}
    base.update(cols)
    return pd.DataFrame(base)


# --- Universe and selection -------------------------------------------------------------------

def test_history_screen_precedes_cap_cut():
    snap = snapshot(4, hist36=[False, True, True, True])        # permno 1 is the largest
    uni = engine.select_universe(snap, n_universe=2)
    assert uni["permno"].tolist() == [2, 3]                      # 3 enters; a cap-first cut would keep 1, 2
    _, counts = engine.choose_weights(snap, "Universe equal weight", n_universe=2, n_hold=1)
    assert counts["history_eligible_n"] == 3 and counts["universe_n"] == 2 and counts["eligible_n"] == 4


def test_vol_partition_precedes_missing_signal_drop():
    # 10 universe names; permno = vol rank. Two low-vol members lack a signal (2: NPY, 3: momentum).
    snap = snapshot(10)
    snap.loc[snap["permno"].eq(2), "npy"] = np.nan
    snap.loc[snap["permno"].eq(3), "momentum"] = np.nan
    w, c = engine.choose_weights(snap, "Conservative", n_universe=10, n_hold=3)
    assert c["low_vol_pool_n"] == 5 and c["signal_complete_n"] == 3
    assert c["pool_missing_npy_n"] == 1 and c["pool_missing_momentum_n"] == 1
    assert sorted(w.index) == [1, 4, 5] and 6 not in w.index
    # The old order (drop incomplete names, then halve) would pull the 6th-lowest-vol name into the pool.
    complete = snap.dropna(subset=["momentum", "npy"]).sort_values("vol36")
    assert 6 in complete.head(len(complete) // 2)["permno"].tolist()


def test_small_universe_uses_all_history_eligible():
    snap = snapshot(25)
    w, c = engine.choose_weights(snap, "Conservative", n_universe=1000, n_hold=3)
    assert c["universe_n"] == c["history_eligible_n"] == 25
    assert c["low_vol_pool_n"] == 12 and c["selected_n"] == 3
    w10, c10 = engine.choose_weights(snap, "Conservative", n_universe=1000, n_hold="pct10")
    assert len(w10) == c10["selected_n"] == 2                    # floor(0.1 * 25)
    assert engine.resolve_n_hold("pct10", 1000) == 100 and engine.resolve_n_hold(100, 25) == 100
    with pytest.raises(ValueError, match="n_hold"):
        engine.resolve_n_hold("pct20", 1000)


def test_raises_when_pool_has_too_few_complete():
    snap = snapshot(10)
    snap.loc[snap["permno"].isin([1, 2]), "npy"] = np.nan        # pool 1..5 keeps 3 complete members
    with pytest.raises(ValueError, match="complete"):
        engine.choose_weights(snap, "Conservative", n_universe=10, n_hold=4)
    snap.loc[snap["permno"].eq(9), "vol36"] = np.nan
    with pytest.raises(ValueError, match="vol36"):
        engine.choose_weights(snap, "Conservative", n_universe=10, n_hold=1)


def test_score_ties_broken_by_permno_and_counted():
    # Pool = permnos 1..4 (universe 8). Ranks: 4 is best on both; 2 and 3 tie at a mean rank of 2.5.
    snap = snapshot(8)
    mom = {1: 0.10, 2: 0.30, 3: 0.20, 4: 0.40}
    npy = {1: 0.01, 2: 0.02, 3: 0.03, 4: 0.04}
    snap.loc[snap["permno"].le(4), "momentum"] = snap["permno"].map(mom)
    snap.loc[snap["permno"].le(4), "npy"] = snap["permno"].map(npy)
    w, c = engine.choose_weights(snap, "Conservative", n_universe=8, n_hold=2)
    assert sorted(w.index) == [2, 4]                             # 2 beats 3 on permno
    assert c["score_ties_at_cut"] == 1
    assert np.allclose(w, 0.5)
    w1, c1 = engine.choose_weights(snap, "Conservative", n_universe=8, n_hold=1)
    assert w1.index.tolist() == [4] and c1["score_ties_at_cut"] == 0


def test_strategy_set_and_counts_shape():
    snap = snapshot(40)
    for name in engine.STRATEGIES:
        w, c = engine.choose_weights(snap, name, n_universe=30, n_hold=5)
        assert np.isclose(w.sum(), 1) and w.gt(0).all(), name
        assert set(engine.COUNT_FIELDS) <= set(c), name
    w, _ = engine.choose_weights(snap, "Low volatility only", n_universe=30, n_hold=5)
    assert sorted(w.index) == [1, 2, 3, 4, 5]
    w, _ = engine.choose_weights(snap, "Universe cap weight", n_universe=30, n_hold=5)
    assert len(w) == 30 and w.idxmax() == 1


# --- Backtest ---------------------------------------------------------------------------------

toy_panel, flat_bench = checks.toy_panel, checks.flat_bench


def test_backtest_drift_cost_exit_hand_example():
    checks.check_drift_cost_exit()


def test_backtest_stale_carry():
    td = pd.date_range("2020-01-31", periods=5, freq="ME")
    # Stock 2 has no CRSP return in Mar and Apr (stale carry), then CRSP's resumption return in May.
    # The quarter-end rebalance at the end of March falls inside the gap.
    toy = toy_panel([(td[0], 1, .10, "crsp", False), (td[0], 2, 0., "crsp", False),
                     (td[1], 1, 0., "crsp", False), (td[1], 2, 0., "crsp", False),
                     (td[2], 1, 0., "crsp", False), (td[2], 2, 0., "stale_carry", False),
                     (td[3], 1, .20, "crsp", False), (td[3], 2, 0., "stale_carry", False),
                     (td[4], 1, 0., "crsp", False), (td[4], 2, .30, "crsp", False)])
    tw = {pd.Timestamp("2019-12-31"): pd.Series({1: .5, 2: .5}),
          pd.Timestamp("2020-03-31"): pd.Series({1: .25, 2: .75})}
    run = engine.backtest(toy, flat_bench(td), tw, td[0], td[-1], cost_bps=0)
    w2 = .5 / 1.05                                                    # drifted, then held at the stale value
    assert np.isclose(run.gross.iloc[2], 0.0)
    assert np.isclose(run.traded_notional.iloc[3], abs(.25 - (1 - w2)) + abs(.75 - w2))
    assert np.isclose(run.gross.iloc[3], .25 * .20)                   # stale position earns 0 in April
    assert np.isclose(run.gross.iloc[4], (.75 / 1.05) * .30)          # resumption return in May
    assert run.stale_held_n.tolist() == [0, 0, 1, 1, 0]
    assert np.isclose(run.stale_weight.iloc[2], w2) and np.isclose(run.stale_weight.iloc[3], .75)
    assert run.stale_carry_n.tolist() == [0, 0, 1, 1, 0] and run.price_ratio_n.sum() == 0


def test_backtest_counts_price_ratio_as_stale():
    td = pd.date_range("2020-01-31", periods=2, freq="ME")
    toy = toy_panel([(td[0], 1, .02, "price_ratio", False), (td[0], 2, 0., "crsp", False),
                     (td[1], 1, .01, "crsp", False), (td[1], 2, 0., "crsp", False)])
    run = engine.backtest(toy, flat_bench(td), {pd.Timestamp("2019-12-31"): pd.Series({1: .5, 2: .5})},
                          td[0], td[-1])
    assert np.isclose(run.gross.iloc[0], .01)
    assert run.stale_held_n.tolist() == [1, 0] and run.price_ratio_n.tolist() == [1, 0]
    assert np.isclose(run.price_ratio_weight.iloc[0], .5) and run.stale_carry_n.sum() == 0


def test_backtest_rejects_nan_ret_hold():
    checks.check_missing_ret_hold_rejected()
    td = pd.date_range("2020-01-31", periods=2, freq="ME")
    tw = {pd.Timestamp("2019-12-31"): pd.Series({1: .5, 2: .5})}
    missing_row = toy_panel([(td[0], 1, 0., "crsp", False), (td[0], 2, 0., "crsp", False),
                             (td[1], 1, 0., "crsp", False)])
    with pytest.raises(ValueError, match="Missing held-stock"):
        engine.backtest(missing_row, flat_bench(td), tw, td[0], td[-1])


# --- Calendar and target validation (NB-002) --------------------------------------------------

def test_rejects_benchmark_gap_inside_window():
    checks.assert_calendar_failure("benchmark_gap")


def test_rejects_late_benchmark_start():
    # NB-002 counterexample: a January start with a benchmark that begins in February must raise.
    checks.assert_calendar_failure("late_benchmark_start")


def test_rejects_missing_first_target():
    checks.assert_calendar_failure("missing_first_target")


def test_rejects_missing_rebalance_target():
    checks.assert_calendar_failure("missing_rebalance_target")


def test_rejects_missing_panel_month_while_holding():
    checks.assert_calendar_failure("missing_panel_month")


def test_rejects_end_before_start():
    with pytest.raises(ValueError, match="end"):
        engine.backtest(*checks.calendar_case("ok")[:3], pd.Timestamp("2020-01-31"), pd.Timestamp("2019-11-30"))


def test_calendar_fixture_passes_when_complete():
    p, bench, targets, start, end = checks.calendar_case("ok")
    run = engine.backtest(p, bench, targets, start, end)
    assert run.index.equals(pd.date_range(start, end, freq="ME")) and run["all_cash"].sum() == 0


def test_flags_all_cash_months():
    checks.check_all_cash_flagged()


def test_second_rebalance_after_drift_reconciles():
    checks.check_second_rebalance_after_drift()


def test_every_section7_check_passes():
    results = checks.run_all()
    assert len(results) == len(checks.ALL_CHECKS) and all(isinstance(r, str) for r in results)


# --- Inputs and demo --------------------------------------------------------------------------

def test_make_demo_has_history_and_holding_columns():
    panel, bench = engine.make_demo(n_stocks=30)
    p, b = engine.validate_inputs(panel, bench)
    first = p.loc[p["permno"].eq(p["permno"].iloc[0])].reset_index(drop=True)
    assert not first.loc[:34, "hist36"].any() and first.loc[35:, "hist36"].all()
    assert (p["ret_hold"] == p["ret_total"]).all() and p["ret_hold_source"].eq("crsp").all()


def test_validate_inputs_requires_holding_return_contract():
    panel, bench = engine.make_demo(n_stocks=5)
    with pytest.raises(ValueError, match="ret_hold"):
        engine.validate_inputs(panel.drop(columns="ret_hold"), bench)
    bad = panel.copy()
    bad.loc[bad.index[0], "ret_hold_source"] = "filled"
    with pytest.raises(ValueError, match="ret_hold_source"):
        engine.validate_inputs(bad, bench)
    bad = panel.copy()
    bad.loc[bad.index[0], "ret_hold"] = np.nan
    with pytest.raises(ValueError, match="no_prior_row"):
        engine.validate_inputs(bad, bench)


def test_attach_signals_one_to_one():
    from research import checks
    panel = checks.signal_fixture()
    out = engine.attach_signals(panel)
    assert len(out) == len(panel) and list(out.columns[:len(panel.columns)]) == list(panel.columns)
    assert set(engine.SIGNAL_COLUMNS) <= set(out.columns)
    pd.testing.assert_frame_equal(out[panel.columns], panel)
    dup = pd.concat([panel, panel.iloc[[5]]], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate"):
        engine.attach_signals(dup)
    with pytest.raises(ValueError, match="already has signal columns"):
        engine.attach_signals(out)


def test_signals_unchanged_when_future_inputs_change():
    from research import checks
    checks.check_future_isolation()
    checks.check_momentum_timing()
    checks.check_gap_breaks_window()

    # The isolation check is not vacuous: a signal that peeks one month ahead fails it.
    def leaky(p):
        s = engine.build_signals(p)
        s["vol36"] = s.groupby("permno")["vol36"].shift(-1)
        return s
    with pytest.raises(AssertionError):
        checks.check_future_isolation(signal_fn=leaky)


def test_formation_targets_returns_targets_and_counts():
    panel, bench = engine.make_demo(n_stocks=60)
    sig = engine.attach_signals(panel)
    targets, counts = engine.formation_targets(sig, ["Conservative"], start=pd.Timestamp("2003-01-31"),
                                               n_universe=50, n_hold=5)
    dates = sorted(targets["Conservative"])
    assert dates[0] == pd.Timestamp("2002-12-31") and all(d.month in (3, 6, 9, 12) for d in dates)
    assert len(counts) == len(dates) and counts["selected_n"].eq(5).all()
    assert counts["low_vol_pool_n"].eq(25).all()
