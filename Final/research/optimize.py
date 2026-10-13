"""Linear industry-constrained optimization with a turnover budget and size/volatility trading costs
(Instructions.md Trading 2 and 4). Conventions are fixed in experiments/2026-10-11-linear-optimization.

A course extension, not the paper's rule: the alpha is the diagnostic composite exposure, and the
optimized targets feed the paper's long-only engine (`research.engine.backtest`) unchanged otherwise.

At each formation, over the universe U and any held names H (w_prev, the engine's drifted weights):

    maximize   sum_i alpha_i w_i - sum_i c_i (b_i + s_i)
    subject to w = w_prev + b - s,  b, s >= 0,  sum_i w_i = 1,
               0 <= w_i <= 2% for i in U,  w_i = 0 for held names outside U (they are sold),
               lo_g <= sum_{i in g} w_i <= hi_g for each industry group g (if a band is set),
               sum_i (b_i + s_i) <= tau (if a budget is set; the initial investment has no budget).

Feasibility rules (fixed in the spec before any result): a group whose band cannot be met under the cap
(n_g x cap < B_g - delta) has its lower bound lowered to n_g x cap; a turnover budget that makes the
problem infeasible is relaxed to the minimum feasible turnover. Both are counted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linprog

CAP = 0.02
CLIP = (0.5, 5.0)


def tcost(names: pd.DataFrame, universe: pd.DataFrame, c0_bps: float, scaled: bool = True) -> pd.Series:
    """Cost per dollar traded (a fraction) for each row of `names` (columns vol36, mktcap; index permno).

    Scaled: c0 x clip((vol36 / median vol36) x sqrt(median mktcap / mktcap), 0.5, 5), medians over `universe`.
    A name missing vol36 or mktcap gets the upper clip (5 x c0). Flat: c0 for every name.
    """
    c0 = c0_bps * 1e-4
    if not scaled:
        return pd.Series(c0, index=names.index, dtype=float)
    mult = (names["vol36"] / universe["vol36"].median()) * np.sqrt(universe["mktcap"].median() / names["mktcap"])
    return (c0 * mult.clip(*CLIP).fillna(CLIP[1])).astype(float)


def industry_bounds(groups: pd.Series, mktcap: pd.Series, delta: float | None, cap: float = CAP) -> pd.DataFrame:
    """Per group: B (cap-weight share of the universe), n, lo, hi and whether lo was relaxed to n x cap.
    With delta None the band is absent (lo 0, hi inf)."""
    B = mktcap.groupby(groups).sum() / mktcap.sum()
    n = groups.value_counts().reindex(B.index)
    out = pd.DataFrame({"B": B, "n": n})
    if delta is None:
        out["lo"], out["hi"], out["relaxed"] = 0.0, np.inf, False
        return out
    lo = (B - delta).clip(lower=0)
    out["relaxed"] = n * cap < lo - 1e-15
    out["lo"] = np.where(out["relaxed"], n * cap, lo)
    out["hi"] = B + delta
    return out


def _lp(alpha, w_prev, cost, cap_ub, G, lo, hi, tau, objective=True):
    """Variables x = [w, b, s] (each N). Returns scipy's result."""
    N = len(alpha)
    I = sparse.identity(N, format="csr")
    A_eq = sparse.vstack([sparse.hstack([I, -I, I]),
                          sparse.hstack([sparse.csr_matrix(np.ones((1, N))), sparse.csr_matrix((1, 2 * N))])])
    b_eq = np.r_[w_prev, 1.0]
    rows, rhs = [], []
    if G is not None:
        Z = sparse.csr_matrix((G.shape[0], 2 * N))
        rows += [sparse.hstack([G, Z]), sparse.hstack([-G, Z])]
        rhs += [hi, -lo]
    if tau is not None:
        rows.append(sparse.hstack([sparse.csr_matrix((1, N)), sparse.csr_matrix(np.ones((1, 2 * N)))]))
        rhs.append([tau])
    A_ub = sparse.vstack(rows).tocsr() if rows else None
    b_ub = np.concatenate([np.asarray(r, float).ravel() for r in rhs]) if rows else None
    c = np.r_[-alpha, cost, cost] if objective else np.r_[np.zeros(N), np.ones(2 * N)]
    bounds = [(0, u) for u in cap_ub] + [(0, None)] * (2 * N)
    return linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq.tocsr(), b_eq=b_eq, bounds=bounds, method="highs")


def solve(alpha: pd.Series, w_prev: pd.Series, cost: pd.Series, groups: pd.Series, bounds: pd.DataFrame | None,
          tau: float | None, cap: float = CAP) -> tuple[pd.Series, dict]:
    """Optimal target weights (indexed by permno, summing to 1, zeros dropped) and solver information.

    `alpha` and `groups` are indexed by the universe; `w_prev` by held names (any, possibly empty); `cost`
    must cover the universe and the held names. `bounds` from `industry_bounds`, or None for no band.
    """
    names = alpha.index.union(w_prev.index)
    in_u = names.isin(alpha.index)
    a = alpha.reindex(names).fillna(0.0).to_numpy(float)
    wp = w_prev.reindex(names).fillna(0.0).to_numpy(float)
    c = cost.reindex(names)
    if c.isna().any():
        raise ValueError(f"No cost for {int(c.isna().sum())} names, e.g. {list(c.index[c.isna()][:5])}")
    c = c.to_numpy(float)
    cap_ub = np.where(in_u, cap, 0.0)
    G = lo = hi = None
    if bounds is not None and np.isfinite(bounds["hi"]).any():
        g = groups.reindex(names)
        codes = pd.Categorical(g, categories=bounds.index)
        rows = np.flatnonzero(in_u & (codes.codes >= 0))
        G = sparse.csr_matrix((np.ones(len(rows)), (codes.codes[rows], rows)), shape=(len(bounds), len(names)))
        lo, hi = bounds["lo"].to_numpy(float), bounds["hi"].to_numpy(float)
    info = {"names": len(names), "held_outside_universe": int((~in_u).sum()), "turnover_relaxed": False,
            "tau": tau, "tau_used": tau, "turnover_min": np.nan}
    res = _lp(a, wp, c, cap_ub, G, lo, hi, tau)
    if res.status == 2 and tau is not None:          # infeasible under the budget: relax to the minimum turnover
        mn = _lp(a, wp, c, cap_ub, G, lo, hi, None, objective=False)
        if mn.status != 0:
            raise ValueError(f"LP infeasible even without a turnover budget: {mn.message}")
        info["turnover_min"] = float(mn.fun)
        info["tau_used"] = float(mn.fun) * (1 + 1e-9) + 1e-12
        info["turnover_relaxed"] = True
        res = _lp(a, wp, c, cap_ub, G, lo, hi, info["tau_used"])
    if res.status != 0:
        raise ValueError(f"LP not solved: status {res.status}, {res.message}")
    N = len(names)
    w = np.clip(res.x[:N], 0, None)
    w = np.where(w > 1e-12, w, 0.0)
    # `turnover` is what is actually traded, sum |w - w_prev| (the engine's traded notional). The LP's own
    # sum (b + s) agrees only to the solver's feasibility tolerance (about 1e-7); both are reported.
    info.update(status="optimal", turnover=float(np.abs(w - wp).sum()), turnover_lp=float(res.x[N:].sum()),
                objective=float(-res.fun), alpha_exposure=float(a @ w))
    out = pd.Series(w, index=names, name="weight")
    out.index.name = "permno"
    return out.loc[out > 0], info


def trailing_ic(ic: pd.Series, h: int, min_obs: int = 12) -> pd.Series:
    """At each date t, the mean of the IC series over formations f with f + h months <= t (horizons already
    complete, so no look-ahead); NaN when fewer than `min_obs` are available."""
    ic = ic.sort_index()
    done = ic.index + pd.offsets.MonthEnd(h)
    out = {}
    for t in ic.index:
        past = ic.loc[done <= t]
        out[t] = float(past.mean()) if len(past) >= min_obs else np.nan
    return pd.Series(out)


def grinold_alpha(z: pd.Series, vol36: pd.Series, ic: float, h: int = 3) -> pd.Series:
    """Expected h-month residual return: IC x sigma_h x z; vol36 is annualized, so sigma_h = vol36 sqrt(h/12)."""
    return ic * vol36 * np.sqrt(h / 12) * z
