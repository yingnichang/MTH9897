"""Time-series regressions for factor attribution: OLS with Newey-West (HAC) standard errors, numpy only.

Conventions (experiments/2026-10-10-factor-attribution, fixed before any regression was run):
- monthly OLS of an excess return on factor returns, with an intercept (alpha);
- alpha annualized as 12 x alpha; its standard errors and CI are scaled the same way;
- Newey-West covariance with Bartlett weights 1 - l/(L+1), l = 1..L, no small-sample adjustment
  (12 lags in the study); the plain OLS t-statistic (s^2 = SSR/(n - k)) is reported alongside, labeled.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Z95 = 1.959963984540054


def newey_west_cov(X: np.ndarray, e: np.ndarray, lags: int) -> np.ndarray:
    """(X'X)^-1 S (X'X)^-1 with S = sum e_t^2 x_t x_t' + sum_l w_l sum_t e_t e_(t-l) (x_t x_(t-l)' + x_(t-l) x_t')."""
    xe = X * e[:, None]
    S = xe.T @ xe
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        g = xe[lag:].T @ xe[:-lag]
        S += w * (g + g.T)
    Q = np.linalg.inv(X.T @ X)
    return Q @ S @ Q


def ols(y: pd.Series, factors: pd.DataFrame, nw_lags: int = 12) -> dict:
    """Regress y on a constant and `factors` (aligned on the index; no missing values allowed)."""
    data = pd.concat([y.rename("_y"), factors], axis=1, join="inner")
    if data.isna().any().any() or len(data) != len(y):
        raise ValueError("ols: y and factors must be aligned with no missing values")
    yv = data["_y"].to_numpy(float)
    names = list(factors.columns)
    X = np.column_stack([np.ones(len(yv)), data[names].to_numpy(float)]) if names else np.ones((len(yv), 1))
    n, k = X.shape
    b, *_ = np.linalg.lstsq(X, yv, rcond=None)
    e = yv - X @ b
    ssr = float(e @ e)
    sst = float(((yv - yv.mean()) ** 2).sum())
    se_ols = np.sqrt(np.diag(ssr / (n - k) * np.linalg.inv(X.T @ X))) if n > k else np.full(k, np.nan)
    se_nw = np.sqrt(np.diag(newey_west_cov(X, e, nw_lags)))
    r2 = 1 - ssr / sst if sst > 0 else np.nan
    out = {"n": n, "first": data.index.min().date(), "last": data.index.max().date(),
           "alpha_monthly": float(b[0]), "alpha_annual": float(12 * b[0]),
           "alpha_se_nw": float(12 * se_nw[0]), "alpha_t_nw": float(b[0] / se_nw[0]) if se_nw[0] > 0 else np.nan,
           "alpha_t_ols": float(b[0] / se_ols[0]) if se_ols[0] > 0 else np.nan,
           "alpha_ci95_low": float(12 * (b[0] - Z95 * se_nw[0])), "alpha_ci95_high": float(12 * (b[0] + Z95 * se_nw[0])),
           "adj_r2": float(1 - (1 - r2) * (n - 1) / (n - k)) if names and n > k else np.nan,
           "betas": b[1:], "se_nw": se_nw, "factors": names}
    for name, beta in zip(names, b[1:]):
        out[f"beta_{name}"] = float(beta)
    return out


# Factor models (decisions.md: Carhart is the primary alpha; FF5 + UMD is the robustness check and
# uses the FF5 file's own market and SMB; it exists from 1963-07 only).
MODELS = {
    "CAPM": ["mktrf"],
    "FF3": ["mktrf", "smb", "hml"],
    "Carhart": ["mktrf", "smb", "hml", "umd"],
    "FF5+UMD": ["mktrf_ff5", "smb_ff5", "hml", "rmw", "cma", "umd"],
}


def cms_net_both_legs(cons_net: pd.Series, spec_gross: pd.Series, spec_net: pd.Series) -> pd.Series:
    """Cost-inclusive long-short CMS (decisions.md, 2026-10-11): long Conservative, short Speculative, each leg
    paying its own trading cost (cost = engine gross - net). Shorting earns -Spec_gross - cost_spec, so
    CMS_net = Cons_net - Spec_gross - (Spec_gross - Spec_net). Borrow and financing costs are not modeled."""
    return cons_net - 2 * spec_gross + spec_net


def left_side(name: str, returns: dict[str, pd.Series], rf: pd.Series) -> pd.Series:
    """Excess return R - rf for a portfolio. CMS is a zero-investment return with no rf subtracted: the
    series under key "CMS" if given (e.g. the cost-inclusive spread), else R_Conservative - R_Speculative."""
    if name == "CMS":
        return returns["CMS"] if "CMS" in returns else returns["Conservative"] - returns["Speculative"]
    return returns[name] - rf.reindex(returns[name].index)


def attribute(returns: dict[str, pd.Series], factors: pd.DataFrame, rf: pd.Series,
              portfolios=("Conservative", "Speculative", "CMS"), models=tuple(MODELS), nw_lags: int = 12,
              label: dict | None = None) -> pd.DataFrame:
    """One row per portfolio x model: annual alpha, NW and OLS t, NW 95% CI, betas, adjusted R^2, N.

    Each regression uses the months in which the return and all of the model's factors exist (FF5 + UMD
    therefore starts at 1963-07). `factors` is indexed by month end.
    """
    rows = []
    for p in portfolios:
        y = left_side(p, returns, rf).dropna()
        for m in models:
            f = factors.reindex(y.index)[MODELS[m]].dropna()
            res = ols(y.loc[f.index], f, nw_lags)
            row = {**(label or {}), "portfolio": p, "model": m}
            row.update({k: res[k] for k in ["alpha_annual", "alpha_se_nw", "alpha_t_nw", "alpha_t_ols",
                                            "alpha_ci95_low", "alpha_ci95_high", "adj_r2", "n", "first", "last"]})
            row.update({f"beta_{c}": res[f"beta_{c}"] for c in MODELS[m]})
            rows.append(row)
    return pd.DataFrame(rows)
