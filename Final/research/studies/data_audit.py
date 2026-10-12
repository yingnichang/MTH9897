"""Data provenance and audits for the report: the pipeline's aggregate audit tables (data/audit/, tracked) and a
summary of data/manifest.json (extract time, coverage, conventions, row counts, file hashes), placed under the
result contract so the notebook and the deck read them through the hash-checked loader.

The security-level worked examples (data/audit/worked_examples.csv, licensed rows) are never copied.
"""
import json
import shutil

from crsp_pipeline import config
from research import results

NAME = "data_audit"
DEPENDS = ()
FILES = {
    "formation_coverage.csv": {"description": "Universe coverage at each quarter-end formation: eligible, history-eligible and universe counts, size cut-offs", "window": "formations 1928-12 .. 2024-12", "returns": "n/a", "role": "check"},
    "exclusions_by_decade.csv": {"description": "Rows excluded from eligibility by reason and decade", "window": "1925-12 .. 2024-12", "returns": "n/a", "role": "check"},
    "missingness_by_decade.csv": {"description": "Missing returns, dividends, shares and industries among eligible rows, by decade", "window": "1925-12 .. 2024-12", "returns": "n/a", "role": "check"},
    "missing_returns.csv": {"description": "Missing monthly returns and the stale-carry / price-ratio holding returns, panel-wide and in universe holdings, by decade", "window": "1925-12 .. 2024-12", "returns": "n/a", "role": "check"},
    "delistings.csv": {"description": "Delisting events by category and source (observed, Shumway-imputed, missing set to zero)", "window": "1925-12 .. 2024-12", "returns": "n/a", "role": "check"},
    "dividend_reconciliation.csv": {"description": "Implied dividends (ret - retx) against CRSP distributions, by decade", "window": "1925-12 .. 2024-12", "returns": "n/a", "role": "check"},
    "benchmark_check.csv": {"description": "CRSP VW market against the Fama-French market, by decade", "window": "1926-07 .. 2024-12", "returns": "gross", "role": "check"},
    "extract_summary.json": {"description": "Extract time and host, coverage, sample counts, conventions, table row counts and data file hashes (from data/manifest.json; no SQL text)", "window": "1925-12 .. 2024-12", "returns": "n/a", "role": "check"},
}
AUDITS = [k for k in FILES if k.endswith(".csv")]


def run(ctx):
    out = ctx.out(NAME)
    for name in AUDITS:
        shutil.copyfile(config.DATA / "audit" / name, out / name)
    m = json.loads(config.MANIFEST_FILE.read_text(encoding="utf-8"))
    ext = m["extract"]
    summary = {"extracted_at_utc": ext["extracted_at_utc"], "host": ext["host"], "library": ext["library"],
               "start": ext["start"], "end": ext["end"],
               "table_rows": {t: v["rows"] for t, v in ext["tables"].items()},
               "sample": m["sample"], "conventions": m["conventions"], "data_files_sha256": m["outputs"],
               "data_manifest_sha256": results.sha256(config.MANIFEST_FILE),
               "code_commit_at_build": m["code"].get("git_commit")}
    (out / "extract_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
