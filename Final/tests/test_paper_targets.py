"""Fixture tests for the confirmed paper targets: the Small control and Table 1's definitions."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research import engine, report  # noqa: E402


def test_small_selects_smallest_100():
    n = 260
    snap = pd.DataFrame({"date": pd.Timestamp("2019-12-31"), "permno": np.arange(1, n + 1), "eligible": True,
                         "hist36": True, "is_exit": False, "mktcap": np.arange(n, 0, -1) * 10.0,
                         "vol36": 0.05, "momentum": 0.1, "npy": 0.01})
    snap.loc[snap["permno"].eq(n), "hist36"] = False      # the smallest name lacks history: not in the universe
    snap.loc[snap["permno"].isin([100, 101]), "mktcap"] = 1605.0  # a tie in size at the cut, broken by permno
    w, c = engine.choose_weights(snap, "Small", n_universe=200, n_hold=100)
    # Universe = the 200 largest history-eligible names (permnos 1..200); Small = its 100 smallest.
    assert c["universe_n"] == 200 and c["selected_n"] == 100
    smallest = snap.loc[snap["permno"].le(200)].sort_values(["mktcap", "permno"]).head(100)["permno"]
    assert sorted(w.index) == sorted(smallest) and np.allclose(w, 0.01)
    assert 100 in w.index and 101 not in w.index and n not in w.index and 1 not in w.index
    assert c["score_ties_at_cut"] == 1
    assert "Small" in engine.PAPER_CONTROLS and "Small" in engine.ALL_STRATEGIES


def test_return_same_risk_definition():
    # Paper Table 1, market column: simple 10.6%, volatility 18.7%, rf about 3.4% -> 9.8% at the Formula's 16.5%.
    assert abs(report.return_same_risk(0.106, 0.187, 0.034) - 0.098) < 0.001
    assert np.isclose(report.derisking_factor(0.187), 0.165 / 0.187)
    assert np.isclose(report.return_same_risk(0.155, 0.165, 0.034), 0.155)          # the Formula itself
    assert np.isclose(report.sharpe_simple(0.155, 0.165), 0.155 / 0.165)
    # The paper's other columns, from its own simple return and volatility (rf 3.4%), within 0.15 pp.
    for simple, vol, same in [(0.158, 0.314, 0.099), (0.182, 0.257, 0.129), (0.106, 0.133, 0.123), (0.156, 0.201, 0.134)]:
        assert abs(report.return_same_risk(simple, vol, 0.034) - same) < 0.0015
