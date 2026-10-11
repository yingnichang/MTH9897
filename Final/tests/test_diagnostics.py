"""Fixture tests of research.diagnostics. Run from Final/:  python -m pytest tests -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from crsp_pipeline.normalize import consecutive  # noqa: E402
from research import diagnostics as dg, engine  # noqa: E402

T0 = pd.Timestamp("2000-12-31")


def test_neutralize_demeans_within_group_and_clips():
    # One date. NoDur has 5 members, Manuf 6; Hlth (2) and Other (3) merge into a 5-member Other group.
    ind = ["NoDur"] * 5 + ["Manuf"] * 6 + ["Hlth"] * 2 + ["Other"] * 3
    x = np.array([1, 2, 3, 4, 5, 10, 10, 10, 10, 10, 70, 0, 2, 4, 6, 8], dtype=float)
    u = pd.DataFrame({"date": T0, "ff12": ind, "x": x})
    g = dg.industry_groups(u)
    assert g.tolist() == ["NoDur"] * 5 + ["Manuf"] * 6 + ["Other"] * 5
    z, counts = dg.neutralize(u["x"], u["date"], g)
    # Hand: group means 3 (NoDur), 20 (Manuf), 4 (Other); demeaned values, then sd over all 16 (ddof 1).
    d = x - np.array([3] * 5 + [20] * 6 + [4] * 5)
    sd = d.std(ddof=1)
    expected = np.clip(d / sd, -3, 3)
    assert np.allclose(z, expected)
    assert (d / sd).max() > 3 and z.max() == 3.0 and counts["clipped"] == 1     # the 70 is clipped
    for grp in ["NoDur", "Other"]:                                              # unclipped groups are demeaned
        assert abs(z[g.eq(grp)].sum()) < 1e-12
    # A missing value stays missing and is counted.
    u.loc[0, "x"] = np.nan
    z2, c2 = dg.neutralize(u["x"], u["date"], g)
    assert np.isnan(z2.iloc[0]) and c2["missing"] == 1 and c2["values"] == 15


def returns_panel(rows):
    p = pd.DataFrame(rows, columns=["date", "permno", "ret_hold", "is_exit"])
    p["date"] = pd.to_datetime(p["date"])
    return p


def test_forward_return_cohort_includes_exits():
    d = pd.date_range("2001-01-31", periods=4, freq="ME")
    # Security 1 exits in month 2 with -50% (its terminal return); afterwards it has no rows and earns 0 as cash.
    p = returns_panel([(T0, 1, 0.0, False), (T0, 2, 0.0, False),
                       (d[0], 1, 0.10, False), (d[0], 2, 0.01, False),
                       (d[1], 1, -0.50, True), (d[1], 2, 0.02, False),
                       (d[2], 2, 0.03, False), (d[3], 2, 0.04, False)])
    u = pd.DataFrame({"date": [T0, T0], "permno": [1, 2]})
    f = dg.forward_returns(p, u, horizons=[1, 2, 3, 4])
    assert np.isclose(f.loc[0, "fwd_1"], 0.10)
    assert np.isclose(f.loc[0, "fwd_2"], 1.10 * 0.50 - 1)                       # exit return counted once
    assert np.isclose(f.loc[0, "fwd_4"], 1.10 * 0.50 - 1)                       # then cash: 0
    assert not f.loc[0, "exit_within_1"] and f.loc[0, "exit_within_2"] and f.loc[0, "exit_within_4"]
    assert np.isclose(f.loc[1, "fwd_4"], 1.01 * 1.02 * 1.03 * 1.04 - 1) and not f.loc[1, "exit_within_4"]
    # Beyond the end of the data the forward return is missing, not zero.
    f5 = dg.forward_returns(p, u, horizons=[5])
    assert f5["fwd_5"].isna().all()


def test_industry_adjusted_sums_to_zero_within_group():
    rng = np.random.default_rng(0)
    u = pd.DataFrame({"date": np.repeat([T0, T0 + pd.offsets.MonthEnd(1)], 20),
                      "group": np.tile(["A"] * 7 + ["B"] * 8 + ["C"] * 5, 2), "fwd": rng.normal(0, 0.1, 40)})
    u.loc[3, "fwd"] = np.nan
    adj = dg.industry_adjust(u["fwd"], u["date"], u["group"])
    sums = adj.groupby([u["date"], u["group"]]).sum()
    assert np.allclose(sums, 0) and np.isnan(adj.iloc[3])


def test_ic_spearman_matches_hand():
    # x ranks 1..5; y = [5, 6, 7, 8, 7] has ranks [1, 2, 3.5, 5, 3.5] (ties averaged).
    df = pd.DataFrame({"date": T0, "x": [1.0, 2, 3, 4, 5], "y": [5.0, 6, 7, 8, 7]})
    rx, ry = np.array([1, 2, 3, 4, 5.0]), np.array([1, 2, 3.5, 5, 3.5])
    hand = ((rx - rx.mean()) * (ry - ry.mean())).sum() / np.sqrt(((rx - rx.mean()) ** 2).sum() * ((ry - ry.mean()) ** 2).sum())
    assert np.isclose(dg.spearman_by_date(df, "x", "y").iloc[0], hand)
    assert np.isclose(hand, 0.8207826816681233)
    # Perfectly reversed ranks give -1; rows with a missing value are dropped.
    df2 = pd.DataFrame({"date": T0, "x": [1.0, 2, 3, 4, np.nan], "y": [4.0, 3, 2, 1, 0]})
    assert np.isclose(dg.spearman_by_date(df2, "x", "y").iloc[0], -1.0)


def test_decile_assignment_equal_count():
    rng = np.random.default_rng(1)
    for n in (1000, 25, 37):
        x = pd.Series(rng.normal(size=n))
        dec = dg.deciles(x, pd.Series(T0, index=x.index), pd.Series(np.arange(n)))
        sizes = dec.value_counts().sort_index()
        assert list(sizes.index) == list(range(1, 11)) and sizes.max() - sizes.min() <= 1
        assert (x.groupby(dec).max().iloc[:-1].to_numpy() <= x.groupby(dec).min().iloc[1:].to_numpy()).all()
    x = pd.Series([0.5, np.nan] + list(range(10)), dtype=float)
    dec = dg.deciles(x, pd.Series(T0, index=x.index), pd.Series(range(12)))
    assert np.isnan(dec.iloc[1]) and dec.notna().sum() == 11


def synthetic_panel(n_names=40, n_months=60, seed=5):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1996-01-31", periods=n_months, freq="ME")
    rows = []
    for k in range(n_names):
        r = rng.normal(0.01, 0.06, n_months)
        price = 20 * np.cumprod(1 + r)
        rows.append(pd.DataFrame({"date": dates, "permno": 100 + k, "ret_total": r, "ret_price": r - 0.001,
                                  "ret_hold": r, "price_adj": price, "div_cash_adj": 0.001 * price,
                                  "shares_adj": 1e6 * (1 + 0.002 * k) ** np.arange(n_months),
                                  "mktcap": price * (1 + k), "eligible": True, "is_exit": False,
                                  "ff12": ["NoDur", "Manuf", "Money", "BusEq"][k % 4]}))
    p = pd.concat(rows, ignore_index=True).sort_values(["permno", "date"]).reset_index(drop=True)
    p["hist36"] = consecutive(p, p["ret_total"].notna(), 36)
    return p


def exposures_at(panel, t):
    sig = engine.attach_signals(panel)
    u = dg.monthly_universe(sig, t, t, n_universe=30)
    e, _ = dg.exposures(u)
    return e.set_index("permno")[dg.EXPOSURES]


def test_exposures_unchanged_when_future_inputs_change():
    p = synthetic_panel()
    t = p["date"].unique()[47]
    before = exposures_at(p, t)
    q = p.copy()
    later = q["date"].gt(t)
    q.loc[later, ["ret_total", "ret_price", "ret_hold"]] = 0.5
    q.loc[later, ["price_adj", "mktcap", "shares_adj"]] *= 7
    q.loc[later, "div_cash_adj"] *= 3
    q["hist36"] = consecutive(q, q["ret_total"].notna(), 36)
    after = exposures_at(q, t)
    assert before.notna().all().all() and len(before) == 30
    pd.testing.assert_frame_equal(before, after)


def test_monthly_universe_matches_engine_selector():
    p = synthetic_panel()
    sig = engine.attach_signals(p)
    t = p["date"].unique()[50]
    u = dg.monthly_universe(sig, t, t, n_universe=17)
    ref = engine.select_universe(sig.loc[sig["date"].eq(t)], 17)
    assert sorted(u["permno"]) == sorted(ref["permno"])
