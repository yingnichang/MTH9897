"""Fixture-based accounting and timing checks shared by the notebook (Section 7) and tests/test_engine.py.

Each check builds its own small synthetic input, runs the real engine or pipeline code, and raises
AssertionError on failure. It returns a one-line description of what passed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import engine

SIGNAL_INPUTS = ["ret_total", "ret_price", "div_cash_adj", "price_adj", "shares_adj"]


def signal_fixture(n_months: int = 72, seed: int = 1) -> pd.DataFrame:
    """Two synthetic securities with returns, quarterly dividends, prices and changing share counts."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2001-01-31", periods=n_months, freq="ME")
    frames = []
    for permno in (1, 2):
        r = rng.normal(0.01, 0.05, n_months)
        div_rate = np.where(np.arange(n_months) % 3 == 2, 0.006, 0.0)
        rp = r - div_rate
        price = 30 * np.cumprod(1 + rp)
        frames.append(pd.DataFrame({
            "date": dates, "permno": permno, "ret_total": r, "ret_price": rp, "price_adj": price,
            "div_cash_adj": div_rate * np.r_[30, price[:-1]],
            "shares_adj": 1e6 * np.cumprod(1 + rng.normal(0, 0.01, n_months))}))
    return pd.concat(frames, ignore_index=True)


def check_future_isolation(signal_fn=engine.build_signals, cut_month: int = 47) -> str:
    """Changing returns, dividends, prices and shares after a cut leaves every signal up to the cut unchanged."""
    p = signal_fixture()
    cut = p["date"].unique()[cut_month]
    before = signal_fn(p).set_index(["permno", "date"])[engine.SIGNAL_COLUMNS]
    q = p.copy()
    later = q["date"].gt(cut)
    q.loc[later, ["ret_total", "ret_price"]] = 0.70
    q.loc[later, "div_cash_adj"] *= 5
    q.loc[later, ["price_adj", "shares_adj"]] *= 3
    after = signal_fn(q).set_index(["permno", "date"])[engine.SIGNAL_COLUMNS]
    keep = before.index.get_level_values("date") <= cut
    assert before[keep].notna().any().all(), "fixture too short: some signal is never defined before the cut"
    pd.testing.assert_frame_equal(before[keep], after[keep])
    return "signals up to a cut date do not change when later returns, dividends, prices or shares change"


def check_momentum_timing(position: int = 45) -> str:
    """Momentum at formation month t compounds exactly the eleven price returns t-11..t-1."""
    p = signal_fixture()
    one = p.loc[p["permno"].eq(1)].reset_index(drop=True)
    sig = engine.build_signals(one)
    expected = np.prod(1 + one["ret_price"].iloc[position - 11:position]) - 1
    assert np.isclose(sig["momentum"].iloc[position], expected), "momentum window misaligned"
    return "momentum uses the eleven monthly price returns before the formation month"


def check_gap_breaks_window(gap_month: int = 20) -> str:
    """A missing month invalidates every 36-month volatility window that spans it."""
    p = signal_fixture()
    one = p.loc[p["permno"].eq(1)].reset_index(drop=True)
    dates = one["date"]
    sig = engine.build_signals(one.drop(index=gap_month)).set_index("date")
    spanning = dates[(dates > dates[gap_month]) & (dates < dates[gap_month] + pd.offsets.MonthEnd(36))]
    assert sig.loc[sig.index.isin(spanning), "vol36"].isna().all(), "a window spanning a gap was computed"
    assert sig.loc[dates[gap_month] + pd.offsets.MonthEnd(36):, "vol36"].notna().any()
    return "a missing month breaks every 36-month volatility window that contains it"


# --- Backtest accounting ----------------------------------------------------------------------

def toy_panel(rows) -> pd.DataFrame:
    """rows: (date, permno, ret_hold, source, is_exit); ret_total = ret_hold where the source is crsp."""
    p = pd.DataFrame(rows, columns=["date", "permno", "ret_hold", "ret_hold_source", "is_exit"])
    p["date"] = pd.to_datetime(p["date"])
    p["ret_total"] = p["ret_hold"].where(p["ret_hold_source"].eq("crsp"))
    return p


def flat_bench(dates, rf: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame({"rf": rf, "market_ret": 0.0}, index=pd.DatetimeIndex(dates))


def check_drift_cost_exit() -> str:
    """Hand example: drift, a 10 bps charge on the initial purchase, and a terminal exit to cash."""
    td = pd.date_range("2020-01-31", periods=3, freq="ME")
    toy = toy_panel([(td[0], 1, .10, "crsp", False), (td[0], 2, 0., "crsp", False),
                     (td[1], 1, 0., "crsp", False), (td[1], 2, .20, "crsp", True),
                     (td[2], 1, 0., "crsp", False)])
    tw = {pd.Timestamp("2019-12-31"): pd.Series({1: .5, 2: .5})}
    run = engine.backtest(toy, flat_bench(td), tw, td[0], td[-1], cost_bps=10)
    gross, net, cash = run["gross"].to_numpy(), run["net"].to_numpy(), run["cash_weight"].to_numpy()
    assert np.isclose(gross[0], .05)                        # 0.5 x 10% + 0.5 x 0%
    assert np.isclose(gross[1], (.5 / 1.05) * .20)          # stock 2 at its drifted weight earns 20%, then exits
    assert np.isclose(net[0], (1 - .001) * 1.05 - 1)        # 10 bps on one unit of traded notional
    assert np.isclose(cash[1], .60 / 1.15)                  # exit proceeds as a share of NAV
    assert run["holdings_n"].to_numpy()[-1] == 1 and np.isclose(run["traded_notional"].sum(), 1.)
    return "weights drift, costs reduce the month's NAV, and a terminal holding moves to cash"


def check_missing_ret_hold_rejected() -> str:
    """A held position whose holding return is missing stops the engine instead of earning 0."""
    td = pd.date_range("2020-01-31", periods=2, freq="ME")
    tw = {pd.Timestamp("2019-12-31"): pd.Series({1: .5, 2: .5})}
    toy = toy_panel([(td[0], 1, np.nan, "no_prior_row", False), (td[0], 2, 0., "crsp", False),
                     (td[1], 1, 0., "crsp", False), (td[1], 2, 0., "crsp", False)])
    try:
        engine.backtest(toy, flat_bench(td), tw, td[0], td[-1])
    except ValueError as exc:
        assert "Missing held-stock" in str(exc), exc
    else:
        raise AssertionError("a missing holding return was not rejected")
    return "a held position without a holding return is rejected"


def check_second_rebalance_after_drift() -> str:
    """Second rebalance: trades = target - drifted weights; notional, cost and reinvested exit cash reconcile.

    Formations 2019-12 ({1, 2} equal weight) and 2020-03 ({1, 3} equal weight), 10 bps, rf = 0.
    Jan: stock 1 +10%. Feb: stock 2 earns +20% and exits to cash. Mar: stock 1 -10%. Apr: stock 3 +5%.
    """
    td = pd.date_range("2020-01-31", periods=4, freq="ME")
    toy = toy_panel([(td[0], 1, .10, "crsp", False), (td[0], 2, 0., "crsp", False), (td[0], 3, 0., "crsp", False),
                     (td[1], 1, 0., "crsp", False), (td[1], 2, .20, "crsp", True), (td[1], 3, 0., "crsp", False),
                     (td[2], 1, -.10, "crsp", False), (td[2], 3, 0., "crsp", False),
                     (td[3], 1, 0., "crsp", False), (td[3], 3, .05, "crsp", False)])
    tw = {pd.Timestamp("2019-12-31"): pd.Series({1: .5, 2: .5}),
          pd.Timestamp("2020-03-31"): pd.Series({1: .5, 3: .5})}
    trades = []
    run = engine.backtest(toy, flat_bench(td), tw, td[0], td[-1], cost_bps=10, trade_log=trades)

    # Hand calculation of the drifted book at the end of March (fractions of NAV).
    v1, v2 = .5 * 1.10, .5 * 1.00                  # end of January
    nav_jan = v1 + v2
    cash_feb = v2 * 1.20                           # stock 2's terminal proceeds
    v1_mar = v1 * 0.90
    nav_mar = v1_mar + cash_feb
    w1_pre, cash_pre = v1_mar / nav_mar, cash_feb / nav_mar
    expected = pd.Series({1: .5 - w1_pre, 3: .5})  # stock 2 is gone; cash is spent, not traded
    second = trades[1].set_index("permno")
    assert np.allclose(second["pre_weight"].reindex([1, 3]).to_numpy(), [w1_pre, 0.0])
    assert np.isclose(second["pre_cash"].iloc[0], cash_pre)
    assert np.allclose(second["trade"].reindex(expected.index).to_numpy(), expected.to_numpy())
    notional = run["traded_notional"].to_numpy()
    assert np.isclose(notional[3], expected.abs().sum()) and np.isclose(notional[3], cash_pre)
    assert np.isclose(notional[0], 1.0) and np.isclose(run["traded_notional"].sum(), 1.0 + cash_pre)
    assert np.isclose(run["cost_fraction"].to_numpy()[3], .001 * cash_pre)
    assert np.isclose(run["gross"].to_numpy()[1], (v2 / nav_jan) * .20)
    assert np.isclose(run["cash_weight"].to_numpy()[2], cash_pre)
    # The exit cash is fully reinvested at the second rebalance: April starts with no cash.
    assert np.isclose(run["gross"].to_numpy()[3], .5 * .05)
    assert np.isclose(run["net"].to_numpy()[3], (1 - .001 * cash_pre) * 1.025 - 1)
    assert np.isclose(run["cash_weight"].to_numpy()[3], 0.0) and run["holdings_n"].to_numpy()[3] == 2
    return "a second rebalance after drift reconciles security trades, notional, cost and reinvested exit cash"


def check_all_cash_flagged() -> str:
    """Months that end fully in cash are flagged (both holdings exit in February; reinvested at March end)."""
    td = pd.date_range("2020-01-31", periods=4, freq="ME")
    rows = [(td[0], k, .01, "crsp", False) for k in (1, 2, 3, 4)]
    rows += [(td[1], 1, .01, "crsp", True), (td[1], 2, .01, "crsp", True), (td[1], 3, .01, "crsp", False),
             (td[1], 4, .01, "crsp", False)]
    rows += [(d, k, .01, "crsp", False) for d in td[2:] for k in (3, 4)]
    tw = {pd.Timestamp("2019-12-31"): pd.Series({1: .5, 2: .5}),
          pd.Timestamp("2020-03-31"): pd.Series({3: .5, 4: .5})}
    run = engine.backtest(toy_panel(rows), flat_bench(td), tw, td[0], td[-1])
    assert run["all_cash"].tolist() == [False, True, True, False], run["all_cash"].tolist()
    return "months that end fully in cash are flagged"


# --- Calendar and target failures (NB-002) ----------------------------------------------------

CALENDAR_FAILURES = {
    "benchmark_gap": "Benchmark lacks 1 month\\(s\\) in the window 2020-01-31..2020-06-30; first missing 2020-04-30",
    "late_benchmark_start": "Benchmark lacks 1 month\\(s\\) in the window 2020-01-31..2020-06-30; first missing 2020-01-31",
    "missing_first_target": "No target for the first formation 2019-12-31",
    "missing_rebalance_target": "No target for quarter-end formation 2020-03-31",
    "missing_panel_month": "No stock returns for 2020-05-31",
}


def calendar_case(name: str):
    """(panel, benchmark, targets, start, end) for a complete Jan-Jun 2020 window, broken as `name` says."""
    td = pd.date_range("2020-01-31", "2020-06-30", freq="ME")
    p = toy_panel([(d, k, .01, "crsp", False) for d in td for k in (1, 2)])
    bench = flat_bench(td)
    targets = {pd.Timestamp("2019-12-31"): pd.Series({1: .5, 2: .5}),
               pd.Timestamp("2020-03-31"): pd.Series({1: .5, 2: .5})}
    if name == "benchmark_gap":
        bench = bench.drop(pd.Timestamp("2020-04-30"))
    elif name == "late_benchmark_start":
        bench = bench.iloc[1:]
    elif name == "missing_first_target":
        del targets[pd.Timestamp("2019-12-31")]
    elif name == "missing_rebalance_target":
        del targets[pd.Timestamp("2020-03-31")]
    elif name == "missing_panel_month":
        p = p.loc[p["date"].ne(pd.Timestamp("2020-05-31"))]
    elif name != "ok":
        raise KeyError(name)
    return p, bench, targets, td[0], td[-1]


def assert_calendar_failure(name: str) -> None:
    try:
        engine.backtest(*calendar_case(name))
    except ValueError as exc:
        import re
        assert re.search(CALENDAR_FAILURES[name], str(exc)), f"{name}: unexpected message {exc}"
    else:
        raise AssertionError(f"{name}: the backtest did not fail")


def check_calendar_failures() -> str:
    """Every calendar or target gap raises with its own message; the complete window runs."""
    for name in CALENDAR_FAILURES:
        assert_calendar_failure(name)
    run = engine.backtest(*calendar_case("ok"))
    assert len(run) == 6 and not run["all_cash"].any()
    return f"each of {len(CALENDAR_FAILURES)} calendar and target gaps raises; a complete window runs"


ALL_CHECKS = [check_future_isolation, check_momentum_timing, check_gap_breaks_window, check_drift_cost_exit,
              check_missing_ret_hold_rejected, check_second_rebalance_after_drift, check_all_cash_flagged,
              check_calendar_failures]


def run_all() -> list[str]:
    """Run every check; raise on the first failure, otherwise return their descriptions."""
    return [check() for check in ALL_CHECKS]
