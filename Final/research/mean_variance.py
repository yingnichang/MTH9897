"""Long-only convex QP with trailing 36-month covariance, 50% diagonal shrinkage.

Maximize alpha'w - (risk_aversion/2) w'Sigma_3m w - cost'|w-w_prev|.
The low-rank sample term uses 36 auxiliary variables instead of a dense 1000x1000 Hessian.
All returns in the risk window end at formation. Shrinkage and risk aversion are fixed heuristics,
introduced during the final review, not pre-registered and not tuned on a return grid.
"""
import numpy as np
import pandas as pd
from scipy import sparse
import clarabel

from research import optimize as opt


def conic_qp(P, q, A, lower, upper):
    """The identical convex QP in Clarabel's equality/nonnegative-cone format."""
    equal = np.isfinite(lower) & np.isfinite(upper) & (lower == upper)
    hi = np.isfinite(upper) & ~equal
    lo = np.isfinite(lower) & ~equal
    matrix = sparse.vstack([A[equal], A[hi], -A[lo]], format="csc")
    rhs = np.r_[upper[equal], upper[hi], -lower[lo]]
    cones = [clarabel.ZeroConeT(int(equal.sum())), clarabel.NonnegativeConeT(int(hi.sum()+lo.sum()))]
    settings = clarabel.DefaultSettings()
    settings.verbose = False
    settings.tol_gap_abs = settings.tol_gap_rel = settings.tol_feas = 1e-9
    settings.max_iter = 300
    result = clarabel.DefaultSolver(P, q, matrix, rhs, cones, settings).solve()
    if str(result.status) != "Solved": raise ValueError(f"Clarabel QP status {result.status}")
    dual = np.max(np.abs(P@np.array(result.x)+q+matrix.T@np.array(result.z)))
    return np.array(result.x), float(dual), int(result.iterations)


def solve(alpha, returns, previous, cost, groups, bounds, tau, risk_aversion=5.0, shrink=0.5):
    names = alpha.index.union(previous.index)
    in_u = names.isin(alpha.index)
    n = len(names)
    r = returns.reindex(columns=names).to_numpy(float, copy=True)
    if r.shape[0] != 36 or not np.isfinite(r[:, in_u]).all():
        raise ValueError("Risk model needs 36 complete monthly returns for each current universe member")
    # Outside-universe holdings are forced to zero: their risk coefficients cannot affect the target.
    r[:, ~in_u] = 0
    centered = r - r.mean(axis=0)
    v = np.sum(centered ** 2, axis=0) / 35
    a = alpha.reindex(names).fillna(0).to_numpy(float)
    wp = previous.reindex(names).fillna(0).to_numpy(float)
    c = cost.reindex(names).to_numpy(float)
    if not np.isfinite(c).all(): raise ValueError("Missing transaction cost")
    cap = np.where(in_u, opt.CAP, 0.0)
    b = bounds
    codes = pd.Categorical(groups.reindex(names), categories=b.index).codes
    idx = np.flatnonzero(in_u & (codes >= 0))
    g = sparse.csc_matrix((np.ones(len(idx)), (codes[idx], idx)), shape=(len(b), n))
    info = {"turnover_relaxed": False, "tau_used": tau}
    # A separate LP finds the true minimum feasible turnover; no silent constraint violation.
    mn = opt._lp(a, wp, c, cap, g, b.lo.to_numpy(), np.minimum(b.hi.to_numpy(), 1.0), None, objective=False)
    if mn.status != 0: raise ValueError(f"Mean-variance constraints infeasible: {mn.message}")
    if tau is not None and mn.fun > tau + 1e-9:
        tau = float(mn.fun) + 1e-7
        info.update(turnover_relaxed=True, tau_used=tau)
    t = 36
    I = sparse.eye(n, format="csc")
    z = sparse.csc_matrix((n, t))
    # x = [weights, absolute trades, centered sample portfolio returns]
    A = sparse.vstack([
        sparse.hstack([I, sparse.csc_matrix((n, n)), z]),
        sparse.hstack([sparse.csc_matrix((n, n)), I, z]),
        sparse.hstack([I, -I, z]), sparse.hstack([-I, -I, z]),
        sparse.hstack([sparse.csc_matrix(np.ones((1, n))), sparse.csc_matrix((1, n+t))]),
        sparse.hstack([g, sparse.csc_matrix((len(b), n+t))]),
        sparse.hstack([sparse.csc_matrix(centered), sparse.csc_matrix((t, n)), -sparse.eye(t)]),
        sparse.hstack([sparse.csc_matrix((1, n)), sparse.csc_matrix(np.ones((1, n))), sparse.csc_matrix((1, t))])
    ], format="csc")
    lower = np.r_[np.zeros(2*n), np.full(2*n, -np.inf), 1, b.lo, np.zeros(t), -np.inf]
    upper = np.r_[cap, np.full(n, np.inf), wp, -wp, 1, b.hi, np.zeros(t), np.inf if tau is None else tau]
    P = sparse.diags(np.r_[risk_aversion*3*shrink*np.maximum(v, 1e-12), np.zeros(n),
                            np.full(t, risk_aversion*3*(1-shrink)/35)], format="csc")
    q = np.r_[-a, c, np.zeros(t)]
    x, dual_residual, iterations = conic_qp(P, q, A, lower, upper)
    w = np.clip(x[:n], 0, cap)
    w[w < 1e-10] = 0
    w /= w.sum()
    turnover = np.abs(w-wp).sum()
    sector = g @ w
    violation = max(abs(w.sum()-1), float(np.maximum(w-cap, 0).max()),
                    float(np.maximum(b.lo-sector, 0).max()), float(np.maximum(sector-b.hi, 0).max()),
                    0 if tau is None else max(0, turnover-tau))
    if violation > 2e-6 or dual_residual > 1e-7:
        raise ValueError(f"QP validation failed: constraint {violation:g}, dual {dual_residual:g}")
    risk = 3*(shrink*(v*w*w).sum() + (1-shrink)*np.sum((centered@w)**2)/35)
    info.update(turnover=float(turnover), predicted_vol_annual=float(np.sqrt(4*risk)),
                max_violation=float(violation), solver_iterations=iterations,
                solver_status="solved", dual_residual=dual_residual)
    out = pd.Series(w, index=names, name="weight")
    return out[out > 0], info
