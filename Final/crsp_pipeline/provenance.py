"""File hashes and code version for the run manifest."""
import hashlib
import platform
import subprocess
from pathlib import Path

from . import config


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def code_version() -> dict:
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=config.FINAL, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    status = git("status", "--porcelain", "--", ".")
    # A commit plus a dirty flag cannot identify uncommitted code, so hash the sources themselves.
    sources = {p.relative_to(config.FINAL).as_posix(): sha256(p)
               for p in sorted((config.FINAL / "crsp_pipeline").glob("*.py"))}
    return {"git_commit": git("rev-parse", "HEAD"), "uncommitted_changes": bool(status),
            "source_sha256": sources, "python": platform.python_version(),
            "packages": _package_versions()}


def _package_versions() -> dict:
    from importlib import metadata
    out = {}
    for name in ["numpy", "pandas", "pyarrow", "sqlalchemy", "psycopg2-binary"]:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out
