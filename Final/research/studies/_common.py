"""Shared context for the study modules run by `python -m research.run_all`."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from research import results

FINAL = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"          # tracked study inputs (explanations, freeze records)
DEFAULT_END = pd.Timestamp("2024-12-31")


@dataclass
class Context:
    results: Path = FINAL / "results"
    output: Path = FINAL / "output"                      # git-ignored: security-level caches and ledgers
    end: pd.Timestamp = DEFAULT_END
    t0: float = field(default_factory=time.time)
    files: dict | None = None                            # manifest file records; None reads <results>/manifest.json
    reads: dict = field(default_factory=dict)            # dependency files read: "study/name" -> sha256

    def out(self, study: str) -> Path:
        p = Path(self.results) / study
        p.mkdir(parents=True, exist_ok=True)
        return p

    def result(self, study: str, name: str) -> Path:
        """Path of an earlier study's output in this results directory (read with the study's own options), after
        checking its sha256 against the manifest. Raises ResultHashError for a file that the manifest does not list
        or whose hash differs, and records the hash it read in `reads`."""
        p = Path(self.results) / study / name
        if not p.exists():
            raise FileNotFoundError(f"{p} is missing: run `python -m research.run_all --only {study}` first")
        files = self.files if self.files is not None else results.manifest(self.results)["files"]
        key = f"{study}/{name}"
        if key not in files:
            raise results.ResultHashError(f"{key} is not listed in the results manifest")
        h = results.sha256(p)
        if h != files[key]["sha256"]:
            raise results.ResultHashError(f"{key}: sha256 differs from the results manifest; rerun "
                                          f"`python -m research.run_all --only {study}`")
        self.reads[key] = h
        return p

    def universe_cache(self) -> Path:
        """output/diagnostics_universe.parquet (security-level, git-ignored); rebuilt when missing."""
        p = Path(self.output) / "diagnostics_universe.parquet"
        if not p.exists():
            from research.studies import diagnostics
            self.log(f"{p.name} missing: rebuilding it")
            diagnostics.build_universe(self)
        return p

    def log(self, msg: str) -> None:
        print(f"[{time.time() - self.t0:5.0f}s] {msg}", flush=True)
