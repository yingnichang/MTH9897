"""Offline stage: data/raw/*.parquet -> normalized panel, benchmark, factors, audits, manifest."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import audit, config
from .normalize import HOLD_SOURCES, build_benchmark, build_panel
from .provenance import code_version, sha256

RAW_TABLES = ["msf", "msenames", "msedelist", "msedist", "msi", "ff_factors"]


def load_raw(raw_dir: Path = config.RAW) -> dict[str, pd.DataFrame]:
    missing = [t for t in RAW_TABLES if not (raw_dir / f"{t}.parquet").exists()]
    if missing:
        raise FileNotFoundError(f"Missing raw extracts {missing} in {raw_dir}; run "
                                "`python -m crsp_pipeline extract --user <wrds_username>` first.")
    return {t: pd.read_parquet(raw_dir / f"{t}.parquet") for t in RAW_TABLES}


def validate_panel(panel: pd.DataFrame) -> None:
    """The invariants the notebook's `validate_inputs` enforces, checked before anything is written."""
    if not panel["date"].dt.is_month_end.all():
        raise AssertionError("Non-month-end dates")
    if panel.duplicated(["permno", "date"]).any():
        raise AssertionError("Duplicate PERMNO-months")
    for col in ["ret_total", "ret_price"]:
        if panel[col].lt(-1).any():
            raise AssertionError(f"{col} below -100%")
    e = panel.loc[panel["eligible"]]
    if (e[["mktcap", "price_adj", "shares_adj"]] <= 0).any().any() or e["is_exit"].any():
        raise AssertionError("Eligible row with nonpositive size fields or a terminal flag")
    if panel["div_cash_adj"].lt(0).any():
        raise AssertionError("Negative dividends")
    exits = panel.loc[panel["is_exit"]]
    if exits["permno"].duplicated().any():
        raise AssertionError("Multiple terminal rows for one security")
    last = panel.groupby("permno")["date"].max()
    if not exits["date"].to_numpy().__eq__(last.loc[exits["permno"]].to_numpy()).all():
        raise AssertionError("Observations after a terminal row")
    if exits["ret_total"].isna().any():
        raise AssertionError("Terminal row without a total return")
    if panel.groupby(["permco", "date"])["eligible"].sum().gt(1).any():
        raise AssertionError("More than one eligible share class per company-month")
    # Holding returns (DATA-002): ret_total where observed, stale carry otherwise, never a silent fill.
    src = panel["ret_hold_source"]
    if not src.isin(HOLD_SOURCES).all():
        raise AssertionError(f"Unknown ret_hold_source values {sorted(set(src) - set(HOLD_SOURCES))}")
    observed = panel["ret_total"].notna()
    if panel.loc[observed, "ret_hold"].ne(panel.loc[observed, "ret_total"]).any():
        raise AssertionError("ret_hold differs from ret_total where the total return is observed")
    if not panel["ret_hold"].isna().eq(src.eq("no_prior_row")).all():
        raise AssertionError("ret_hold is NaN outside no_prior_row (or no_prior_row has a value)")
    if (src.eq("stale_carry") & panel["is_exit"]).any():
        raise AssertionError("stale_carry on a terminal row")
    ratio = src.eq("price_ratio")
    if (ratio & (observed | panel["is_exit"])).any():
        raise AssertionError("price_ratio on a row with an observed return or a terminal flag")
    if (ratio & ~panel["price_adj"].gt(0)).any():
        raise AssertionError("price_ratio without a positive price")


def build(raw: dict[str, pd.DataFrame] | None = None, out_dir: Path = config.DATA,
          end: str = config.EXTRACT_END) -> dict:
    from_disk = raw is None
    raw = load_raw() if from_disk else raw
    audit_dir = out_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    print("normalizing panel ...", flush=True)
    panel, delist_log = build_panel(raw)
    panel = panel.loc[panel["date"].le(pd.Timestamp(end))].reset_index(drop=True)
    validate_panel(panel)
    bench, factors = build_benchmark(raw["msi"], raw["ff_factors"], config.BENCHMARK_START, end)

    panel_path = out_dir / config.PANEL_FILE.name
    bench_path = out_dir / config.BENCHMARK_FILE.name
    factors_path = out_dir / config.FACTORS_FILE.name
    panel.to_parquet(panel_path, index=False, compression="zstd")
    bench.to_csv(bench_path, index=False, date_format="%Y-%m-%d")
    factors.to_csv(factors_path, index=False, date_format="%Y-%m-%d")

    print("auditing ...", flush=True)
    tables = {
        "formation_coverage": audit.formation_coverage(panel),
        "exclusions_by_decade": audit.exclusions_by_decade(panel),
        "missingness_by_decade": audit.missingness_by_decade(panel),
        "delistings": audit.delisting_summary(delist_log, panel),
        "dividend_reconciliation": audit.dividend_reconciliation(panel, raw["msedist"]),
        "benchmark_check": audit.benchmark_check(bench, factors),
        "worked_examples": audit.worked_examples(panel, delist_log),
        "missing_returns": audit.missing_returns(panel),
    }
    for name, t in tables.items():
        t.to_csv(audit_dir / f"{name}.csv", index=name in {"exclusions_by_decade", "missingness_by_decade",
                                                           "benchmark_check"}, date_format="%Y-%m-%d")

    cov = tables["formation_coverage"]
    first = cov.loc[cov["date"].eq(pd.Timestamp(config.FIRST_INVESTMENT) - pd.offsets.MonthEnd(1))]
    extract_log = config.RAW / "extract_log.json"
    manifest = {
        "code": code_version(),
        "extract": json.loads(extract_log.read_text(encoding="utf-8")) if from_disk and extract_log.exists() else None,
        "conventions": {
            "common_share_codes": list(config.COMMON_SHARE_CODES),
            "exchange_codes": list(config.EXCHANGE_CODES),
            "delist_impute_nyse_amex": config.DELIST_IMPUTE_NYSE_AMEX,
            "delist_impute_nasdaq": config.DELIST_IMPUTE_NASDAQ,
            "performance_delist_codes": "500, 520-584",
            "dividends": "implied from ret - retx times lagged adjusted price",
            "one_class_per_permco": "largest market cap common-stock class",
            "history_months": config.HISTORY_MONTHS,
            "missing_held_returns": ("stale-price carry: ret_hold = 0 after the first row, or the price ratio to the "
                                     f"last price when CRSP reports a price and the last one is <= "
                                     f"{config.PRICE_RATIO_MAX_LOOKBACK_MONTHS} months earlier; "
                                     "resumption keeps CRSP's return"),
        },
        "sample": {
            "panel_rows": len(panel), "securities": int(panel["permno"].nunique()),
            "first_month": str(panel["date"].min().date()), "last_month": str(panel["date"].max().date()),
            "eligible_rows": int(panel["eligible"].sum()), "terminal_rows": int(panel["is_exit"].sum()),
            "eligible_missing_ret_total": int(panel.loc[panel["eligible"], "ret_total"].isna().sum()),
            "benchmark_months": len(bench),
            "benchmark_first": str(bench["date"].min().date()), "benchmark_last": str(bench["date"].max().date()),
            "first_formation_universe_n": int(first["universe_n"].iloc[0]) if len(first) else None,
            "min_universe_n": int(cov["universe_n"].min()) if len(cov) else None,
            "first_formation_with_full_universe": (str(cov.loc[cov["universe_n"].ge(config.UNIVERSE_SIZE), "date"].min().date())
                                                   if cov["universe_n"].ge(config.UNIVERSE_SIZE).any() else None),
            "delist_sources": delist_log["delist_source"].value_counts().to_dict(),
            "delist_rows_after_dropped": int(delist_log["rows_dropped"].sum()),
            "ret_hold_stale_carry_rows": int(panel["ret_hold_source"].eq("stale_carry").sum()),
            "ret_hold_no_prior_row_rows": int(panel["ret_hold_source"].eq("no_prior_row").sum()),
            "ret_hold_price_ratio_rows": int(panel["ret_hold_source"].eq("price_ratio").sum()),
            "universe_holding_stale_carry_months": int(
                tables["missing_returns"].set_index("decade").loc["total", "universe_holding_stale_carry"]),
        },
        "outputs": {p.name: sha256(p) for p in [panel_path, bench_path, factors_path]},
        "audits": {f"audit/{n}.csv": sha256(audit_dir / f"{n}.csv") for n in tables},
    }
    (out_dir / config.MANIFEST_FILE.name).write_text(json.dumps(manifest, indent=2, default=_json), encoding="utf-8")
    print(json.dumps(manifest["sample"], indent=2, default=_json))
    return {"panel": panel, "benchmark": bench, "factors": factors, "delistings": delist_log, **tables,
            "manifest": manifest}


def _json(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    return str(x)
