"""Table 4 strategies on industry portfolios.

Random industry selection (Task 2.1): each month, one industry is drawn uniformly from
that month's eligible set, independently across months and paths. The draws are generated once
per universe as an explicit (paths x months) array of column positions, and the same array is
applied to equal- and value-weighted returns, which share one eligible universe. The algorithm is
fixed so a seed reproduces every draw:

    rng = np.random.default_rng(seed)
    k = rng.integers(0, counts, size=(n_paths, n_months))   # counts[t] = |A_t|
    selection[p, t] = the k[p, t]-th eligible column of month t, in the declared column order

A selection is never dropped or redrawn using holding-month information: an ineligible selection
or a selected industry without a return raises.

Momentum (Task 2.2): each month t, hold the industry with the highest compounded return
over months t-3 to t-1, among industries that are formation-eligible in month t and have all
three lookback returns. Ties go to the lowest position in the declared column order. The score
never uses month t, so a holding-month return cannot affect that month's selection.
"""

from __future__ import annotations

import hashlib
from statistics import NormalDist

import numpy as np
import pandas as pd


class SelectionError(ValueError):
    """A selection array breaks the random-selection rule."""


def eligible_positions(eligible: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Per month, the number of eligible industries and their column positions (declared order, padded with -1)."""
    mask = eligible.to_numpy(dtype=bool)
    counts = mask.sum(axis=1)
    if (counts == 0).any():
        raise SelectionError(f"no eligible industry in {eligible.index[np.argmax(counts == 0)]}")
    # A stable sort of "not eligible" puts eligible columns first, in their declared order.
    order = np.argsort(~mask, axis=1, kind="stable")
    positions = np.where(np.arange(mask.shape[1])[None, :] < counts[:, None], order, -1)
    return counts, positions


def random_selections(eligible: pd.DataFrame, n_paths: int, seed: int) -> np.ndarray:
    """(paths x months) column positions of one uniformly drawn eligible industry per month (module docstring)."""
    if n_paths < 1:
        raise ValueError("n_paths must be positive")
    counts, positions = eligible_positions(eligible)
    rng = np.random.default_rng(seed)
    k = rng.integers(0, counts, size=(n_paths, len(counts)))
    selections = positions[np.arange(len(counts))[None, :], k]
    return selections.astype(np.int16)


def selection_fingerprint(selections: np.ndarray) -> str:
    """SHA-256 of a selection array's shape, dtype and bytes, recorded with the results."""
    digest = hashlib.sha256(f"{selections.shape}{selections.dtype}".encode())
    digest.update(np.ascontiguousarray(selections).tobytes())
    return digest.hexdigest()


def selected_returns(returns: pd.DataFrame, eligible: pd.DataFrame, selections: np.ndarray) -> pd.DataFrame:
    """Months x paths returns of the selected industries; raises on an ineligible selection or a missing return."""
    if not (returns.index.equals(eligible.index) and returns.columns.equals(eligible.columns)):
        raise ValueError("returns and eligibility must share months and column order")
    n_months = len(returns)
    if selections.ndim != 2 or selections.shape[1] != n_months:
        raise ValueError(f"selections must be (paths x {n_months} months), got {selections.shape}")
    rows = np.arange(n_months)[None, :]
    if selections.min() < 0 or selections.max() >= returns.shape[1]:
        raise SelectionError("a selection is not a valid column position")
    if not eligible.to_numpy(dtype=bool)[rows, selections].all():
        raise SelectionError("an ineligible industry was selected")
    values = returns.to_numpy(dtype=float)[rows, selections]
    if not np.isfinite(values).all():
        raise SelectionError("a selected industry has no holding-month return; the run stops for investigation")
    return pd.DataFrame(values.T, index=returns.index)


def selection_frequency_check(selections: np.ndarray, eligible: pd.DataFrame, family_alpha: float = 0.001,
                              z_floor: float = 4.0) -> pd.DataFrame:
    """How often each industry is selected, against uniform selection from the eligible sets.

    For industry i the expected count is n sum_t 1{i in A_t} / |A_t| and, since draws are independent,
    the variance is n sum_t p_t (1 - p_t) with p_t = 1 / |A_t|. The z limit is a nominal Bonferroni
    level across industries (never below z_floor). Selections of ineligible industries are counted
    separately and must be zero.
    """
    counts, _ = eligible_positions(eligible)
    mask = eligible.to_numpy(dtype=bool)
    n_paths, n_months = selections.shape
    n_cols = mask.shape[1]
    cells = np.bincount((np.arange(n_months)[None, :] * n_cols + selections).ravel(), minlength=n_months * n_cols)
    cells = cells.reshape(n_months, n_cols)
    p = np.where(mask, 1.0 / counts[:, None], 0.0)
    expected = n_paths * p.sum(axis=0)
    sd = np.sqrt(n_paths * (p * (1 - p)).sum(axis=0))
    observed = cells.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(sd > 0, (observed - expected) / sd, np.where(observed == expected, 0.0, np.inf))
    limit = max(z_floor, NormalDist().inv_cdf(1 - family_alpha / (2 * n_cols)))
    table = pd.DataFrame({"industry": eligible.columns, "months_eligible": mask.sum(axis=0), "selected": observed,
                          "expected": expected, "z": z, "ineligible_selections": (cells * ~mask).sum(axis=0)})
    table["z_limit"] = limit
    table["ok"] = (table["z"].abs() <= limit) & (table["ineligible_selections"] == 0)
    return table


def require_uniform_selections(table: pd.DataFrame) -> pd.DataFrame:
    failed = table[~table["ok"]]
    if len(failed):
        raise SelectionError("selection frequencies are not consistent with uniform selection:\n"
                             + failed.to_string(index=False))
    return table


# ----------------------------------------------------------------------------------------------
# Step 10: momentum


def _require_monthly(frame: pd.DataFrame) -> None:
    index = frame.index
    if not isinstance(index, pd.PeriodIndex) or index.freqstr != "M" or (np.diff(index.asi8) != 1).any():
        raise ValueError("returns must be indexed by consecutive monthly periods")


def momentum_scores(returns: pd.DataFrame, lookback: int = 3) -> pd.DataFrame:
    """s_{i,t} = prod_{j=1..lookback} (1 + r_{i,t-j}) - 1, the compounded return over the lookback months
    before t; month t itself is never used. NaN unless every lookback return exists."""
    if lookback < 1:
        raise ValueError("lookback must be at least one month")
    _require_monthly(returns)
    gross = 1.0 + returns.to_numpy(dtype=float)
    score = np.ones_like(gross)
    for j in range(1, lookback + 1):
        lagged = np.full_like(gross, np.nan)
        lagged[j:] = gross[:-j]
        score = score * lagged
    return pd.DataFrame(score - 1.0, index=returns.index, columns=returns.columns)


def momentum_candidates(returns: pd.DataFrame, eligible: pd.DataFrame, lookback: int = 3) -> pd.DataFrame:
    """Industries that can be ranked in each month: formation-eligible then, with all `lookback` earlier returns."""
    if not (returns.index.equals(eligible.index) and returns.columns.equals(eligible.columns)):
        raise ValueError("returns and eligibility must share months and column order")
    scores = momentum_scores(returns, lookback)
    return eligible.astype(bool) & scores.notna()


def momentum_selections(returns: pd.DataFrame, eligible: pd.DataFrame, start, lookback: int = 3) -> pd.Series:
    """Column position of the industry held each month from `start` (module docstring).

    Ties go to the lowest declared position, which is what argmax returns. A month without any
    candidate raises, because argmax over all -inf scores would silently pick the first column.
    """
    candidates = momentum_candidates(returns, eligible, lookback).loc[start:]
    scores = momentum_scores(returns, lookback).loc[start:]
    empty = ~candidates.to_numpy().any(axis=1)
    if empty.any():
        raise SelectionError(f"no industry can be ranked for {scores.index[np.argmax(empty)]}")
    values = np.where(candidates.to_numpy(), scores.to_numpy(), -np.inf)
    return pd.Series(values.argmax(axis=1), index=scores.index, name="position")


def held_returns(returns: pd.DataFrame, eligible: pd.DataFrame, positions: pd.Series) -> pd.Series:
    """Return of the held industry each month; raises on an ineligible holding or a missing return."""
    index = positions.index
    held = selected_returns(returns.loc[index], eligible.loc[index], positions.to_numpy()[None, :])
    return held.iloc[:, 0].rename("return")


def position_weights(positions: pd.Series, columns: pd.Index) -> pd.DataFrame:
    """Target weights of a one-industry strategy: 1 on the held industry, 0 elsewhere."""
    weights = np.zeros((len(positions), len(columns)))
    weights[np.arange(len(positions)), positions.to_numpy()] = 1.0
    return pd.DataFrame(weights, index=positions.index, columns=columns)


# ----------------------------------------------------------------------------------------------
# Step 11: bonus rules


def top_k_weights(returns: pd.DataFrame, eligible: pd.DataFrame, start, lookback: int = 6, k: int = 5) -> pd.DataFrame:
    """Equal weights on the k candidates with the highest lookback return, each month from `start`.

    Candidates are as in momentum_candidates (formation-eligible, all `lookback` earlier returns),
    so month t's return never enters month t's selection. A stable sort on the negated scores puts
    ties in the declared column order, so with k = 1 this is momentum_selections. A month with fewer
    than k candidates raises.
    """
    if k < 1:
        raise ValueError("k must be at least one")
    candidates = momentum_candidates(returns, eligible, lookback).loc[start:]
    scores = momentum_scores(returns, lookback).loc[start:]
    short = candidates.to_numpy().sum(axis=1) < k
    if short.any():
        raise SelectionError(f"fewer than {k} rankable industries in {scores.index[np.argmax(short)]}")
    values = np.where(candidates.to_numpy(), scores.to_numpy(), -np.inf)
    top = np.argsort(-values, axis=1, kind="stable")[:, :k]
    weights = np.zeros(values.shape)
    np.put_along_axis(weights, top, 1.0 / k, axis=1)
    return pd.DataFrame(weights, index=scores.index, columns=returns.columns)


def equal_industry_weights(eligible: pd.DataFrame, start=None) -> pd.DataFrame:
    """Equal weights across all formation-eligible industries each month (rule a)."""
    mask = eligible.loc[start:].astype(float)
    counts = mask.sum(axis=1)
    if (counts == 0).any():
        raise SelectionError(f"no eligible industry in {mask.index[np.argmax(counts.to_numpy() == 0)]}")
    return mask.div(counts, axis=0)


def portfolio_returns(weights: pd.DataFrame, returns: pd.DataFrame, eligible: pd.DataFrame) -> pd.Series:
    """Monthly return of target weights; raises if a held industry is ineligible or has no return."""
    index = weights.index
    if not (weights.columns.equals(returns.columns) and weights.columns.equals(eligible.columns)):
        raise ValueError("weights, returns and eligibility must share the column order")
    w = weights.to_numpy(dtype=float)
    if (w < 0).any() or not np.allclose(w.sum(axis=1), 1.0, rtol=0, atol=1e-12):
        raise ValueError("weights must be non-negative and sum to one each month")
    held = w > 0
    if not eligible.loc[index].to_numpy(dtype=bool)[held].all():
        raise SelectionError("an ineligible industry is held")
    r = returns.loc[index].to_numpy(dtype=float)
    if not np.isfinite(r[held]).all():
        raise SelectionError("a held industry has no holding-month return; the run stops for investigation")
    return pd.Series((w * np.where(held, r, 0.0)).sum(axis=1), index=index, name="return")
