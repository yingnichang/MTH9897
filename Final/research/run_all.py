"""Run every study and write the tracked result contract (results/<study>/*, results/manifest.json).

    python -m research.run_all                         # every study, 1929-01 .. 2024-12
    python -m research.run_all --only critical_tests   # one study (its dependencies must be current in results/)
    python -m research.run_all --only critical_tests --with-deps   # also recompute stale or absent dependencies
    python -m research.run_all --only data_audit replication attribution paper_targets --end 2016-12-31 --results results_rehearsal   # a paper-period rehearsal outside results/

Inputs are only `data/` (panel, benchmark, factors, raw msedist/msi where used). Security-level caches and
ledgers go to the git-ignored `output/`. A study must write exactly the files it declares in `FILES`; every CSV
is checked to be aggregate-only before the manifest is written.

Provenance is kept per study: the data-manifest hash, the hashes of the source files the study imports, the hash of
every dependency file it read, and a fingerprint of each dependency study. A partial run (`--only`) refuses to reuse
a dependency whose provenance differs from the current data and sources, or whose files changed, unless
`--with-deps` recomputes it first. Studies with a fixed sample (`FIXED_END`) reject another `--end`. All of this is
checked before any result directory is touched.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import platform
import sys
import time
from importlib import metadata
from pathlib import Path

import pandas as pd

from crsp_pipeline import config
from research import results
from research.studies._common import DATA, DEFAULT_END, FINAL, Context

PACKAGES = ["numpy", "pandas", "scipy", "matplotlib", "pyarrow"]
LOCAL_PACKAGES = ("research", "crsp_pipeline")
STUDIES_DIR = FINAL / "research" / "studies"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _rel(p: Path) -> str:
    return str(Path(p).relative_to(FINAL)).replace("\\", "/")


def source_hashes() -> dict:
    files = sorted([*(FINAL / "research").rglob("*.py"), *(FINAL / "research" / "studies" / "data").glob("*"),
                    *(FINAL / "crsp_pipeline").glob("*.py")])
    return {_rel(p): results.sha256(p) for p in files if p.is_file()}


def data_hash() -> str | None:
    return results.sha256(config.MANIFEST_FILE) if config.MANIFEST_FILE.exists() else None


def _module_file(name: str) -> Path | None:
    parts = name.split(".")
    if parts[0] not in LOCAL_PACKAGES:
        return None
    base = FINAL.joinpath(*parts)
    for p in (base.with_suffix(".py"), base / "__init__.py"):
        if p.is_file():
            return p
    return None


def _imported_names(path: Path):
    """Dotted names imported anywhere in a module (function-level imports included), relative imports resolved."""
    rel = Path(path).relative_to(FINAL).with_suffix("").parts
    package = rel[:-1]                                    # the package of a module and of an __init__ alike
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ".".join([*package[:len(package) - node.level + 1], *([node.module] if node.module else [])])
            else:
                base = node.module
            yield base
            yield from (f"{base}.{a.name}" for a in node.names)


def study_sources(study) -> dict:
    """sha256 of the files a study module depends on: the module, the local modules it imports (transitively), and
    the tracked study inputs in research/studies/data that it names, plus `_common.py` (the Context every study runs in). Other study modules (and the registry package)
    are not followed: studies are linked only through DEPENDS, whose fingerprints are recorded separately."""
    start = getattr(study, "__file__", None)
    if start is None:
        return {}
    start = Path(start).resolve()
    seen, todo = set(), [start, (STUDIES_DIR / "_common.py").resolve()]   # every study runs through Context
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        for name in _imported_names(p):
            f = _module_file(name)
            if f is None or f in seen:
                continue
            f = f.resolve()
            if f.parent == STUDIES_DIR and f.name != "_common.py" and f != start:
                continue                                  # another study module, or research/studies/__init__.py
            todo.append(f)
    text = start.read_text(encoding="utf-8")
    data = [p for p in DATA.glob("*") if p.is_file() and p.name in text]
    return {_rel(p): results.sha256(p) for p in sorted([*seen, *data])}


def fingerprint(man: dict, study: str) -> str:
    """Identity of a study's recorded state: its end, provenance and file hashes (not its run time)."""
    rec = man["studies"][study]
    body = {"end": rec.get("end"), "provenance": rec.get("provenance"),
            "files": {k: v["sha256"] for k, v in man["files"].items() if k.startswith(f"{study}/")}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def stale_reasons(man: dict, registry: dict, study: str, root: Path, data: str | None, end: pd.Timestamp,
                  recompute: set) -> list[str]:
    """Why a study's recorded results may not be reused as a dependency in this run ([] when they are current)."""
    rec = man["studies"].get(study)
    if rec is None:
        return [f"not in {root}"]
    prov = rec.get("provenance")
    if not prov:
        return ["no provenance recorded (manifest written before per-study provenance)"]
    why = []
    if prov.get("data_manifest_sha256") != data:
        why.append("data manifest changed")
    cur, old = study_sources(registry[study]), prov.get("sources", {})
    changed = sorted(k for k in set(cur) | set(old) if cur.get(k) != old.get(k))
    if changed:
        why.append(f"sources changed: {changed}")
    if rec.get("end") != str(end.date()):
        why.append(f"end {rec.get('end')} differs from {end.date()}")
    for name in registry[study].FILES:
        frec, p = man["files"].get(f"{study}/{name}"), root / study / name
        if frec is None or not p.exists() or results.sha256(p) != frec["sha256"]:
            why.append(f"{study}/{name} missing or modified")
    for d in getattr(registry[study], "DEPENDS", ()):
        if d in recompute:
            why.append(f"depends on {d}, which this run recomputes")
        elif d not in man["studies"] or prov.get("depends", {}).get(d) != fingerprint(man, d):
            why.append(f"{d} changed since {study} ran")
    for k, h in prov.get("inputs", {}).items():
        if man["files"].get(k, {}).get("sha256") != h:
            why.append(f"input {k} changed")
    return why


def _closure(registry: dict, selected: set) -> set:
    need, todo = set(), list(selected)
    while todo:
        for d in getattr(registry[todo.pop()], "DEPENDS", ()):
            if d not in need:
                need.add(d)
                todo.append(d)
    return need - selected


def packages() -> dict:
    out = {"python": platform.python_version()}
    for name in PACKAGES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def main(argv=None, registry: dict | None = None) -> dict:
    if registry is None:
        from research.studies import REGISTRY as registry
    ap = argparse.ArgumentParser(prog="python -m research.run_all", description=__doc__.split("\n")[0])
    ap.add_argument("--only", nargs="+", metavar="STUDY", help=f"studies to run, from: {', '.join(registry)}")
    ap.add_argument("--with-deps", action="store_true",
                    help="recompute dependencies that are absent or whose provenance is stale, instead of failing")
    ap.add_argument("--end", default=str(DEFAULT_END.date()), help="last month for the studies that run to 2024")
    ap.add_argument("--results", default=str(results.RESULTS), help="results directory (default: results/)")
    ap.add_argument("--output", default=str(FINAL / "output"), help="security-level cache directory (git-ignored)")
    args = ap.parse_args(argv)
    unknown = sorted(set(args.only or []) - set(registry))
    if unknown:
        ap.error(f"unknown study {unknown}; choose from {list(registry)}")
    end = pd.Timestamp(args.end)
    root = Path(args.results)
    if end != DEFAULT_END and root.resolve() == results.RESULTS.resolve():
        ap.error("a non-default --end must write to another directory (--results ...), never over results/")

    # Everything below is validated before any result directory is created or changed.
    mpath = root / "manifest.json"
    man = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    man.setdefault("files", {})
    man.setdefault("studies", {})
    data = data_hash()
    chosen = set(args.only or registry)
    while True:
        stale = {d: why for d in sorted(_closure(registry, chosen))
                 if (why := stale_reasons(man, registry, d, root, data, end, chosen))}
        if not stale:
            break
        if not args.with_deps:
            ap.error("dependencies cannot be reused: " + "; ".join(f"{d}: {', '.join(w)}" for d, w in stale.items())
                     + ". Rerun them, include them in --only, or add --with-deps")
        chosen |= set(stale)
    selected = [s for s in registry if s in chosen]
    fixed = [s for s in selected if getattr(registry[s], "FIXED_END", None) is not None
             and pd.Timestamp(registry[s].FIXED_END) != end]
    if fixed:
        ap.error(f"{fixed} have a fixed sample end and cannot run with --end {end.date()}")

    root.mkdir(parents=True, exist_ok=True)
    ctx = Context(results=root, output=Path(args.output), end=end, files=man["files"])
    pkgs = packages()
    t_all = time.time()
    for s in selected:
        study = registry[s]
        out = ctx.out(s)
        for old in out.iterdir():                       # generated directory: stale files are removed
            if old.is_file():
                old.unlink()
        ctx.log(f"--- {s}")
        ctx.reads = {}
        t = time.time()
        study.run(ctx)
        secs = time.time() - t
        produced = {p.name for p in out.iterdir() if p.is_file()}
        declared = set(study.FILES)
        if produced != declared:
            raise ValueError(f"{s}: files written {sorted(produced - declared)} not declared, "
                             f"declared {sorted(declared - produced)} not written")
        for name in sorted(produced):
            if name.endswith(".csv"):
                results.check_aggregate(pd.read_csv(out / name, nrows=None), out / name)
        for k in [k for k in man["files"] if k.startswith(f"{s}/")]:
            del man["files"][k]                          # in place: ctx.files is this dict
        for name in sorted(produced):
            man["files"][f"{s}/{name}"] = results.file_record(root, s, name, study.FILES[name])
        man["studies"][s] = {"run_utc": _now(), "seconds": round(secs, 1), "end": str(end.date()),
                             "files": len(produced),
                             "provenance": {"data_manifest_sha256": data, "sources": study_sources(study),
                                            "inputs": dict(sorted(ctx.reads.items())),
                                            "depends": {d: fingerprint(man, d) for d in getattr(study, "DEPENDS", ())},
                                            "packages": pkgs}}
        ctx.log(f"{s}: {len(produced)} files in {secs:.0f}s")
    hashes = {v.get("provenance", {}).get("data_manifest_sha256") for v in man["studies"].values()}
    man.pop("source_sha256", None)                      # superseded by the per-study provenance
    man.update({"updated_utc": _now(),
                "data_manifest_sha256": hashes.pop() if len(hashes) == 1 else
                "mixed: see studies.<name>.provenance",
                "packages": pkgs,
                "last_run": {"studies": selected, "seconds": round(time.time() - t_all, 1),
                             "argv": argv if argv is not None else sys.argv[1:], "source_sha256": source_hashes()}})
    man["files"] = dict(sorted(man["files"].items()))
    man["studies"] = dict(sorted(man["studies"].items(), key=lambda kv: list(registry).index(kv[0])
                                 if kv[0] in registry else len(registry)))
    mpath.write_text(json.dumps(man, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    ctx.log(f"manifest: {len(man['files'])} files, {len(man['studies'])} studies -> {mpath}")
    return man


if __name__ == "__main__":
    main()
