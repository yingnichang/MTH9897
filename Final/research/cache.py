"""Hash and producer identity for the licensed diagnostics cache. No observations in metadata."""
import json
from pathlib import Path

from crsp_pipeline import config
from research import results

KEY = "diagnostics_universe"


def identity(ctx):
    from research.run_all import study_sources, packages
    from research.studies import diagnostics
    return {"data_manifest_sha256": results.sha256(config.MANIFEST_FILE),
            "sources": study_sources(diagnostics), "end": str(ctx.end.date()), "packages": packages()}


def record_universe(ctx, path):
    rec = {"sha256": results.sha256(path), "producer": identity(ctx)}
    Path(path).with_suffix(".metadata.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    ctx.produced_caches[KEY] = rec
    return rec


def verified_universe(ctx):
    from research.studies import diagnostics
    path = Path(ctx.output) / "diagnostics_universe.parquet"
    meta = path.with_suffix(".metadata.json")
    records = ctx.study_records if ctx.study_records is not None else results.manifest(ctx.results)["studies"]
    expected = records.get("diagnostics", {}).get("provenance", {}).get("caches_produced", {}).get(KEY)
    if expected is None:
        raise results.ResultHashError("Diagnostics has no recorded cache identity; rerun diagnostics with dependencies")
    if expected["producer"] != identity(ctx):
        raise results.ResultHashError("Diagnostics cache producer is stale; rerun diagnostics with dependencies")
    if not path.exists():
        ctx.log(f"{path.name} missing: rebuilding from the verified producer")
        diagnostics.build_universe(ctx)
    if not meta.exists():
        raise results.ResultHashError("Diagnostics cache metadata missing; rerun diagnostics")
    actual = json.loads(meta.read_text(encoding="utf-8"))
    if actual != expected or results.sha256(path) != expected["sha256"]:
        raise results.ResultHashError("Diagnostics cache modified or from another run; rerun diagnostics")
    ctx.cache_reads[KEY] = expected
    return path
