"""Fixture tests of the declared Phase 5 improvement "Conservative buffer" (rank buffer) in research.engine."""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research import engine  # noqa: E402

FORMATION = pd.Timestamp("2019-12-31")


def snapshot(n, **cols):
    """n universe candidates, permno 1..n; vol36 rises with permno, and the combined score worsens with it."""
    base = {"date": FORMATION, "permno": np.arange(1, n + 1), "eligible": True, "hist36": True,
            "is_exit": False, "mktcap": np.arange(n, 0, -1) * 10.0, "vol36": np.arange(1, n + 1) / 100,
            "momentum": np.linspace(0.3, 0.0, n), "npy": np.linspace(0.05, 0.0, n)}
    base.update(cols)
    return pd.DataFrame(base)


def held(*permnos):
    return pd.Series(1 / len(permnos), index=pd.Index(permnos, name="permno"))


def buffer(snap, holdings, n_hold=5, buffer_n=8):
    return engine.choose_weights(snap, "Conservative buffer", n_universe=40, n_hold=n_hold, holdings=holdings,
                                 buffer_n=buffer_n)


def test_buffer_keeps_holdings_within_150():
    # Pool = permnos 1..20 (low-vol half of 40), ranked 1 (best) .. 20. Hold 5, buffer 8 (the 100/150 rule scaled).
    w, c = buffer(snapshot(40), held(6, 8, 9, 12))
    assert sorted(w.index) == [1, 2, 3, 6, 8]           # 6 and 8 rank within the top 8 and stay; 9 and 12 do not
    assert np.allclose(w, 0.2) and c["buffer_kept_n"] == 2 and c["selected_n"] == 5
    base, _ = engine.choose_weights(snapshot(40), "Conservative", n_universe=40, n_hold=5)
    assert sorted(base.index) == [1, 2, 3, 4, 5]
    assert engine.BUFFER_N == 150 and engine.DEFAULT_HOLDINGS == 100   # the declared parameter


def test_buffer_fills_with_best_ranked():
    snap = snapshot(40)
    w0, c0 = buffer(snap, None)                          # no current holdings: identical to the baseline rule
    base, cb = engine.choose_weights(snap, "Conservative", n_universe=40, n_hold=5)
    pd.testing.assert_series_equal(w0, base)
    assert c0["buffer_kept_n"] == 0
    w, c = buffer(snap, held(7))
    assert sorted(w.index) == [1, 2, 3, 4, 7] and c["buffer_kept_n"] == 1
    w, c = buffer(snap, held(1, 2, 3, 4, 5))
    assert sorted(w.index) == [1, 2, 3, 4, 5] and c["buffer_kept_n"] == 5


def test_buffer_sells_names_leaving_pool():
    snap = snapshot(40)
    snap.loc[snap["permno"].eq(4), "npy"] = np.nan       # 4 is in the pool but no longer complete: not ranked
    # 25 is outside the low-vol pool, 99 has left the universe, 7 is kept; the rest is filled from the best.
    w, c = buffer(snap, held(4, 7, 25, 99))
    assert sorted(w.index) == [1, 2, 3, 5, 7] and c["buffer_kept_n"] == 1
    assert not {4, 25, 99} & set(w.index)


def test_formation_targets_buffer_uses_previous_targets():
    panel, bench = engine.make_demo(n_stocks=200)
    panel, bench = engine.validate_inputs(panel, bench)
    s = engine.attach_signals(panel)
    start, last = pd.Timestamp("2003-01-31"), pd.Timestamp("2010-12-31")
    tg, counts = engine.formation_targets(s, ["Conservative", "Conservative buffer"], start=start, last=last,
                                          n_hold=20, buffer_n=30)
    forms = sorted(tg["Conservative"])
    base, buf = tg["Conservative"], tg["Conservative buffer"]
    pd.testing.assert_series_equal(base[forms[0]], buf[forms[0]])
    for prev, f in zip(forms, forms[1:]):
        snap = s.loc[s["date"].eq(f)]
        w, _ = engine.choose_weights(snap, "Conservative buffer", n_hold=20, holdings=buf[prev], buffer_n=30)
        pd.testing.assert_series_equal(w, buf[f])
    changed = lambda t: sum(len(set(t[a].index) ^ set(t[b].index)) for a, b in zip(forms, forms[1:]))
    assert changed(buf) < changed(base)
    assert counts.loc[counts["strategy"].eq("Conservative buffer"), "buffer_kept_n"].iloc[1:].gt(0).all()


def frame_hash(df):
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes()).hexdigest()


def test_baseline_unchanged():
    # The Conservative targets and counts do not depend on whether the buffer runs alongside, and the demo
    # Conservative backtest matches the hash recorded before the engine was extended.
    p, b = engine.make_demo()
    p, b = engine.validate_inputs(p, b)
    s = engine.attach_signals(p)
    start, end = pd.Timestamp("2003-01-31"), pd.Timestamp("2025-12-31")
    alone, ca = engine.formation_targets(s, ["Conservative"], start=start, last=end)
    both, cb = engine.formation_targets(s, ["Conservative", "Conservative buffer"], start=start, last=end)
    for f, w in alone["Conservative"].items():
        pd.testing.assert_series_equal(w, both["Conservative"][f])
    pd.testing.assert_frame_equal(ca, cb.loc[cb["strategy"].eq("Conservative"), ca.columns].reset_index(drop=True))
    assert "buffer_kept_n" not in ca.columns
    log = []
    run = engine.backtest(p, b, alone["Conservative"], start, end, 30, trade_log=log)
    assert frame_hash(run) == "a1312701744f461f713bcf48e90ea96d71c3cff1d3bee24ebe76974523f5219e"
    assert frame_hash(pd.concat(log, ignore_index=True)) == "c0dbdcc66cd9f44b20d22db86c459bb5623f28715b350fe79cd9979aed2aa8ba"
