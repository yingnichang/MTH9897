"""Deterministic fixtures in raw legacy-CRSP layout. Run from Final/:  python -m pytest tests -q"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from crsp_pipeline import audit, config  # noqa: E402
from crsp_pipeline.build import build, validate_panel  # noqa: E402
from crsp_pipeline.extract import TABLES, build_query, decade_chunks  # noqa: E402
from crsp_pipeline.normalize import build_benchmark, build_panel  # noqa: E402
from crsp_pipeline.signals import build_signals  # noqa: E402

N = 60
TRADE_DATES = pd.date_range("2000-01-01", periods=N, freq="BME")   # CRSP-style last trading days
MONTHS = TRADE_DATES + pd.offsets.MonthEnd(0)
SPLIT_AT = 30
GAP1_AT = 40   # 111: one missing-return month inside a holding quarter
GAP2_AT = 38   # 112: two missing-return months straddling a rebalance
GAP3_AT = 45   # 113: a missing return with a CRSP price in the month


def _rows(permno, permco, ret, retx, prc, shrout, cfacpr=1.0, cfacshr=1.0, months=None):
    idx = np.arange(N) if months is None else np.asarray(months)
    as_arr = lambda v: np.broadcast_to(np.asarray(v, dtype=float), (N,))[idx]
    return pd.DataFrame({"permno": permno, "permco": permco, "date": TRADE_DATES[idx],
                         "ret": as_arr(ret), "retx": as_arr(retx), "prc": as_arr(prc),
                         "shrout": as_arr(shrout), "cfacpr": as_arr(cfacpr),
                         "cfacshr": as_arr(cfacshr), "vol": 1.0})


def make_raw():
    t = np.arange(N)
    # 101: quarterly payer with a 2-for-1 split in month 30. Adjusted (current) basis is post-split.
    p_adj = 100 * 1.01 ** t
    cf = np.where(t < SPLIT_AT, 2.0, 1.0)
    d_adj = np.where((t + 1) % 3 == 0, 0.25, 0.0)
    ret_101 = 0.01 + d_adj / np.r_[np.nan, p_adj[:-1]]
    ret_101[0] = 0.01 + d_adj[0] / (100 / 1.01)
    msf = [_rows(101, 1, ret_101, 0.01, p_adj * cf, 2000 / cf, cf, cf)]
    # 102: non-payer issuing 1% more shares per month; retx missing in month 20.
    retx_102 = np.full(N, 0.02); retx_102[20] = np.nan
    msf.append(_rows(102, 2, 0.02, retx_102, 50 * 1.02 ** t, 500 * 1.01 ** t))
    # 103: NASDAQ, last monthly row month 40, delisted next month, missing dlret, code 552.
    msf.append(_rows(103, 3, -0.02, -0.02, 20.0, 100, months=range(41)))
    # 104: NYSE merger in month 45 with dlret 0.10; a spurious row in month 46.
    msf.append(_rows(104, 4, 0.05, 0.05, 30.0, 300, months=range(47)))
    # 105/106: two classes of one company; 105 is larger.
    msf.append(_rows(105, 5, 0.01, 0.01, 40.0, 1000))
    msf.append(_rows(106, 5, 0.01, 0.01, 40.0, 100))
    # 107: share code 12; 108: exchange 4.
    msf.append(_rows(107, 7, 0.01, 0.01, 10.0, 100))
    msf.append(_rows(108, 8, 0.01, 0.01, 10.0, 100))
    # 109: industry change in July 2002; missing monthly row 10.
    msf.append(_rows(109, 9, 0.015, 0.015, 25.0, 200, months=[m for m in range(N) if m != 10]))
    # 110: name history starts January 2001.
    msf.append(_rows(110, 10, 0.01, 0.01, 15.0, 100))
    # 111: first row has no return; no-trade month GAP1_AT, the next return spans the gap.
    # In the universe at formation month 38 (2003-03), so the gap resumes inside that quarter.
    p_111 = 10 * 1.01 ** t
    r_111 = np.full(N, 0.01); r_111[[0, GAP1_AT]] = np.nan; r_111[GAP1_AT + 1] = 1.01 ** 2 - 1
    msf.append(_rows(111, 11, r_111, r_111, np.where(np.isnan(r_111) & (t > 0), np.nan, p_111), 100))
    # 112: two no-trade months GAP2_AT..+1, held from formation month 35 (2002-12); the gap
    # straddles the 2003-03 rebalance and the return in month 40 spans both months.
    p_112 = 30 * 1.01 ** t
    r_112 = np.full(N, 0.01); r_112[[GAP2_AT, GAP2_AT + 1]] = np.nan; r_112[GAP2_AT + 2] = 1.01 ** 3 - 1
    msf.append(_rows(112, 12, r_112, r_112, np.where(np.isnan(r_112), np.nan, p_112), 100))
    # 113: CRSP reports a price but no return in month GAP3_AT (held from formation month 44,
    # 2003-09); the next return starts from that in-gap price, as CRSP does (DATA-010).
    r_113 = np.full(N, 0.01); r_113[GAP3_AT] = np.nan
    msf.append(_rows(113, 13, r_113, r_113, 20 * 1.01 ** t, 100))
    msf = pd.concat(msf, ignore_index=True)

    def name(permno, start, end, shrcd=11, exchcd=1, siccd=2000, ticker="X", permco=None):
        return {"permno": permno, "permco": permco or permno, "namedt": pd.Timestamp(start),
                "nameendt": pd.Timestamp(end), "shrcd": shrcd, "exchcd": exchcd, "siccd": siccd,
                "ticker": ticker, "comnam": f"CO {permno}", "shrcls": None}
    names = pd.DataFrame([
        name(101, "1999-01-01", "2024-12-31", ticker="PAY", siccd=3570, permco=1),
        name(102, "1999-01-01", "2024-12-31", ticker="ISS", permco=2),
        name(103, "1999-01-01", "2003-06-30", exchcd=3, permco=3),
        name(104, "1999-01-01", "2004-01-31", permco=4),
        name(105, "1999-01-01", "2024-12-31", ticker="CLA", permco=5),
        name(106, "1999-01-01", "2024-12-31", ticker="CLB", permco=5),
        name(107, "1999-01-01", "2024-12-31", shrcd=12, permco=7),
        name(108, "1999-01-01", "2024-12-31", exchcd=4, permco=8),
        name(109, "1999-01-01", "2002-06-30", siccd=2834, permco=9),
        name(109, "2002-07-01", "2024-12-31", siccd=7372, permco=9),
        name(110, "2001-01-01", "2024-12-31", permco=10),
        name(111, "1999-01-01", "2024-12-31", ticker="GAPA", permco=11),
        name(112, "1999-01-01", "2024-12-31", ticker="GAPB", permco=12),
        name(113, "1999-01-01", "2024-12-31", ticker="GAPC", permco=13),
    ])
    delist = pd.DataFrame({
        "permno": [103, 104, 101], "dlstdt": pd.to_datetime(["2003-06-15", "2003-10-20", "2025-01-01"]),
        "dlstcd": [552, 233, 100], "dlret": [np.nan, 0.10, np.nan], "dlretx": [np.nan, 0.10, np.nan],
        "dlprc": np.nan, "nwperm": 0})
    q = (t + 1) % 3 == 0
    dist = pd.DataFrame({"permno": 101, "distcd": 1232, "divamt": (d_adj * cf)[q],
                         "facpr": 0.0, "facshr": 0.0, "exdt": TRADE_DATES[q] - pd.Timedelta(days=5),
                         "dclrdt": pd.NaT, "rcrddt": pd.NaT, "paydt": pd.NaT})
    split = pd.DataFrame({"permno": [101], "distcd": [5523], "divamt": [0.0], "facpr": [1.0], "facshr": [1.0],
                          "exdt": [TRADE_DATES[SPLIT_AT] - pd.Timedelta(days=3)],
                          "dclrdt": pd.NaT, "rcrddt": pd.NaT, "paydt": pd.NaT})
    msi = pd.DataFrame({"date": TRADE_DATES, "vwretd": 0.01, "vwretx": 0.008, "ewretd": 0.012,
                        "totval": 1e6, "totcnt": 10})
    ff = pd.DataFrame({"dateff": MONTHS, "mktrf": 0.009, "smb": 0.0, "hml": 0.0, "rf": 0.001, "umd": 0.0})
    return {"msf": msf, "msenames": names, "msedelist": delist,
            "msedist": pd.concat([dist, split], ignore_index=True), "msi": msi, "ff_factors": ff}


@pytest.fixture(scope="module")
def built():
    raw = make_raw()
    panel, log = build_panel(raw)
    return raw, panel, log


def rows(panel, permno):
    return panel.loc[panel["permno"].eq(permno)].sort_values("date").reset_index(drop=True)


def test_month_end_dates_and_contract(built):
    _, panel, _ = built
    assert panel["date"].dt.is_month_end.all()
    validate_panel(panel)


def test_split_is_not_issuance_and_dividends_survive_split(built):
    _, panel, _ = built
    s = rows(panel, 101)
    assert np.allclose(s["shares_adj"], 2000)
    assert np.allclose(s["price_adj"].pct_change().iloc[1:], 0.01)
    expected = np.where((np.arange(N) + 1) % 3 == 0, 0.25, 0.0)
    assert np.isnan(s["div_cash_adj"].iloc[0])           # no prior month: unknown, not zero
    assert np.allclose(s["div_cash_adj"].iloc[1:], expected[1:])
    sig = build_signals(panel).query("permno == 101").reset_index(drop=True)
    assert np.allclose(sig["net_issuance"].dropna(), 0)
    assert np.allclose(sig["div_yield"].iloc[-1], 1.0 / s["price_adj"].iloc[-1])


def test_confirmed_zero_versus_unknown_dividends(built):
    _, panel, _ = built
    s = rows(panel, 102)
    assert s.loc[20, "div_cash_adj"] != s.loc[20, "div_cash_adj"]        # NaN when retx missing
    assert (s.loc[s.index.difference([0, 20]), "div_cash_adj"] == 0).all()
    sig = build_signals(panel).query("permno == 102").reset_index(drop=True)
    ni = sig["net_issuance"].iloc[-1]
    assert np.isclose(ni, 1 / np.mean(1.01 ** -np.arange(24)) - 1)      # positive issuance lowers NPY
    assert sig["npy"].iloc[-1] < 0


def test_missing_delisting_return_appended_and_imputed(built):
    _, panel, log = built
    s = rows(panel, 103)
    last = s.iloc[-1]
    assert len(s) == 42 and last["is_exit"] and not last["eligible"]
    assert last["date"] == pd.Timestamp("2003-06-30")
    assert np.isclose(last["ret_total"], config.DELIST_IMPUTE_NASDAQ)
    assert last["delist_source"] == "imputed_shumway"
    assert log.set_index("permno").loc[103, "placement"] == "appended_month"


def test_same_month_delisting_compounded_once_and_later_rows_dropped(built):
    _, panel, log = built
    s = rows(panel, 104)
    assert s["date"].max() == pd.Timestamp("2003-10-31") and s["is_exit"].sum() == 1
    assert np.isclose(s.iloc[-1]["ret_total"], 1.05 * 1.10 - 1)
    assert np.isclose(s.iloc[-2]["ret_total"], 0.05)
    assert log.set_index("permno").loc[104, "rows_dropped"] == 1


def test_active_code_is_not_an_exit(built):
    _, panel, _ = built
    assert not rows(panel, 101)["is_exit"].any()


def test_one_eligible_class_per_company(built):
    _, panel, _ = built
    a, b = rows(panel, 105), rows(panel, 106)
    assert a["eligible"].all() and not b["eligible"].any()
    assert (b["exclusion"] == "secondary_share_class").all()
    assert np.allclose(a["mktcap_company"], 40 * 1100 / 1e3)


def test_exclusion_reasons(built):
    _, panel, _ = built
    assert (rows(panel, 107)["exclusion"] == "share_code").all()
    assert (rows(panel, 108)["exclusion"] == "exchange").all()
    s = rows(panel, 110)
    assert (s.loc[s["date"] < "2001-01-01", "exclusion"] == "no_name_record").all()
    assert s.loc[s["date"] >= "2001-01-31", "eligible"].all()


def test_point_in_time_industry_and_history_gap(built):
    _, panel, _ = built
    s = rows(panel, 109).set_index("date")
    assert s.loc["2002-06-30", "ff12"] == "Hlth" and s.loc["2002-07-31", "ff12"] == "BusEq"
    # Gap at month 10 (November 2000): the first full 36-month window ends 36 rows later.
    hist = s["hist36"]
    assert not hist.loc[:"2003-10-31"].any() and hist.loc["2003-11-30"]
    assert np.isnan(s.loc["2000-12-31", "div_cash_adj"])


def test_history_screen_precedes_capitalization_cut(built, monkeypatch):
    _, panel, _ = built
    monkeypatch.setattr(config, "UNIVERSE_SIZE", 2)
    cov = audit.formation_coverage(panel).set_index("date")
    row = cov.loc["2003-06-30"]
    # 109 lacks 36 consecutive months after its gap; only stocks with full history qualify.
    assert row["universe_n"] == 2
    snap = panel.loc[panel["date"].eq("2003-06-30")]
    assert audit.universe_members(snap, 2)["hist36"].all()


HOLD_COLS = ["ret_hold", "ret_hold_source"]


def test_ret_hold_stale_carry_and_resumption(built):
    _, panel, _ = built
    s = rows(panel, 111)
    gap, resume = s.loc[GAP1_AT], s.loc[GAP1_AT + 1]
    assert np.isnan(gap["ret_total"]) and gap["ret_hold"] == 0 and gap["ret_hold_source"] == "stale_carry"
    assert resume["ret_hold"] == resume["ret_total"] and resume["ret_hold_source"] == "crsp"
    growth = (1 + s.loc[GAP1_AT:GAP1_AT + 1, "ret_hold"]).prod()
    assert np.isclose(growth, s.loc[GAP1_AT + 1, "price_adj"] / s.loc[GAP1_AT - 1, "price_adj"])
    b = rows(panel, 112)
    assert (b.loc[GAP2_AT:GAP2_AT + 1, "ret_hold_source"] == "stale_carry").all()
    assert np.isclose((1 + b.loc[GAP2_AT:GAP2_AT + 2, "ret_hold"]).prod(),
                      b.loc[GAP2_AT + 2, "price_adj"] / b.loc[GAP2_AT - 1, "price_adj"])
    observed = panel["ret_total"].notna()
    assert (panel.loc[observed, "ret_hold"] == panel.loc[observed, "ret_total"]).all()
    assert (panel.loc[observed, "ret_hold_source"] == "crsp").all()


def test_ret_hold_first_row_and_exit(built):
    _, panel, _ = built
    first = rows(panel, 111).iloc[0]
    assert np.isnan(first["ret_total"]) and np.isnan(first["ret_hold"])
    assert first["ret_hold_source"] == "no_prior_row"
    for permno, expected in [(103, config.DELIST_IMPUTE_NASDAQ), (104, 1.05 * 1.10 - 1)]:
        last = rows(panel, permno).iloc[-1]
        assert last["is_exit"] and last["ret_hold_source"] == "crsp"
        assert np.isclose(last["ret_hold"], expected)
    assert rows(panel, 103).iloc[-1]["delist_ret_without_monthly"]      # base ret was NaN, still crsp


def test_ret_hold_leaves_returns_history_and_signals_unchanged(built):
    from crsp_pipeline.normalize import add_holding_returns
    _, panel, _ = built
    without = panel.drop(columns=HOLD_COLS)
    again = add_holding_returns(without)
    pd.testing.assert_frame_equal(again[without.columns], without)
    pd.testing.assert_frame_equal(again[HOLD_COLS], panel[HOLD_COLS])
    pd.testing.assert_frame_equal(build_signals(panel), build_signals(without))
    # A gap still breaks the 36-month history: False from the gap until 36 new returns accrue.
    for permno, gap in [(111, GAP1_AT), (112, GAP2_AT)]:
        s = rows(panel, permno)
        assert s.loc[gap - 1, "hist36"] and not s.loc[gap:, "hist36"].any()
        assert s.loc[gap:, "ret_total"].isna().sum() == (1 if permno == 111 else 2)


def test_ret_hold_price_ratio_in_gap(built):
    _, panel, _ = built
    s = rows(panel, 113)
    gap, resume = s.loc[GAP3_AT], s.loc[GAP3_AT + 1]
    assert np.isnan(gap["ret_total"]) and gap["ret_hold_source"] == "price_ratio"
    assert np.isclose(gap["ret_hold"], gap["price_adj"] / s.loc[GAP3_AT - 1, "price_adj"] - 1)
    assert resume["ret_hold_source"] == "crsp" and resume["ret_hold"] == resume["ret_total"]
    growth = (1 + s.loc[GAP3_AT:GAP3_AT + 1, "ret_hold"]).prod()
    assert np.isclose(growth, resume["price_adj"] / s.loc[GAP3_AT - 1, "price_adj"])
    # ret_total and hist36 keep the gap.
    assert not s.loc[GAP3_AT, "hist36"]


def test_ret_hold_price_ratio_lookback_bound():
    from crsp_pipeline.normalize import add_holding_returns
    dates = pd.date_range("2001-01-31", periods=6, freq="ME")
    # Security 1: last price 4 months before the priced gap month -> stale carry.
    # Security 2: last price exactly PRICE_RATIO_MAX_LOOKBACK_MONTHS (3) before -> price ratio.
    p = pd.DataFrame({
        "permno": [1] * 6 + [2] * 6, "date": list(dates) * 2, "is_exit": False,
        "ret_total": [0.01, np.nan, np.nan, np.nan, np.nan, 0.02] + [0.01, np.nan, np.nan, np.nan, 0.02, 0.02],
        "price_adj": [10, np.nan, np.nan, np.nan, 12, 12.24] + [10, np.nan, np.nan, 11, 11.22, 11.44]})
    out = add_holding_returns(p)
    assert config.PRICE_RATIO_MAX_LOOKBACK_MONTHS == 3
    one, two = out.loc[out["permno"].eq(1)].reset_index(drop=True), out.loc[out["permno"].eq(2)].reset_index(drop=True)
    assert (one.loc[1:4, "ret_hold_source"] == "stale_carry").all() and (one.loc[1:4, "ret_hold"] == 0).all()
    assert (two.loc[1:2, "ret_hold_source"] == "stale_carry").all()
    assert two.loc[3, "ret_hold_source"] == "price_ratio" and np.isclose(two.loc[3, "ret_hold"], 0.1)


def _hold_differs(p):
    i = p.index[p["ret_hold_source"].eq("crsp")][0]
    p.loc[i, "ret_hold"] += 0.5


def _hold_nan_on_stale(p):
    p.loc[p["ret_hold_source"].eq("stale_carry"), "ret_hold"] = np.nan


def _stale_on_exit(p):
    p.loc[p["is_exit"], "ret_hold_source"] = "stale_carry"   # ret_hold still equals ret_total there


def _unknown_source(p):
    p.loc[p["ret_hold_source"].eq("stale_carry"), "ret_hold_source"] = "filled"


def _price_ratio_on_exit(p):
    p.loc[p["is_exit"], "ret_hold_source"] = "price_ratio"   # observed return and a terminal flag


def _price_ratio_without_price(p):
    p.loc[p["ret_hold_source"].eq("price_ratio"), "price_adj"] = np.nan


@pytest.mark.parametrize("breaker, message", [
    (_hold_differs, "ret_hold differs from ret_total"),
    (_hold_nan_on_stale, "ret_hold is NaN outside no_prior_row"),
    (_stale_on_exit, "stale_carry on a terminal row"),
    (_unknown_source, "Unknown ret_hold_source"),
    (_price_ratio_on_exit, "price_ratio on a row with an observed return or a terminal flag"),
    (_price_ratio_without_price, "price_ratio without a positive price"),
])
def test_validate_panel_rejects_bad_ret_hold(built, breaker, message):
    _, panel, _ = built
    bad = panel.copy()
    breaker(bad)
    with pytest.raises(AssertionError, match=message):
        validate_panel(bad)


def test_missing_returns_audit_counts(built):
    _, panel, _ = built
    t = audit.missing_returns(panel).set_index("decade")
    total = t.loc["total"]
    assert total["nan_ret_rows"] == 5 and total["stale_carry_rows"] == 3 and total["no_prior_row_rows"] == 1
    assert total["price_ratio_rows"] == 1
    # Missing-return holding months (stale_carry or price_ratio): 111 month 40, 112 month 38, 113 month 45.
    assert total["universe_holding_stale_carry"] == 3 and total["universe_holding_price_ratio"] == 1
    assert total["universe_holding_securities"] == 3 and total["universe_holding_runs"] == 3
    assert total["resume_in_quarter"] == 2 and total["straddle_rebalance"] == 1
    assert total["runs_over_10_months"] == 0 and total["runs_resuming_with_valid_return"] == 3
    assert total["runs_le_10_crsp_spans_gap"] == 2 and total["runs_le_10_checkable"] == 3
    assert total["universe_holding_months"] > total["universe_holding_stale_carry"]
    # 113's next return starts from the in-gap price, so it does not span the gap.
    assert total["runs_le_10_nonspanning_priced_gap"] == 1 and total["runs_le_10_nonspanning_other"] == 0
    by_decade = t.drop(index="total")
    for col in ["nan_ret_rows", "price_ratio_rows", "universe_holding_months", "universe_holding_stale_carry",
                "universe_holding_price_ratio", "resume_in_quarter",
                "straddle_rebalance", "universe_holding_runs", "runs_resuming_with_valid_return",
                "runs_le_10_nonspanning_priced_gap", "runs_le_10_nonspanning_other"]:
        assert by_decade[col].sum() == total[col], col


def test_missing_returns_audit_with_no_missing_returns(built):
    _, panel, _ = built
    clean = panel.loc[panel["permno"].eq(101)].reset_index(drop=True)
    validate_panel(clean)
    assert clean["ret_total"].notna().all()
    t = audit.missing_returns(clean).set_index("decade")
    total = t.loc["total"]
    zero = [c for c in t.columns if c != "universe_holding_months"]
    assert (t[zero] == 0).all().all()
    # hist36 from 2002-12 (month 35): formations 2002-12 .. 2004-09 hold 3 rows each (8 x 3);
    # the 2004-12 formation has no holding rows inside the fixture.
    assert total["universe_holding_months"] == 24
    assert t.drop(index="total")["universe_holding_months"].sum() == 24


def test_missing_returns_classifies_nonspanning_runs(built):
    _, panel, _ = built
    p = panel.copy()
    # 111: CRSP reports a price but no return in the gap month, and the resumption return starts
    # from that in-gap price, so it no longer spans the gap.
    gap = p.index[p["permno"].eq(111)][GAP1_AT]
    p.loc[gap, "price_adj"] = p.loc[gap - 1, "price_adj"] * 1.05
    p.loc[gap + 1, "ret_price"] = p.loc[gap + 1, "price_adj"] / p.loc[gap, "price_adj"] - 1
    # 112: no in-gap price, but the resumption price return disagrees with the price ratio
    # (as when a non-ordinary distribution falls in the gap).
    resume = p.index[p["permno"].eq(112)][GAP2_AT + 2]
    p.loc[resume, "ret_price"] -= 0.05
    total = audit.missing_returns(p).set_index("decade").loc["total"]
    # 113 is a priced gap in the unperturbed fixture already.
    assert total["runs_le_10_checkable"] == 3 and total["runs_le_10_crsp_spans_gap"] == 0
    assert total["runs_le_10_nonspanning_priced_gap"] == 2 and total["runs_le_10_nonspanning_other"] == 1


def notebook_build_signals(p):
    """Reference copy of the notebook's Section 4 loop implementation."""
    parts = []
    for sid, raw in p.groupby("permno", sort=False):
        g = raw.set_index("date").sort_index()
        g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="ME"))
        g.index.name = "date"
        g["permno"] = sid
        g["vol36"] = g.ret_total.rolling(36, min_periods=36).std(ddof=1) * np.sqrt(12)
        g["momentum"] = (1 + g.ret_price).shift(1).rolling(11, min_periods=11).apply(np.prod, raw=True) - 1
        g["div_yield"] = g.div_cash_adj.rolling(12, min_periods=12).sum() / g.price_adj
        g["net_issuance"] = g.shares_adj / g.shares_adj.rolling(24, min_periods=24).mean() - 1
        g["npy"] = g.div_yield - g.net_issuance
        parts.append(g.reset_index())
    return pd.concat(parts, ignore_index=True)


def test_vectorized_signals_match_notebook_definitions(built):
    _, panel, _ = built
    cols = ["vol36", "momentum", "div_yield", "net_issuance", "npy"]
    fast = build_signals(panel).set_index(["permno", "date"])[cols]
    ref = notebook_build_signals(panel[["date", "permno", "ret_total", "ret_price", "div_cash_adj",
                                        "price_adj", "shares_adj"]]).set_index(["permno", "date"])[cols]
    ref = ref.reindex(fast.index)
    pd.testing.assert_frame_equal(fast, ref, check_exact=False, rtol=1e-9, atol=1e-12)
    assert fast.notna().sum().min() > 0


def test_dividend_reconciliation_agrees_with_distribution_file(built):
    raw, panel, _ = built
    rec = audit.dividend_reconciliation(panel, raw["msedist"])
    assert (rec["agree_ordinary_cash"] == 1).all()
    paying = rec["n_with_distribution_ordinary_cash"] > 0
    assert paying.any() and (rec.loc[paying, "agree_ordinary_cash_given_distribution"] == 1).all()


def test_benchmark_coverage_is_enforced():
    raw = make_raw()
    bench, _ = build_benchmark(raw["msi"], raw["ff_factors"], "2000-01-31", "2004-12-31")
    assert len(bench) == N and np.allclose(bench["market_ret"], 0.01)
    with pytest.raises(ValueError, match="does not cover"):
        build_benchmark(raw["msi"].iloc[1:], raw["ff_factors"], "2000-01-31", "2004-12-31")
    with pytest.raises(ValueError, match="does not cover"):
        build_benchmark(raw["msi"], raw["ff_factors"], "2000-01-31", "2005-03-31")
    pct = raw["ff_factors"].assign(rf=0.1, mktrf=0.9 * 100)
    with pytest.raises(ValueError, match="percentages"):
        build_benchmark(raw["msi"], pct, "2000-01-31", "2004-12-31")


def test_end_to_end_build_writes_outputs_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BENCHMARK_START", "2000-01-31")
    res = build(make_raw(), out_dir=tmp_path, end="2004-12-31")
    for f in ["crsp_monthly_normalized.parquet", "benchmark_monthly.csv", "ff_factors_monthly.csv",
              "manifest.json", "audit/formation_coverage.csv", "audit/worked_examples.csv",
              "audit/missing_returns.csv"]:
        assert (tmp_path / f).exists(), f
    man = json.loads((tmp_path / "manifest.json").read_text())
    assert man["extract"] is None and man["sample"]["terminal_rows"] == 2
    assert man["sample"]["ret_hold_stale_carry_rows"] == 3 and man["sample"]["ret_hold_no_prior_row_rows"] == 1
    assert man["sample"]["ret_hold_price_ratio_rows"] == 1
    assert man["sample"]["universe_holding_stale_carry_months"] == 3      # missing-return holding months
    assert "audit/missing_returns.csv" in man["audits"]
    assert "crsp_pipeline/normalize.py" in man["code"]["source_sha256"]
    assert man["code"]["packages"]["pandas"] == pd.__version__
    back = pd.read_parquet(tmp_path / "crsp_monthly_normalized.parquet")
    pd.testing.assert_frame_equal(back, res["panel"])


def test_extract_queries_name_every_required_field():
    for name, (_, _, cols, _, _) in TABLES.items():
        sql = build_query(name, "crsp")
        assert all(c in sql for c in cols)
        assert "{lib}" not in sql
    assert "shrcd in (10, 11)" in build_query("msf", "crsp")
    chunks = list(decade_chunks("1925-12-31", "2024-12-31"))
    assert chunks[0] == ("1925-12-31", "1929-12-31") and chunks[-1] == ("2020-01-01", "2024-12-31")
    assert all(pd.Timestamp(b) + pd.Timedelta(days=1) == pd.Timestamp(a2)
               for (_, b), (a2, _) in zip(chunks, chunks[1:]))
