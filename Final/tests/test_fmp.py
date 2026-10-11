"""Fixture tests of research.fmp (factor-mimicking portfolios). Run from Final/:  python -m pytest tests -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research import fmp  # noqa: E402


def fixture(n=60, seed=0):
    rng = np.random.default_rng(seed)
    f = pd.DataFrame({"permno": np.arange(n), "group": np.tile(["A", "B", "C", "Other"], n // 4),
                      "lowvol_z": rng.normal(size=n), "momentum_z": rng.normal(size=n),
                      "npy_z": rng.normal(size=n), "size_z": rng.normal(size=n),
                      "mktcap": rng.lognormal(5, 1, n), "ret": rng.normal(0.01, 0.05, n)})
    return f


def test_fmp_unit_own_exposure_zero_others():
    f = fixture()
    X, cols = fmp.design(f, fmp.STYLES)
    P = fmp.fmp_weights(X, np.sqrt(f["mktcap"].to_numpy()))
    assert cols[:4] == fmp.STYLES and set(cols[4:]) == {"ind_A", "ind_B", "ind_C", "ind_Other"}
    assert np.allclose(P @ X, np.eye(X.shape[1]), atol=1e-10)                # unit own, zero to the rest
    w = P[: len(fmp.STYLES)]
    assert np.allclose(w.sum(axis=1), 0, atol=1e-10)                           # style FMPs are dollar-neutral
    # Composite: unit exposure to each of the three signals, zero to size and industries.
    c = fmp.composite(P, cols)
    expo = c @ X
    assert np.allclose(expo[:3], 1, atol=1e-10) and np.allclose(expo[3:], 0, atol=1e-10)


def test_wls_matches_closed_form():
    f = fixture(seed=1)
    X, _ = fmp.design(f, fmp.STYLES)
    w = np.sqrt(f["mktcap"].to_numpy())
    y = f["ret"].to_numpy()
    coef = fmp.fmp_weights(X, w) @ y
    W = np.diag(w)
    closed = np.linalg.inv(X.T @ W @ X) @ X.T @ W @ y
    sw = np.sqrt(w)
    lstsq = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
    assert np.allclose(coef, closed, atol=1e-12) and np.allclose(coef, lstsq, atol=1e-12)


def test_lagged_combination_weights():
    for K in (1, 3, 6, 12):
        for scheme in ("equal", "exponential"):
            a = fmp.lag_weights(K, scheme)
            assert len(a) == K and np.isclose(a.sum(), 1) and (a > 0).all()
        assert np.allclose(fmp.lag_weights(K, "equal"), 1 / K)
    a = fmp.lag_weights(6, "exponential")                                       # half-life K/2 = 3 months
    assert np.isclose(a[3] / a[0], 0.5) and (np.diff(a) < 0).all()
    assert np.allclose(fmp.lag_weights(1, "exponential"), [1.0])
    with pytest.raises(ValueError):
        fmp.lag_weights(3, "linear")


def test_turnover_definition():
    prev = pd.Series({1: 0.5, 2: -0.5, 3: 0.0})
    new = pd.Series({1: 0.25, 2: -0.5, 4: 0.25})
    # |0.25-0.5| + |(-0.5)-(-0.5)| + |0-0| + |0.25-0| = 0.5, one-way 0.25.
    assert np.isclose(fmp.turnover(prev, new), 0.25)
    M = np.array([[0.5, -0.5, 0.0, 0.0], [0.25, -0.5, 0.0, 0.25]])
    assert np.allclose(fmp.turnover_matrix(M), [np.nan, 0.25], equal_nan=True)


def test_active_metrics_hand():
    idx = pd.date_range("2000-01-31", periods=4, freq="ME")
    a = pd.Series([0.01, -0.02, 0.03, -0.01], index=idx)
    b = pd.Series([0.02, 0.00, 0.01, 0.03], index=idx)
    m = fmp.active_metrics(a, b)
    assert np.isclose(m["cumulative_active"], 0.01)
    assert np.isclose(m["ir"], np.sqrt(12) * a.mean() / a.std(ddof=1))
    assert np.isclose(m["max_drawdown_active"], -0.02)                          # cum path 0.01, -0.01, 0.02, 0.01
    assert np.isclose(m["corr_benchmark"], a.corr(b)) and m["months"] == 4
