"""Validation and comparison helpers for the Table 1 simulations (output of table1_sim.run_seeds).

Every helper that summarizes across seeds or joins to the paper works on one experiment at a
time: a single return model, mean, path count and path length. Mixed inputs raise rather than
being pooled, and derived tables carry the experiment and main seed with them.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PAPER_TABLE1 = Path(__file__).resolve().parents[1] / "data" / "paper" / "table1.csv"

# Columns that must be constant within one experiment, and the key of one simulated row.
EXPERIMENT = ["return_model", "mu", "n_paths", "n_periods"]
ROW_KEY = ["seed", "sigma", "sampling", "horizon_periods"]
# One simulated cell; the seed column distinguishes repeated runs of the same cell.
CELL = ["sigma", "sampling", "horizon_periods", "horizon_years", "n_obs"]

# Half a unit in the last digit the paper reports, per statistic (values in decimals).
PAPER_HALF_UNIT = {"skew": 0.0005, "median": 0.00005, "pct_positive": 0.00005, "p99": 0.0005}

# Statistics that must be finite in every simulated row; skewness may be NaN only at sigma = 0.
FINITE_STATS = ["mean", "sd", "median", "pct_positive", "p99"]


class ValidationError(ValueError):
    """A simulated table failed a check that should stop the analysis."""


def load_paper_table1(path: Path = PAPER_TABLE1) -> pd.DataFrame:
    """Bessembinder (2018) Table 1 in long form: stat, horizon_years, sigma, value (decimals)."""
    paper = pd.read_csv(path)
    if paper.duplicated(["stat", "horizon_years", "sigma"]).any():
        raise ValueError(f"{path} has duplicate (stat, horizon_years, sigma) rows")
    return paper


def experiment_of(table: pd.DataFrame) -> dict:
    """The single experiment a table holds; raises if it mixes experiments or repeats a row."""
    values = {}
    for column in EXPERIMENT:
        distinct = table[column].unique()
        if len(distinct) != 1:
            raise ValueError(f"table mixes experiments: {column} takes values {sorted(distinct)}")
        values[column] = distinct[0]
    if table.duplicated(ROW_KEY).any():
        raise ValueError("table repeats (seed, sigma, sampling, horizon) rows")
    return values


def _key(values: pd.Series) -> pd.Series:
    # Float grids are matched on rounded keys so 0.06 and 0.060000000000000005 agree.
    return values.astype(float).round(10)


def moment_checks(table: pd.DataFrame, z_limit: float = 4.0, skew_limit: float = 10.0) -> pd.DataFrame:
    """Compare simulated mean and sd with the exact values of the unclipped model.

    mean_z uses the standard error exact_sd / sqrt(n). sd_z uses the relative standard error of
    a sample sd, sqrt((kurtosis - 1) / (4 n)), from the exact kurtosis. The check column is:
      "pass" / "fail"   literal model, 0 < exact skewness < skew_limit, both |z| <= z_limit;
      "diagnostic only" literal model with exact skewness >= skew_limit, where the normal
                        approximation behind the z-scores is too rough to act as a test;
      "pass" / "fail"   for sigma = 0, a numerical check: sd is 0 and the mean equals the
                        compounded mean to a relative 1e-12;
      "not applicable"  for the absorbing model, whose population moments differ.
    Even a "pass" is a heavy-tail diagnostic, not proof of convergence.
    """
    out = table.copy()
    n = out["n_obs"].astype(float)
    out["mean_z"] = (out["mean"] - out["unclipped_exact_mean"]) / (out["unclipped_exact_sd"] / np.sqrt(n))
    sd_rel_se = np.sqrt((out["unclipped_exact_kurt"] - 1.0) / (4.0 * n))
    out["sd_z"] = (out["sd"] / out["unclipped_exact_sd"] - 1.0) / sd_rel_se

    literal = out["return_model"] == "literal"
    zero_vol = out["sigma"] == 0.0
    tested = literal & ~zero_vol & (out["unclipped_exact_skew"] < skew_limit)
    within = (out["mean_z"].abs() <= z_limit) & (out["sd_z"].abs() <= z_limit)
    zero_ok = (out["sd"] == 0.0) & np.isclose(
        out["mean"], out["unclipped_exact_mean"], rtol=1e-12, atol=0.0
    )

    out["check"] = np.select(
        [~literal, zero_vol & zero_ok, zero_vol, tested & within, tested],
        ["not applicable", "pass", "fail", "pass", "fail"],
        default="diagnostic only",
    )
    return out


def enforce_checks(checked: pd.DataFrame) -> pd.DataFrame:
    """Stop on a failed or non-finite row; otherwise return a summary derived from the checks.

    Raises ValidationError if any row is labeled "fail", if a statistic in FINITE_STATS is not
    finite, or if skewness is not finite at positive volatility. "diagnostic only" rows are
    not failures. The summary gives, per check label, the row count and the largest |z| for
    the mean and sd (the z-scores are undefined at sigma = 0).
    """
    problems = []
    failed = checked[checked["check"] == "fail"]
    if len(failed):
        problems.append(f"{len(failed)} row(s) fail the mean/sd check:\n"
                        + failed[ROW_KEY + ["mean_z", "sd_z"]].to_string(index=False))
    for column in FINITE_STATS:
        bad = ~np.isfinite(checked[column].astype(float))
        if bad.any():
            problems.append(f"{int(bad.sum())} row(s) have a non-finite {column}")
    bad_skew = (checked["sigma"] > 0.0) & ~np.isfinite(checked["skew"].astype(float))
    if bad_skew.any():
        problems.append(f"{int(bad_skew.sum())} positive-volatility row(s) have a non-finite skewness")
    if problems:
        raise ValidationError("\n".join(problems))

    positive = checked[checked["sigma"] > 0.0]
    summary = checked.groupby("check").size().rename("rows").to_frame()
    summary["max_abs_mean_z"] = positive.groupby("check")["mean_z"].apply(lambda z: z.abs().max())
    summary["max_abs_sd_z"] = positive.groupby("check")["sd_z"].apply(lambda z: z.abs().max())
    return summary


def skewness_warnings(table: pd.DataFrame, bound_share: float = 0.1, n_sd: float = 3.0) -> pd.DataFrame:
    """One row per cell: the seeds' skewness estimates against the exact population skewness.

    Two declared heuristics, neither a calibrated test:
      near_bound             the exact skewness is at least bound_share of the sample-skewness
                             bound for that sample size;
      outside_seed_interval  the exact skewness lies outside the seeds' mean +- n_sd standard
                             deviations. Unavailable (NA) with fewer than two finite seed
                             estimates, since one estimate gives no spread.
    The warning column reads "warning triggered" if either fires; "no warning triggered" if
    neither fires and both were available; "no bound warning; seed interval unavailable" with
    a single seed; and "not applicable" at sigma = 0 or for the absorbing model, whose
    population skewness is not the unclipped exact value. The absence of a warning does not
    establish that an estimate is accurate. seeds_below_exact is descriptive only: under heavy
    tails sample skewness is biased downward, which shows up as most seeds falling below the
    exact value.
    """
    experiment = experiment_of(table)
    cells = (
        table.assign(below=table["skew"] < table["unclipped_exact_skew"])
        .groupby(CELL, sort=True)
        .agg(
            n_seeds=("seed", "nunique"),
            n_finite=("skew", "count"),
            seeds_below_exact=("below", "sum"),
            skew_mean=("skew", "mean"),
            skew_sd=("skew", "std"),
            skew_min=("skew", "min"),
            skew_max=("skew", "max"),
            exact_skew=("unclipped_exact_skew", "first"),
            skew_bound=("skew_bound", "first"),
        )
        .reset_index()
    )
    for column, value in experiment.items():
        cells.insert(0, column, value)

    applicable = (experiment["return_model"] == "literal") & cells["exact_skew"].notna()
    interval_available = applicable & (cells["n_finite"] >= 2)
    cells["interval_low"] = (cells["skew_mean"] - n_sd * cells["skew_sd"]).where(interval_available)
    cells["interval_high"] = (cells["skew_mean"] + n_sd * cells["skew_sd"]).where(interval_available)
    near = applicable & (cells["exact_skew"] >= bound_share * cells["skew_bound"])
    outside = (cells["exact_skew"] < cells["interval_low"]) | (cells["exact_skew"] > cells["interval_high"])

    cells["near_bound"] = pd.Series(near, dtype="boolean").where(applicable)
    cells["outside_seed_interval"] = pd.Series(outside, dtype="boolean").where(interval_available)
    cells["warning"] = np.select(
        [~applicable, near | (interval_available & outside), interval_available],
        ["not applicable", "warning triggered", "no warning triggered"],
        default="no bound warning; seed interval unavailable",
    )
    return cells


def compare_with_paper(
    table: pd.DataFrame,
    paper: pd.DataFrame,
    stats: tuple[str, ...] = ("skew", "median", "pct_positive", "p99"),
    main_seed: int = 0,
    paper_sigma: dict[float, float] | None = None,
) -> pd.DataFrame:
    """Main-seed statistics next to the paper's, with the seeds' spread as a Monte Carlo diagnostic.

    table must hold one experiment with one sampling scheme per horizon. paper_sigma maps each
    simulated sigma to the paper column it is compared with; by default the same value. A
    mapped comparison (daily sigma against a monthly column) is labeled "approximate" in the
    match column: it pairs similar volatilities, not matched moments.

    diff_in_seed_sd scales the difference by the standard deviation across seeds; together
    with the paper's rounding (paper_half_unit) it indicates whether a gap is within
    simulation noise. It is not a formal acceptance interval, and it is NaN for a single seed
    or a deterministic cell.
    """
    experiment = experiment_of(table)
    if main_seed not in set(table["seed"]):
        raise ValueError(f"main seed {main_seed} is not in the table")
    if table.duplicated(["seed", "sigma", "horizon_years"]).any():
        raise ValueError("table has two sampling schemes for the same horizon; select one")

    keys = ["sigma", "horizon_years"]
    rows = []
    for stat in stats:
        spread = table.groupby(keys)[stat].std().rename("seed_sd")
        ours = table[table["seed"] == main_seed].set_index(keys)[stat].rename("ours")
        cell = pd.concat([ours, spread], axis=1).reset_index()
        cell["stat"] = stat
        rows.append(cell)
    ours = pd.concat(rows, ignore_index=True)

    mapping = {} if paper_sigma is None else {round(float(k), 10): v for k, v in paper_sigma.items()}
    if paper_sigma is not None and set(_key(ours["sigma"])) - set(mapping):
        raise ValueError("paper_sigma does not cover every simulated sigma")
    ours["paper_sigma"] = [mapping.get(round(float(s), 10), s) for s in ours["sigma"]]
    ours["match"] = "same sigma" if paper_sigma is None else "approximate (mapped sigma)"

    reference = paper.assign(paper_key=_key(paper["sigma"]), horizon_key=_key(paper["horizon_years"]))
    merged = ours.assign(paper_key=_key(ours["paper_sigma"]), horizon_key=_key(ours["horizon_years"])).merge(
        reference[["stat", "paper_key", "horizon_key", "value"]].rename(columns={"value": "paper"}),
        on=["stat", "paper_key", "horizon_key"],
        how="left",
        validate="many_to_one",
    )
    merged["diff"] = merged["ours"] - merged["paper"]
    # Deterministic cells (sigma = 0) have no seed spread; only the paper's rounding applies.
    merged["diff_in_seed_sd"] = merged["diff"] / merged["seed_sd"].where(merged["seed_sd"] > 0.0)
    merged["paper_half_unit"] = merged["stat"].map(PAPER_HALF_UNIT)
    for column, value in experiment.items():
        merged[column] = value
    merged["main_seed"] = main_seed
    return merged[EXPERIMENT + ["main_seed", "stat", "horizon_years", "sigma", "paper_sigma", "match",
                                "ours", "paper", "diff", "seed_sd", "diff_in_seed_sd", "paper_half_unit"]]


def panel(frame: pd.DataFrame, value: str, row: str = "horizon_years", column: str = "sigma") -> pd.DataFrame:
    """Table 1 layout: horizons down the side, volatilities across the top (duplicates raise)."""
    return frame.pivot(index=row, columns=column, values=value)


def stacked_panel(parts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Interleave same-shaped panels: per horizon, one row per labeled part, in the given order."""
    shapes = {(tuple(p.index), tuple(p.columns)) for p in parts.values()}
    if len(shapes) != 1:
        raise ValueError("panels must share horizons and columns")
    stacked = pd.concat(parts, names=["row"]).reorder_levels(["horizon_years", "row"])
    horizons = next(iter(parts.values())).index
    order = pd.MultiIndex.from_product([sorted(horizons), list(parts)], names=["horizon_years", "row"])
    return stacked.reindex(order)


def paper_panel(comparison: pd.DataFrame, stat: str) -> pd.DataFrame:
    """One Table 1 panel for display: per horizon, rows ours / paper / difference / difference in seed SDs."""
    cells = comparison[comparison["stat"] == stat]
    main_seed = int(cells["main_seed"].iloc[0])
    return stacked_panel({
        f"ours (seed {main_seed})": panel(cells, "ours"),
        "paper": panel(cells, "paper"),
        "ours - paper": panel(cells, "diff"),
        "diff / seed SD": panel(cells, "diff_in_seed_sd"),
    })


def skewness_table(warnings: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    """Panel A in long form: exact, paper, main-seed and seed-range skewness with the warning.

    Both inputs must come from the same experiment; the join is one-to-one on sigma and horizon.
    """
    for column in EXPERIMENT:
        if set(warnings[column]) != set(comparison[column]):
            raise ValueError(f"warnings and comparison come from different experiments ({column})")
    skew = comparison[comparison["stat"] == "skew"]
    merged = warnings.assign(sigma_key=_key(warnings["sigma"]), horizon_key=_key(warnings["horizon_years"])).merge(
        skew.assign(sigma_key=_key(skew["sigma"]), horizon_key=_key(skew["horizon_years"]))[
            ["sigma_key", "horizon_key", "main_seed", "paper_sigma", "ours", "paper"]],
        on=["sigma_key", "horizon_key"],
        how="left",
        validate="one_to_one",
    )
    return merged[EXPERIMENT + ["main_seed", "horizon_years", "sigma", "paper_sigma", "exact_skew", "paper",
                                "ours", "skew_min", "skew_max", "n_seeds", "seeds_below_exact", "skew_bound",
                                "near_bound", "outside_seed_interval", "warning"]]
