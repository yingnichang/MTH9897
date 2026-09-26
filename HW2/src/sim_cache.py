"""Cached Table 1 simulation runs: a CSV of run_seeds output plus a JSON description of the run.

A cache is reused only if its JSON matches the requested experiment exactly (seeds, mean,
volatility grid, path count and length, horizons, return model) and names the same simulator
source fingerprint and schema version; if the CSV still has the SHA-256 recorded when it was
written; and if the CSV holds exactly the expected grid of unique rows with derived columns
(observation counts, horizons in years, draw counts, exact moments, skewness bound) that agree
with the run's parameters. Anything else raises CacheMismatch; pass refresh=True to recompute.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

import table1_sim

SCHEMA_VERSION = 1
SIMULATOR_SOURCE = Path(table1_sim.__file__)

REQUIRED_COLUMNS = [
    "mu", "sigma", "horizon_periods", "horizon_years", "sampling", "return_model", "seed",
    "n_paths", "n_periods", "n_draws", "n_obs", "mean", "sd", "skew", "median", "pct_positive",
    "p99", "unclipped_exact_mean", "unclipped_exact_sd", "unclipped_exact_skew",
    "unclipped_exact_kurt", "skew_bound", "n_below_minus_one",
]


class CacheMismatch(ValueError):
    """A cached simulation does not match the requested experiment."""


def simulator_fingerprint(source: Path = SIMULATOR_SOURCE) -> str:
    """SHA-256 of the simulator source with line endings normalized, so any edit invalidates caches."""
    return hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def experiment_config(
    *,
    seeds: Iterable[int],
    mu: float,
    sigmas: Iterable[float],
    n_paths: int,
    n_periods: int,
    block_lengths: Iterable[int] = (),
    prefix_lengths: Iterable[int] = (),
    absorbing: bool = False,
    periods_per_year: int = 12,
) -> dict:
    """JSON-ready description of a run_seeds call, used as the cache key."""
    return {
        "schema_version": SCHEMA_VERSION,
        "simulator_sha256": simulator_fingerprint(),
        "seeds": sorted(int(s) for s in seeds),
        "mu": float(mu),
        "sigmas": [float(s) for s in sigmas],
        "n_paths": int(n_paths),
        "n_periods": int(n_periods),
        "block_lengths": sorted({int(L) for L in block_lengths}),
        "prefix_lengths": sorted({int(k) for k in prefix_lengths}),
        "return_model": "absorbing" if absorbing else "literal",
        "periods_per_year": int(periods_per_year),
    }


def validate_table(table: pd.DataFrame, config: dict) -> None:
    """Raise CacheMismatch unless table is exactly the grid config asks for."""
    missing = [c for c in REQUIRED_COLUMNS if c not in table.columns]
    if missing:
        raise CacheMismatch(f"missing columns: {missing}")
    horizons = [("block", L) for L in config["block_lengths"]] + [("prefix", k) for k in config["prefix_lengths"]]
    expected_rows = len(config["seeds"]) * len(config["sigmas"]) * len(horizons)
    if len(table) != expected_rows:
        raise CacheMismatch(f"expected {expected_rows} rows, found {len(table)}")
    if table.duplicated(["seed", "sigma", "sampling", "horizon_periods"]).any():
        raise CacheMismatch("duplicate (seed, sigma, sampling, horizon) rows")
    if sorted(table["seed"].unique().tolist()) != config["seeds"]:
        raise CacheMismatch("seeds differ from the requested run")
    if sorted(table["sigma"].round(10).unique().tolist()) != sorted(round(s, 10) for s in config["sigmas"]):
        raise CacheMismatch("volatility grid differs from the requested run")
    found = sorted(set(zip(table["sampling"], table["horizon_periods"].astype(int))))
    if found != sorted(horizons):
        raise CacheMismatch(f"horizons differ: found {found}, expected {sorted(horizons)}")
    for column in ("mu", "n_paths", "n_periods", "return_model"):
        values = table[column].unique().tolist()
        if len(values) != 1 or values[0] != config[column]:
            raise CacheMismatch(f"{column} is {values}, expected {config[column]!r}")
    _validate_derived(table, config)


def _validate_derived(table: pd.DataFrame, config: dict) -> None:
    # Derived columns drive z-scores, labels and comparisons, so they are recomputed, not trusted.
    lengths = table["horizon_periods"].astype(int).to_numpy()
    blocks = (table["sampling"] == "block").to_numpy()
    expected_obs = np.where(blocks, config["n_paths"] * config["n_periods"] // lengths, config["n_paths"])
    if not (table["n_obs"].to_numpy() == expected_obs).all():
        raise CacheMismatch("n_obs disagrees with the path count, path length and horizon")
    if not np.allclose(table["horizon_years"], lengths / config["periods_per_year"], rtol=0.0, atol=1e-12):
        raise CacheMismatch("horizon_years disagrees with horizon_periods / periods_per_year")
    if not (table["n_draws"] == config["n_paths"] * config["n_periods"]).all():
        raise CacheMismatch("n_draws disagrees with n_paths * n_periods")
    columns = ["unclipped_exact_mean", "unclipped_exact_sd", "unclipped_exact_skew", "unclipped_exact_kurt"]
    exact = np.array([table1_sim.exact_moments(config["mu"], s, int(L))
                      for s, L in zip(table["sigma"], lengths)])
    if not np.allclose(table[columns].to_numpy(), exact, rtol=1e-9, atol=0.0, equal_nan=True):
        raise CacheMismatch("exact-moment columns disagree with the run's mean, volatility and horizon")
    bound = np.array([table1_sim.max_sample_skewness(int(n)) for n in table["n_obs"]])
    if not np.allclose(table["skew_bound"].to_numpy(), bound, rtol=1e-12, atol=0.0):
        raise CacheMismatch("skew_bound disagrees with the observation count")


def _csv_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run_cached(path: Path, *, refresh: bool = False, **run) -> pd.DataFrame:
    """run_seeds output for the experiment described by run (the experiment_config arguments).

    Reuses path when its sidecar JSON (path with suffix .json) matches the request, the CSV
    still has the SHA-256 recorded in that JSON, and the CSV passes validate_table; raises
    CacheMismatch otherwise. refresh=True recomputes and overwrites both files.
    """
    config = experiment_config(**run)
    meta_path = path.with_suffix(".json")
    if not refresh and path.exists():
        stored = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        stored_config = {k: v for k, v in stored.items() if k != "csv_sha256"}
        if stored_config != config:
            changed = sorted(k for k in config if stored_config.get(k) != config[k])
            raise CacheMismatch(
                f"{path} does not match the requested run (differs in {changed}); "
                "rerun with refresh=True to recompute"
            )
        if stored.get("csv_sha256") != _csv_sha256(path):
            raise CacheMismatch(f"{path} has changed since it was written; rerun with refresh=True")
        # The default C parser can be off by one unit in the last place; round_trip is exact.
        table = pd.read_csv(path, float_precision="round_trip")
        validate_table(table, config)
        return table

    table = table1_sim.run_seeds(
        config["seeds"], config["mu"], config["sigmas"], config["n_paths"], config["n_periods"],
        block_lengths=config["block_lengths"], prefix_lengths=config["prefix_lengths"],
        absorbing=run.get("absorbing", False), periods_per_year=config["periods_per_year"],
    )
    validate_table(table, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)
    meta_path.write_text(json.dumps({**config, "csv_sha256": _csv_sha256(path)}, indent=2) + "\n")
    return table
