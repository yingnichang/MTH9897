"""Download, cache and parse the Ken French data library files used for Table 4.

Download and cache
------------------
Each zip is saved unchanged in data/raw/. data/vintage.json (the manifest) records, per file,
the source URL, download time (UTC), size, SHA-256 and the first line of the enclosed CSV,
which names the CRSP release ("This file was created using the 202608 CRSP database.").
French rebuilds the files when CRSP updates and history can be revised, so the cache is reused
rather than fetched again unless refresh=True.

The three files are treated as one set. A cache is reused only when every file is present,
has a manifest entry, matches its recorded SHA-256 and names a CRSP release, and all three
releases agree; anything else raises instead of being patched silently. A refresh fetches and
validates the complete set in memory before writing anything, then replaces each file
atomically and writes the manifest last, also atomically. If a refresh is interrupted while
files are being replaced, the next run finds files that no longer match the manifest and
raises; running with --refresh again restores a coherent cache.

Parsing
-------
Tables are located by their title line and header, never by line number. Only structure is
validated here: each required section appears once, labels match the declared order, months are
valid, consecutive and identical across sections and files, and values are numeric. Returns
become decimals with the missing-data codes (-99.99, -999) as NaN; firm counts stay counts.
Facts about one particular release are checked separately, in ff_audit.py.

Run from HW2 with: python src/ff_data.py [--refresh]
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = DATA_DIR / "raw"
VINTAGE_PATH = DATA_DIR / "vintage.json"

BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {
    "ff49": "49_Industry_Portfolios_CSV.zip",
    "ff12": "12_Industry_Portfolios_CSV.zip",
    "factors": "F-F_Research_Data_Factors_CSV.zip",
}

# Declared column order of each industry universe; every section must match it exactly.
INDUSTRY_COLUMNS = {
    "ff49": ("Agric", "Food", "Soda", "Beer", "Smoke", "Toys", "Fun", "Books", "Hshld", "Clths", "Hlth",
             "MedEq", "Drugs", "Chems", "Rubbr", "Txtls", "BldMt", "Cnstr", "Steel", "FabPr", "Mach", "ElcEq",
             "Autos", "Aero", "Ships", "Guns", "Gold", "Mines", "Coal", "Oil", "Util", "Telcm", "PerSv",
             "BusSv", "Hardw", "Softw", "Chips", "LabEq", "Paper", "Boxes", "Trans", "Whlsl", "Rtail",
             "Meals", "Banks", "Insur", "RlEst", "Fin", "Other"),
    "ff12": ("NoDur", "Durbl", "Manuf", "Enrgy", "Chems", "BusEq", "Telcm", "Utils", "Shops", "Hlth", "Money",
             "Other"),
}
FACTOR_COLUMNS = ("Mkt-RF", "SMB", "HML", "RF")

# Title lines (stripped) of the three monthly sections used from each industry file.
INDUSTRY_SECTIONS = {
    "vw": "Average Value Weighted Returns -- Monthly",
    "ew": "Average Equal Weighted Returns -- Monthly",
    "firms": "Number of Firms in Portfolios",
}
MISSING_CODES = (-99.99, -999.0)


def _fetch(url: str, timeout: float = 60.0) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def zipped_csv_text(content: bytes) -> str:
    """Text of the single CSV inside a French zip archive, given the archive's bytes."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        if len(names) != 1 or not names[0].lower().endswith(".csv"):
            raise ValueError(f"expected one CSV in the archive, found {names}")
        return archive.read(names[0]).decode("latin-1")


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def crsp_vintage(header: str) -> str | None:
    """CRSP release (YYYYMM) named in a French file's first line, or None if absent."""
    match = re.search(r"(\d{6}) CRSP", header)
    return match.group(1) if match else None


def load_vintage(path: Path = VINTAGE_PATH) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(content)
    partial.replace(path)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _require_one_release(releases: dict[str, str | None]) -> None:
    missing = [key for key, release in releases.items() if release is None]
    if missing:
        raise ValueError(f"no CRSP release named in the header of: {missing}")
    if len(set(releases.values())) > 1:
        raise ValueError(f"files come from different CRSP releases: {releases}")


def verify_cache(raw_dir: Path = RAW_DIR, vintage_path: Path = VINTAGE_PATH) -> dict[str, Path]:
    """Paths of a complete, coherent cache; raises if any file or manifest entry disagrees."""
    manifest = load_vintage(vintage_path)
    paths = {}
    for key, filename in FILES.items():
        path = raw_dir / filename
        if not path.exists():
            raise ValueError(f"{path} is missing; run with refresh=True to download the set")
        entry = manifest.get(key)
        if entry is None:
            raise ValueError(f"{path} has no entry in {vintage_path}; run with refresh=True")
        if _sha256(path.read_bytes()) != entry["sha256"]:
            raise ValueError(f"{path} does not match the SHA-256 in {vintage_path}; run with refresh=True")
        paths[key] = path
    _require_one_release({key: manifest[key].get("crsp_vintage") for key in FILES})
    return paths


def download_all(refresh: bool = False, raw_dir: Path = RAW_DIR, vintage_path: Path = VINTAGE_PATH) -> dict[str, Path]:
    """Paths to the three cached zips, downloading the complete set first if needed.

    Without refresh, an empty cache (no files, no manifest) is downloaded; any existing
    cache must pass verify_cache. With refresh, the set is fetched again. Every download
    must be a zip holding one CSV whose header names a CRSP release, and all three releases
    must agree, before anything is written.
    """
    if not refresh:
        has_files = any((raw_dir / filename).exists() for filename in FILES.values())
        if has_files or vintage_path.exists():
            return verify_cache(raw_dir, vintage_path)

    fetched = {}
    for key, filename in FILES.items():
        url = BASE_URL + filename
        content = _fetch(url)
        header = _first_line(zipped_csv_text(content))
        fetched[key] = (url, content, header)
    _require_one_release({key: crsp_vintage(header) for key, (_, _, header) in fetched.items()})

    downloaded_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {}
    for key, (url, content, header) in fetched.items():
        _write_atomic(raw_dir / FILES[key], content)
        manifest[key] = {
            "file": FILES[key],
            "url": url,
            "downloaded_utc": downloaded_utc,
            "bytes": len(content),
            "sha256": _sha256(content),
            "header": header,
            "crsp_vintage": crsp_vintage(header),
        }
    _write_atomic(vintage_path, (json.dumps(manifest, indent=2) + "\n").encode())
    return {key: raw_dir / filename for key, filename in FILES.items()}


@dataclass(frozen=True)
class Section:
    """One table of a French CSV: its title line, stripped labels, date keys and values as printed."""

    title: str
    columns: tuple[str, ...]
    dates: tuple[str, ...]
    values: np.ndarray

    @property
    def monthly(self) -> bool:
        return all(len(date) == 6 for date in self.dates)


def _is_row(line: str) -> bool:
    return line.split(",", 1)[0].strip().isdigit()


def read_sections(text: str) -> list[Section]:
    """Every table in a French CSV, each found by its header (a line starting with a comma).

    A table's title is the nearest non-blank line above its header. Its rows are the lines right
    below the header whose first field is an integer date, and it ends at the first other line.
    Every row must have one number per label, and all of a table's dates must have one width.
    """
    lines = text.splitlines()
    sections = []
    for i, line in enumerate(lines):
        if not line.strip().startswith(","):
            continue
        columns = tuple(label.strip() for label in line.strip().split(",")[1:])
        title = next((lines[j].strip() for j in range(i - 1, -1, -1) if lines[j].strip()), "")
        dates, rows = [], []
        for row in lines[i + 1:]:
            if not _is_row(row):
                break
            fields = row.split(",")
            if len(fields) != len(columns) + 1:
                raise ValueError(f"section {title!r}: row {fields[0].strip()} has {len(fields) - 1} values "
                                 f"for {len(columns)} labels")
            try:
                rows.append([float(field) for field in fields[1:]])
            except ValueError:
                raise ValueError(f"section {title!r}: row {fields[0].strip()} has a non-numeric value") from None
            dates.append(fields[0].strip())
        if len({len(date) for date in dates}) > 1:
            raise ValueError(f"section {title!r} mixes date formats")
        sections.append(Section(title, columns, tuple(dates), np.array(rows, dtype=float).reshape(-1, len(columns))))
    return sections


def _one_section(sections: list[Section], title: str | None = None, columns: Sequence[str] | None = None) -> Section:
    """The single monthly section with this title and/or labels; raises on zero or several matches."""
    matches = [s for s in sections if s.dates and s.monthly and (title is None or s.title == title)
               and (columns is None or s.columns == tuple(columns))]
    if len(matches) != 1:
        wanted = f"title {title!r}" if title is not None else f"labels {tuple(columns)}"
        raise ValueError(f"expected one monthly section with {wanted}, found {len(matches)}")
    return matches[0]


def month_index(dates: Sequence[str]) -> pd.PeriodIndex:
    """Monthly PeriodIndex for YYYYMM keys; raises unless they are valid, unique, increasing and consecutive."""
    if not dates:
        raise ValueError("no monthly rows")
    invalid = [d for d in dates if len(d) != 6 or not d.isdigit() or not 1 <= int(d[4:]) <= 12]
    if invalid:
        raise ValueError(f"invalid YYYYMM dates: {invalid[:5]}")
    ordinals = np.array([int(d[:4]) * 12 + int(d[4:]) - 1 for d in dates])
    breaks = np.flatnonzero(np.diff(ordinals) != 1)
    if breaks.size:
        k = breaks[0]
        raise ValueError(f"months are not consecutive: {dates[k]} is followed by {dates[k + 1]}")
    return pd.period_range(f"{dates[0][:4]}-{dates[0][4:]}", periods=len(dates), freq="M", name="month")


def _returns(section: Section) -> np.ndarray:
    """Percent returns as decimals, with the missing-data codes as NaN."""
    values = section.values
    if not np.isfinite(values).all():
        raise ValueError(f"section {section.title!r} has non-finite values")
    missing = np.isin(values, MISSING_CODES)
    impossible = ~missing & (values <= -100)
    if impossible.any():
        raise ValueError(f"section {section.title!r} has a return of -100% or below that is not a missing-data "
                         f"code: {values[impossible][:5]}")
    return np.where(missing, np.nan, values / 100)


def _counts(section: Section) -> np.ndarray:
    values = section.values
    if not np.isfinite(values).all() or (values < 0).any() or (values != np.round(values)).any():
        raise ValueError(f"section {section.title!r} must hold non-negative whole firm counts")
    return values.astype(np.int64)


@dataclass(frozen=True)
class Industries:
    """Monthly data from one industry file on one month index and one declared column order.

    vw and ew are returns in decimals (NaN where missing); firms holds the number of firms.
    missing_codes counts each missing-data code found in the two return sections.
    """

    vw: pd.DataFrame
    ew: pd.DataFrame
    firms: pd.DataFrame
    missing_codes: dict[float, int]


def parse_industries(text: str, columns: Sequence[str] | None = None) -> Industries:
    """The VW, EW and firm-count sections of an industry file, validated against one another.

    With columns given, every section's labels must equal them in order; otherwise the value-
    weighted section's labels are the reference. All three sections must list the same months.
    """
    sections = read_sections(text)
    found = {name: _one_section(sections, title=title) for name, title in INDUSTRY_SECTIONS.items()}
    labels = found["vw"].columns if columns is None else tuple(columns)
    if len(set(labels)) != len(labels) or "" in labels:
        raise ValueError(f"industry labels must be unique and non-empty: {labels}")
    for name, section in found.items():
        if section.columns != labels:
            raise ValueError(f"{name} labels {section.columns} differ from {labels}")
        if section.dates != found["vw"].dates:
            raise ValueError(f"{name} months differ from the value-weighted section's")
    index = month_index(found["vw"].dates)
    codes = {code: int(sum(np.count_nonzero(found[name].values == code) for name in ("vw", "ew")))
             for code in MISSING_CODES}

    def frame(values: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame(values, index=index, columns=list(labels))

    return Industries(frame(_returns(found["vw"])), frame(_returns(found["ew"])), frame(_counts(found["firms"])),
                      codes)


def parse_factors(text: str) -> pd.DataFrame:
    """Monthly benchmarks in decimals: mkt = (Mkt-RF) + RF, the VW market return, and rf, the T-bill return."""
    section = _one_section(read_sections(text), columns=FACTOR_COLUMNS)
    values = section.values
    if not np.isfinite(values).all() or np.isin(values, MISSING_CODES).any():
        raise ValueError("the monthly factors have missing values")
    mkt_rf, rf = values[:, 0] / 100, values[:, 3] / 100
    factors = pd.DataFrame({"mkt": mkt_rf + rf, "rf": rf}, index=month_index(section.dates))
    if (factors.to_numpy() <= -1).any():
        raise ValueError("a monthly benchmark return is -100% or below")
    return factors


def load_industries(key: str, paths: dict[str, Path] | None = None) -> Industries:
    """FF49 or FF12 from the verified cache, in the declared column order."""
    paths = verify_cache() if paths is None else paths
    return parse_industries(zipped_csv_text(paths[key].read_bytes()), INDUSTRY_COLUMNS[key])


def load_factors(paths: dict[str, Path] | None = None) -> pd.DataFrame:
    paths = verify_cache() if paths is None else paths
    return parse_factors(zipped_csv_text(paths["factors"].read_bytes()))


def require_same_months(frames: dict[str, pd.DataFrame]) -> pd.PeriodIndex:
    """The month index shared by every frame; raises if any differs, rather than joining."""
    (first_name, first), *rest = frames.items()
    for name, frame in rest:
        if not frame.index.equals(first.index):
            raise ValueError(f"{name} covers {frame.index[0]} to {frame.index[-1]} ({len(frame)} months), "
                             f"{first_name} covers {first.index[0]} to {first.index[-1]} ({len(first)} months)")
    return first.index


def load_all(paths: dict[str, Path] | None = None) -> tuple[dict[str, Industries], pd.DataFrame]:
    """Both industry universes and the factors from the verified cache, on identical months."""
    paths = verify_cache() if paths is None else paths
    industries = {key: load_industries(key, paths) for key in INDUSTRY_COLUMNS}
    factors = load_factors(paths)
    require_same_months({"factors": factors} | {f"{key} {name}": getattr(data, name)
                                                for key, data in industries.items()
                                                for name in ("vw", "ew", "firms")})
    return industries, factors


def formation_eligibility(firms: pd.DataFrame) -> pd.DataFrame:
    """Eligible industries per month under the July-count reconstruction assumption.

    An industry is eligible in month t when its firm count is positive in the July that starts
    t's formation year: July of the same year for July to December, of the previous year for
    January to June. Eligibility never depends on whether a return exists. Raises if a month's
    formation July is not in the data.
    """
    index = firms.index
    if not isinstance(index, pd.PeriodIndex) or index.freqstr != "M":
        raise ValueError("firm counts must be indexed by monthly periods")
    july = pd.PeriodIndex.from_ordinals(index.asi8 - np.asarray((index.month - 7) % 12), freq="M")
    absent = ~july.isin(index)
    if absent.any():
        raise ValueError(f"no firm counts for the formation July of {index[absent][0]} ({july[absent][0]})")
    counts = firms.to_numpy()[index.get_indexer(july)]
    return pd.DataFrame(counts > 0, index=index, columns=firms.columns)


def eligible_without_return(returns: pd.DataFrame, eligible: pd.DataFrame) -> pd.DataFrame:
    """(month, industry) pairs that are eligible but have no return, which must not happen."""
    if not (returns.index.equals(eligible.index) and returns.columns.equals(eligible.columns)):
        raise ValueError("returns and eligibility must share months and column order")
    rows, cols = np.nonzero(eligible.to_numpy() & returns.isna().to_numpy())
    return pd.DataFrame({"month": returns.index[rows], "industry": returns.columns[cols]})


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download the Ken French files into data/raw/.")
    parser.add_argument("--refresh", action="store_true", help="fetch the complete set again")
    args = parser.parse_args()
    paths = download_all(refresh=args.refresh)
    vintage = load_vintage()
    for key, path in paths.items():
        entry = vintage[key]
        print(f"{key:8s} {path.name:36s} {entry['bytes'] / 1e3:5.0f} KB  CRSP {entry['crsp_vintage']}  {entry['downloaded_utc']}")
