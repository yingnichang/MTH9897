"""Fixture tests of research.stats (OLS with Newey-West errors). Run from Final/:  python -m pytest tests -q"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research import stats  # noqa: E402


def test_ols_alpha_recovers_known_coefficients():
    rng = np.random.default_rng(42)
    n = 5000
    idx = pd.date_range("1900-01-31", periods=n, freq="ME")
    f = pd.DataFrame(rng.normal(0, 0.04, (n, 3)), index=idx, columns=["mktrf", "smb", "hml"])
    alpha, betas = 0.004, np.array([0.9, -0.3, 0.5])
    y = pd.Series(alpha + f.to_numpy() @ betas + rng.normal(0, 0.01, n), index=idx)
    res = stats.ols(y, f, nw_lags=12)
    assert res["n"] == n
    assert abs(res["alpha_monthly"] - alpha) < 4 * res["alpha_se_nw"] / 12     # se is on the annual alpha
    assert np.isclose(res["alpha_annual"], 12 * res["alpha_monthly"])
    assert np.allclose([res["beta_mktrf"], res["beta_smb"], res["beta_hml"]], betas, atol=0.02)
    assert 0.9 < res["adj_r2"] < 1
    # Exact fit when there is no noise.
    exact = stats.ols(alpha + f @ betas, f, nw_lags=2)
    assert np.isclose(exact["alpha_monthly"], alpha) and np.allclose(exact["betas"], betas)


def test_newey_west_matches_hand_calculation():
    # Intercept only: y = [1, 2, 4, 3, 5], mean 3, residuals e = [-2, -1, 1, 0, 2].
    # Lag 1 Bartlett weight 1 - 1/2 = 0.5. S = sum e^2 + 2 * 0.5 * sum e_t e_(t-1) = 10 + 1 * 1 = 11.
    # Var(mean) = S / n^2 = 11 / 25.
    y = pd.Series([1.0, 2, 4, 3, 5], index=pd.date_range("2000-01-31", periods=5, freq="ME"))
    res = stats.ols(y, pd.DataFrame(index=y.index), nw_lags=1)
    assert np.isclose(res["alpha_monthly"], 3.0)
    assert np.isclose(res["alpha_se_nw"] / 12, math.sqrt(11 / 25))       # se reported on the annual alpha
    assert np.isclose(res["alpha_t_nw"], 3.0 / math.sqrt(11 / 25))
    ols_se = math.sqrt(10 / 4 / 5)                                       # s^2 / n with s^2 = SSR / (n - 1)
    assert np.isclose(res["alpha_t_ols"], 3.0 / ols_se)

    # One regressor, lag 2, against an explicit sandwich computed with loops.
    x = np.array([0.5, -1.0, 2.0, 0.0, 1.5, -0.5, 1.0])
    yv = np.array([1.2, -0.4, 3.1, 0.9, 2.2, 0.1, 1.8])
    X = np.column_stack([np.ones(7), x])
    b = np.linalg.solve(X.T @ X, X.T @ yv)
    e = yv - X @ b
    S = sum(e[t] ** 2 * np.outer(X[t], X[t]) for t in range(7))
    for lag, w in [(1, 1 - 1 / 3), (2, 1 - 2 / 3)]:
        for t in range(lag, 7):
            g = e[t] * e[t - lag] * np.outer(X[t], X[t - lag])
            S = S + w * (g + g.T)
    Q = np.linalg.inv(X.T @ X)
    V = Q @ S @ Q
    idx = pd.date_range("2000-01-31", periods=7, freq="ME")
    res = stats.ols(pd.Series(yv, index=idx), pd.DataFrame({"x": x}, index=idx), nw_lags=2)
    assert np.isclose(res["alpha_se_nw"] / 12, math.sqrt(V[0, 0]))
    assert np.isclose(res["se_nw"][1], math.sqrt(V[1, 1]))


def test_ols_rejects_missing_values():
    idx = pd.date_range("2000-01-31", periods=4, freq="ME")
    with pytest.raises(ValueError, match="missing"):
        stats.ols(pd.Series([1.0, np.nan, 2, 3], index=idx), pd.DataFrame({"x": [1.0, 2, 3, 4]}, index=idx))


def test_cms_net_both_legs_pays_costs():
    # Equal gross legs: a long-short spread that pays both legs' costs must lose exactly those costs.
    idx = pd.date_range("2000-01-31", periods=3, freq="ME")
    g = pd.Series([0.02, -0.01, 0.03], index=idx)
    c_cons, c_spec = pd.Series([0.001, 0.0, 0.0005], index=idx), pd.Series([0.002, 0.0, 0.0015], index=idx)
    cms = stats.cms_net_both_legs(cons_net=g - c_cons, spec_gross=g, spec_net=g - c_spec)
    assert np.allclose(cms, -(c_cons + c_spec)) and (cms <= 0).all()
    # The difference of net long-only returns would instead credit back the short leg's cost.
    assert ((g - c_cons) - (g - c_spec)).iloc[0] > 0
