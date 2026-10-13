"""The empirical result contract: `results/<study>/<file>` plus `results/manifest.json`.

`python -m research.run_all` writes the files and the manifest; the notebook and the slides read them only through
`load`, which refuses a file whose sha256 differs from the manifest. `results/` holds aggregates only
(portfolio-, decile- or formation-level rows); security-level rows stay in the git-ignored `output/`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

FINAL = Path(__file__).resolve().parent.parent
RESULTS = FINAL / "results"
SECURITY_COLUMNS = {"permno", "permco", "ticker", "comnam", "cusip", "ncusip"}
META_KEYS = ("description", "window", "returns", "role")
ROLES = {"primary", "exploratory", "check"}


class ResultHashError(RuntimeError):
    """A result file differs from the hash recorded in the manifest."""


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_aggregate(df: pd.DataFrame, where) -> None:
    """Raise if a results table carries security-level rows: an identifier column (permno, ticker, comnam, ...),
    or more than one row per (date, permno)."""
    cols = {str(c).strip().lower() for c in df.columns}
    bad = sorted(cols & SECURITY_COLUMNS)
    if bad:
        raise ValueError(f"{where}: security-level column(s) {bad}; such rows belong in output/, not results/")
    if {"date", "permno"} <= cols and df.duplicated(["date", "permno"]).any():
        raise ValueError(f"{where}: security-level rows (repeated date, permno)")


def security_headers(headers) -> list[str]:
    """The header cells that name a security identifier (exact match, case- and space-insensitive). Prose that
    merely mentions an identifier, such as a convention "one class per PERMCO", is not a header."""
    return [h for h in headers if str(h).strip().strip("*").lower() in SECURITY_COLUMNS]


def file_record(root: Path, study: str, name: str, meta: dict) -> dict:
    """Manifest entry for results/<study>/<name>: path, hash, size and the declared metadata."""
    missing = [k for k in META_KEYS if k not in meta]
    if missing:
        raise ValueError(f"{study}/{name}: metadata lacks {missing}")
    if meta["role"] not in ROLES:
        raise ValueError(f"{study}/{name}: role must be one of {sorted(ROLES)}, got {meta['role']!r}")
    path = Path(root) / study / name
    return {"path": f"{study}/{name}", "study": study, "sha256": sha256(path), "bytes": path.stat().st_size,
            **{k: meta[k] for k in META_KEYS}}


def manifest(root: Path = RESULTS) -> dict:
    return json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))


def path(study: str, name: str, root: Path = RESULTS) -> Path:
    """The verified path of a result file (raises like `load`)."""
    rec = manifest(root)["files"][f"{study}/{name}"]
    p = Path(root) / study / name
    if sha256(p) != rec["sha256"]:
        raise ResultHashError(f"{study}/{name}: sha256 differs from results/manifest.json; rerun python -m research.run_all")
    return p


def load(study: str, name: str, root: Path = RESULTS, **read_csv_kwargs):
    """(content, metadata) of results/<study>/<name>. CSVs come back as DataFrames read with exact float
    round-tripping, JSON as a dict, anything else (figures) as its path. Raises KeyError for a file that the
    manifest does not list and ResultHashError for a file whose hash does not match."""
    p = path(study, name, root)
    rec = manifest(root)["files"][f"{study}/{name}"]
    if p.suffix == ".csv":
        return pd.read_csv(p, float_precision="round_trip", **read_csv_kwargs), rec
    if p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8")), rec
    return p, rec
