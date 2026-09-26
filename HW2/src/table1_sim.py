"""Monte Carlo engine for Table 1 of Bessembinder (2018), "Do Stocks Outperform Treasury Bills?".

Single-period simple returns are i.i.d. normal, r ~ N(mu, sigma^2), and buy-and-hold gross
wealth over T periods is W_T = prod(1 + r_t). This is a literal interpretation of the paper's
stated assumptions: a draw below -100% produces a negative gross return and is counted, not
clipped. The paper does not document how it treats such draws, so absorbing bankruptcy is
available as a sensitivity.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd

# Roughly 32 MB of float64 per chunk.
DEFAULT_CHUNK_ELEMENTS = 4_000_000


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")


def _require_positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")


def _require_volatility(sigma: float) -> None:
    _require_finite("sigma", sigma)
    if sigma < 0.0:
        raise ValueError(f"sigma must be nonnegative, got {sigma}")


def exact_moments(mu: float, sigma: float, n_periods: int) -> tuple[float, float, float, float]:
    """Exact mean, standard deviation, skewness and kurtosis of the n-period buy-and-hold return.

    These are population benchmarks for the literal (unclipped) normal-return model. With
    a = 1 + mu the raw moments of W_T are E[W] = a^T, E[W^2] = (a^2 + sigma^2)^T,
    E[W^3] = (a^3 + 3 a sigma^2)^T and E[W^4] = (a^4 + 6 a^2 sigma^2 + 3 sigma^4)^T. They are
    rewritten through u, v, w = E[W^k]/E[W]^k - 1 for k = 2, 3, 4, which gives
    skewness = (v - 3u) / u^1.5 and kurtosis = (w - 4v + 6u) / u^2 (not excess kurtosis)
    without the cancellation the raw-moment form suffers at low volatility. Skewness and
    kurtosis are NaN when sigma = 0. Requires mu > -1.
    """
    _require_finite("mu", mu)
    if mu <= -1.0:
        raise ValueError(f"mu must exceed -1, got {mu}")
    _require_volatility(sigma)
    _require_positive_int("n_periods", n_periods)

    a = 1.0 + mu
    mean_gross = a**n_periods
    x = (sigma / a) ** 2
    u = math.expm1(n_periods * math.log1p(x))
    v = math.expm1(n_periods * math.log1p(3.0 * x))
    w = math.expm1(n_periods * math.log1p(6.0 * x + 3.0 * x * x))
    sd = mean_gross * math.sqrt(u)
    if u == 0.0:
        return mean_gross - 1.0, sd, math.nan, math.nan
    return mean_gross - 1.0, sd, (v - 3.0 * u) / u**1.5, (w - 4.0 * v + 6.0 * u) / u**2


def _is_constant(x: np.ndarray) -> bool:
    # Compared before centering: subtracting a rounded mean from identical values can leave a
    # tiny nonzero residual that would otherwise produce a skewness of exactly +1 or -1.
    return bool(np.all(x == x[0]))


def sample_skewness(x: np.ndarray) -> float:
    """Standardized sample skewness m3 / m2^1.5 using population (biased) central moments.

    NaN for empty samples and for samples whose observations are all identical.
    """
    if x.size == 0 or _is_constant(x):
        return math.nan
    d = x - x.mean()
    m2 = np.mean(d * d)
    return float(np.mean(d * d * d) / m2**1.5)


def max_sample_skewness(n_obs: int) -> float:
    """Largest value sample_skewness can take on n_obs observations, (n - 2) / sqrt(n - 1).

    It is attained by one outlier among n - 1 equal values, and it is a property of this
    estimator at this sample size: a population skewness near or above it cannot be recovered
    from n_obs draws, and averaging the statistic across seeds does not lift the ceiling.
    Pooling more draws raises it (roughly as sqrt(n)), but a value below the bound is not
    evidence of accuracy, because rare tail draws make convergence very slow. NaN for n_obs < 2.
    """
    if n_obs < 2:
        return math.nan
    return (n_obs - 2) / math.sqrt(n_obs - 1)


def simulate_wealth(
    mu: float,
    sigma: float,
    n_paths: int,
    n_periods: int,
    *,
    block_lengths: Iterable[int] = (),
    prefix_lengths: Iterable[int] = (),
    seed: int | np.random.SeedSequence = 0,
    absorbing: bool = False,
    chunk_elements: int = DEFAULT_CHUNK_ELEMENTS,
) -> tuple[dict[tuple[str, int], np.ndarray], int]:
    """Simulate n_paths paths of n_periods normal returns and collect buy-and-hold gross wealth.

    block_lengths: non-overlapping blocks of L consecutive periods within every path (L must
        divide n_periods), giving n_paths * n_periods / L observations for each L. Each block
        is a separate buy-and-hold investment.
    prefix_lengths: wealth after the first k periods of every path, giving n_paths
        observations for each k. Different k share their early draws.
    seed: passing the same seed for different sigmas (or mus) reuses the same standard normal
        draws (common random numbers), which reduces, but does not eliminate, sampling noise
        in comparisons across the grid. Results do not depend on chunk_elements.
    absorbing: if True, a draw below -100% is replaced by a -100% return, so the block or
        prefix investment containing it ends with zero wealth. Blocks are separate
        investments, so later blocks of the same path are unaffected.

    Returns (wealth, n_below) where wealth maps ("block", L) or ("prefix", k) to a 1-D array
    of gross wealth, and n_below counts single-period draws below -100% among all
    n_paths * n_periods draws (counted whether or not absorbing is set).
    """
    _require_finite("mu", mu)
    _require_volatility(sigma)
    _require_positive_int("n_paths", n_paths)
    _require_positive_int("n_periods", n_periods)
    _require_positive_int("chunk_elements", chunk_elements)
    blocks = sorted(set(block_lengths))
    prefixes = sorted(set(prefix_lengths))
    for length in blocks:
        _require_positive_int("block length", length)
        if n_periods % length:
            raise ValueError(f"block length {length} must divide n_periods={n_periods}")
    for length in prefixes:
        _require_positive_int("prefix length", length)
        if length > n_periods:
            raise ValueError(f"prefix length {length} exceeds n_periods={n_periods}")

    wealth = {("block", L): np.empty(n_paths * (n_periods // L)) for L in blocks}
    wealth.update({("prefix", k): np.empty(n_paths) for k in prefixes})

    rng = np.random.default_rng(seed)
    rows_per_chunk = max(1, chunk_elements // n_periods)
    n_below = 0
    for start in range(0, n_paths, rows_per_chunk):
        rows = min(rows_per_chunk, n_paths - start)
        gross = rng.standard_normal((rows, n_periods))
        gross *= sigma
        gross += 1.0 + mu
        n_below += int(np.count_nonzero(gross < 0.0))
        if absorbing:
            np.maximum(gross, 0.0, out=gross)
        for L in blocks:
            per_path = n_periods // L
            wealth[("block", L)][start * per_path : (start + rows) * per_path] = (
                gross.reshape(rows, per_path, L).prod(axis=2).ravel()
            )
        for k in prefixes:
            wealth[("prefix", k)][start : start + rows] = gross[:, :k].prod(axis=1)
    return wealth, n_below


def summarize_returns(returns: np.ndarray) -> dict[str, float]:
    """Table 1 statistics (plus mean and sd for validation) of a sample of buy-and-hold returns.

    For identical observations sd is 0 and skewness is NaN; for a single observation sd is NaN.
    """
    if returns.size == 0:
        raise ValueError("cannot summarize an empty sample")
    if returns.size == 1:
        sd = math.nan
    elif _is_constant(returns):
        sd = 0.0
    else:
        sd = float(returns.std(ddof=1))
    return {
        "n_obs": returns.size,
        "mean": float(returns.mean()),
        "sd": sd,
        "skew": sample_skewness(returns),
        "median": float(np.median(returns)),
        "pct_positive": float(np.mean(returns > 0.0)),
        "p99": float(np.quantile(returns, 0.99)),
    }


def run_grid(
    mu: float,
    sigmas: Iterable[float],
    n_paths: int,
    n_periods: int,
    *,
    block_lengths: Iterable[int] = (),
    prefix_lengths: Iterable[int] = (),
    seed: int = 0,
    absorbing: bool = False,
    periods_per_year: int = 12,
    chunk_elements: int = DEFAULT_CHUNK_ELEMENTS,
) -> pd.DataFrame:
    """Simulate every sigma with common random numbers; one row per (sigma, horizon).

    Each row is self-describing when exported: the return model ("literal" or "absorbing"),
    the seed, path count, periods per path and total draws for that sigma; the simulated
    statistics; the exact mean, sd, skewness and kurtosis of the unclipped model (a
    reference, not the population values of the absorbing model); the sample-skewness bound for that sample
    size; and the count of draws below -100% among the n_draws draws of that sigma, which is
    shared by all horizons of the same sigma.
    """
    _require_positive_int("periods_per_year", periods_per_year)
    block_lengths, prefix_lengths = tuple(block_lengths), tuple(prefix_lengths)
    run_info = {
        "return_model": "absorbing" if absorbing else "literal",
        "seed": seed,
        "n_paths": n_paths,
        "n_periods": n_periods,
        "n_draws": n_paths * n_periods,
    }
    rows = []
    for sigma in sigmas:
        wealth, n_below = simulate_wealth(
            mu,
            sigma,
            n_paths,
            n_periods,
            block_lengths=block_lengths,
            prefix_lengths=prefix_lengths,
            seed=seed,
            absorbing=absorbing,
            chunk_elements=chunk_elements,
        )
        for (sampling, length), gross in wealth.items():
            exact_mean, exact_sd, exact_skew, exact_kurt = exact_moments(mu, sigma, length)
            rows.append(
                {
                    "mu": mu,
                    "sigma": sigma,
                    "horizon_periods": length,
                    "horizon_years": length / periods_per_year,
                    "sampling": sampling,
                    **run_info,
                    **summarize_returns(gross - 1.0),
                    "unclipped_exact_mean": exact_mean,
                    "unclipped_exact_sd": exact_sd,
                    "unclipped_exact_skew": exact_skew,
                    "unclipped_exact_kurt": exact_kurt,
                    "skew_bound": max_sample_skewness(gross.size),
                    "n_below_minus_one": n_below,
                }
            )
    return pd.DataFrame(rows)


def run_seeds(seeds: Iterable[int], mu: float, sigmas: Iterable[float], n_paths: int,
              n_periods: int, **kwargs) -> pd.DataFrame:
    """run_grid once per seed, stacked into one long table (the seed column tells them apart)."""
    sigmas = tuple(sigmas)
    return pd.concat(
        [run_grid(mu, sigmas, n_paths, n_periods, seed=seed, **kwargs) for seed in seeds],
        ignore_index=True,
    )
