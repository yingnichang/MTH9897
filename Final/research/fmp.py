"""Factor-mimicking portfolios (Instructions.md 7D-F). Conventions are fixed in
experiments/2026-10-11-factor-mimicking (before any result).

At each month-end: WLS of next-month returns on the neutralized style exposures (lowvol, momentum, npy, size)
and a full set of industry dummies (no intercept), weights sqrt(mktcap). The FMP weights are the rows of
(X'WX)^-1 X'W: each style FMP has unit exposure to its own style and zero to the other styles and to every
industry (so it is dollar-neutral), and its return is the WLS coefficient.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STYLES = ["lowvol_z", "momentum_z", "npy_z", "size_z"]
SIGNAL_STYLES = ["lowvol_z", "momentum_z", "npy_z"]


def design(frame: pd.DataFrame, styles=STYLES, group: str = "group") -> tuple[np.ndarray, list[str]]:
    """Columns: the style exposures, then one dummy per industry group present (no intercept)."""
    groups = sorted(frame[group].unique())
    dummies = (frame[group].to_numpy()[:, None] == np.array(groups)[None, :]).astype(float)
    X = np.column_stack([frame[list(styles)].to_numpy(float), dummies])
    return X, list(styles) + [f"ind_{g}" for g in groups]


def fmp_weights(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """P = (X'WX)^-1 X'W (k x n), W = diag(w). P @ X = I; P @ y is the WLS coefficient vector."""
    XtW = X.T * w
    return np.linalg.solve(XtW @ X, XtW)


def composite(P: np.ndarray, cols: list[str]) -> np.ndarray:
    """Equal-weight sum of the three signal FMPs: unit exposure to each signal (so to their mean), zero to
    size and industries."""
    return sum(P[cols.index(c)] for c in SIGNAL_STYLES)


def lag_weights(K: int, scheme: str) -> np.ndarray:
    """Weights a_1..a_K on the composites formed 1..K months before the holding month: equal (1/K), or
    exponential decay with half-life K/2 (a_k proportional to 0.5^((k-1)/(K/2))). They sum to 1."""
    if scheme == "equal":
        a = np.ones(K)
    elif scheme == "exponential":
        a = 0.5 ** (np.arange(K) / (K / 2))
    else:
        raise ValueError(f"unknown weighting scheme {scheme!r}")
    return a / a.sum()


def turnover(prev: pd.Series, new: pd.Series) -> float:
    """One-way turnover 0.5 x sum |new - prev| over the union of names (a missing name has weight 0)."""
    keys = prev.index.union(new.index)
    return 0.5 * float((new.reindex(keys, fill_value=0) - prev.reindex(keys, fill_value=0)).abs().sum())


def turnover_matrix(M: np.ndarray) -> np.ndarray:
    """Row-by-row one-way turnover of a (months x names) weight matrix; the first row has none (NaN)."""
    out = np.full(M.shape[0], np.nan)
    out[1:] = 0.5 * np.abs(np.diff(M, axis=0)).sum(axis=1)
    return out


def active_metrics(active: pd.Series, bench: pd.Series) -> dict:
    """Metrics of a monthly active (overlay) return. Cumulative active return is the running sum (an overlay
    on the benchmark); its drawdown is measured on that additive path from a starting value of 0."""
    a = active.dropna()
    cum = a.cumsum()
    peak = np.maximum.accumulate(np.r_[0.0, cum.to_numpy()])[1:]
    sd = float(a.std(ddof=1))
    return {"months": len(a), "first": a.index.min().date(), "last": a.index.max().date(),
            "mean_annual": float(12 * a.mean()), "vol_annual": float(np.sqrt(12) * sd),
            "cumulative_active": float(cum.iloc[-1]), "ir": float(np.sqrt(12) * a.mean() / sd) if sd > 0 else np.nan,
            "max_drawdown_active": float((cum.to_numpy() - peak).min()),
            "skew": float(a.skew()), "excess_kurtosis": float(a.kurt()),
            "corr_benchmark": float(a.corr(bench.reindex(a.index)))}
