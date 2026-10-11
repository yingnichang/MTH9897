"""Fixture tests of research.report statistics. Run from Final/:  python -m pytest tests -q"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research import report  # noqa: E402

DATES = pd.date_range("2000-01-31", periods=6, freq="ME")
R = pd.Series([0.10, -0.05, 0.02, 0.00, 0.08, -0.10], index=DATES)
RF = pd.Series([0.01, 0.01, 0.00, 0.00, 0.02, 0.00], index=DATES)


def test_statistics_on_hand_computed_series():
    s = report.statistics(R, RF)
    growth = 1.10 * 0.95 * 1.02 * 1.00 * 1.08 * 0.90
    mean = (0.10 - 0.05 + 0.02 + 0.00 + 0.08 - 0.10) / 6
    sd = math.sqrt(sum((x - mean) ** 2 for x in R) / 5)
    ex = [r - f for r, f in zip(R, RF)]
    ex_mean = sum(ex) / 6
    ex_sd = math.sqrt(sum((x - ex_mean) ** 2 for x in ex) / 5)
    assert s["months"] == 6
    assert np.isclose(s["compounded"], growth ** (12 / 6) - 1)
    assert np.isclose(s["arithmetic"], 12 * mean)
    assert np.isclose(s["volatility"], math.sqrt(12) * sd)
    assert np.isclose(s["sharpe_paper"], 12 * mean / (math.sqrt(12) * sd))
    assert np.isclose(s["sharpe_excess"], 12 * ex_mean / (math.sqrt(12) * ex_sd))
    # Wealth path from 1: 1.10, 1.045, 1.0659, 1.0659, 1.151172, 1.0360548. Falls from the running
    # peak: 1.10 -> 1.045 (-5%) and 1.151172 -> 1.0360548 (-10%); the maximum drawdown is the latter.
    assert np.isclose(s["max_drawdown"], 1.0360548 / 1.151172 - 1)
    assert np.isclose(report.max_drawdown(pd.Series([-0.2, 0.1])), -0.2)      # a first-month loss counts


def test_statistics_require_aligned_rf():
    with pytest.raises(ValueError, match="rf"):
        report.statistics(R, RF.iloc[1:])


def test_turnover_excludes_initial_investment():
    run = pd.DataFrame({"traded_notional": [1.0, 0, 0, 0.6, 0, 0, 0.4, 0, 0],
                        "gross": 0.0, "net": 0.0, "cost_fraction": 0.0},
                       index=pd.date_range("2000-01-31", periods=9, freq="ME"))
    t = report.quarterly_turnover(run)
    assert t["rebalances"] == 2 and np.isclose(t["one_way_per_quarter"], (0.3 + 0.2) / 2)
    # A rebalance month with no trades still counts as a rebalance.
    run.loc[run.index[6], "traded_notional"] = 0.0
    assert np.isclose(report.quarterly_turnover(run)["one_way_per_quarter"], 0.15)


def test_cost_reconciliation_matches_engine_haircut():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2000-01-31", periods=24, freq="ME")
    gross = pd.Series(rng.normal(0.01, 0.04, 24), index=idx)
    traded = pd.Series(np.where(idx.month.isin([1, 4, 7, 10]), 0.6, 0.0), index=idx)
    traded.iloc[0] = 1.0
    c = 0.003
    net = (1 - c * traded) * (1 + gross) - 1
    run = pd.DataFrame({"gross": gross, "net": net, "traded_notional": traded, "cost_fraction": c * traded})
    rec = report.cost_reconciliation(run, bps=30)
    assert np.isclose(rec["implied_annual_cost"], 0.3 * 2 * 4 * c)
    assert np.isclose(rec["engine_arithmetic_drag"], 12 * (gross - net).mean())


# --- Critical tests (RS-006): periods, net series, break-even ---------------------------------

def test_period_slicing_counts():
    idx = pd.date_range("1929-01-31", "2024-12-31", freq="ME")
    s = pd.Series(1.0, index=idx)
    counts = {name: len(report.period_slice(s, name)) for name in report.PERIODS}
    assert counts == {"1929–1962": 408, "1963–1989": 324, "1990–2016": 324, "2017–2024": 96, "1990–2024": 420}
    assert len(idx) == 1152
    with pytest.raises(ValueError, match="does not cover"):
        report.period_slice(s.loc[:"2016-12-31"], "2017–2024")


def test_net_series_matches_engine_haircut():
    from research import checks, engine
    p, bench, targets, start, end = checks.calendar_case("ok")
    p = p.copy()
    p["ret_hold"] = np.linspace(-0.02, 0.03, len(p))
    p["ret_total"] = p["ret_hold"]
    targets[pd.Timestamp("2020-03-31")] = pd.Series({1: 0.8, 2: 0.2})
    g = engine.backtest(p, bench, targets, start, end, 0)
    for bps in (10, 30, 250):
        n = engine.backtest(p, bench, targets, start, end, bps)
        assert n["traded_notional"].equals(g["traded_notional"])          # trades do not depend on costs
        assert np.allclose(report.net_from_gross(g, bps), n["net"], rtol=0, atol=1e-15)


def test_breakeven_bisection_hits_zero():
    # Closed form: f(c) = a - b c is zero at c* = a / b (in bps).
    a, b = 0.03, 0.0001
    be = report.breakeven(lambda c: a - b * c)
    assert be["status"] == "found" and abs(be["bps"] - a / b) <= 0.5
    # Already non-positive at zero cost: reported, no search.
    assert report.breakeven(lambda c: -0.01 - b * c)["status"] == "<= 0"
    # Still positive at the top of the bracket.
    assert report.breakeven(lambda c: 1.0 - 1e-6 * c)["status"] == "> 2000"
    # On a net series: arithmetic excess over a flat benchmark with trades of 0.8 each quarter.
    idx = pd.date_range("2000-01-31", periods=48, freq="ME")
    run = pd.DataFrame({"gross": 0.012, "traded_notional": np.where(idx.month.isin([1, 4, 7, 10]), 0.8, 0.0)}, index=idx)
    mkt = pd.Series(0.01, index=idx)
    f = lambda c: 12 * (report.net_from_gross(run, c) - mkt).mean()
    be = report.breakeven(f)
    exact = 0.002 / (1.012 * 0.8 / 3) * 10_000      # monthly excess 0.002 - c x 1.012 x mean(T), mean(T) = 0.8/3
    assert abs(be["bps"] - exact) <= 0.5 and f(be["bps"] - 0.5) > 0 > f(be["bps"] + 0.5)


def test_block_bootstrap_mean_se_iid():
    rng = np.random.default_rng(3)
    idx = pd.date_range("1990-01-31", periods=420, freq="ME")
    r = pd.Series(rng.normal(0.01, 0.05, 420), index=idx)
    rf = pd.Series(0.002, index=idx)
    b = report.bootstrap_statistics(r, rf, block=12, reps=5000, seed=9897)
    se_mean_annual = 12 * r.std(ddof=1) / np.sqrt(len(r))
    assert abs(b["arithmetic_se"] / se_mean_annual - 1) < 0.10
    assert b["arithmetic_ci95_low"] < 12 * r.mean() < b["arithmetic_ci95_high"]
    for k in ["compounded", "volatility", "sharpe_paper", "sharpe_excess"]:
        assert b[f"{k}_se"] > 0 and b[f"{k}_ci95_low"] < b[f"{k}_ci95_high"], k


def test_block_bootstrap_deterministic_with_seed():
    idx = pd.date_range("2017-01-31", periods=96, freq="ME")
    r = pd.Series(np.sin(np.arange(96)) / 20, index=idx)
    rf = pd.Series(0.001, index=idx)
    a = report.bootstrap_statistics(r, rf, reps=500, seed=1)
    assert a == report.bootstrap_statistics(r, rf, reps=500, seed=1)
    assert a != report.bootstrap_statistics(r, rf, reps=500, seed=2)
    # Blocks wrap nothing: every resampled index stays inside the series.
    idx_draw = report.block_indices(96, block=12, reps=50, seed=1)
    assert idx_draw.shape == (50, 96) and idx_draw.min() >= 0 and idx_draw.max() <= 95
