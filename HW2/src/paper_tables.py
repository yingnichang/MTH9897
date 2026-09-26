"""Rebuild data/paper/table1.csv and table4.csv from the text of the paper's PDF.

Both tables are parsed from pypdf's text extraction rather than typed by hand. The PDF writes
minus signs as the Unicode en dash (Table 1) or hyphen followed by a space (Table 4, e.g.
"‐ 0.09"); both become an ordinary minus. It also uses non-breaking spaces, which become spaces. Percentages are divided by 100, so every value is a
decimal: simple returns (Table 4's 9498.26 is 949,826%), outcome fractions (0.5359 is 53.59%),
or dimensionless skewness.

Run from HW2 with: python src/paper_tables.py          (write both CSVs)
                   python src/paper_tables.py --check  (compare with the saved CSVs)
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

HW2_DIR = Path(__file__).resolve().parents[1]
PDF_PATH = HW2_DIR / "Do stocks outperform treasury bills.pdf"
PAPER_DIR = HW2_DIR / "data" / "paper"

# 1-based PDF page numbers (the paper's own printed numbers are one lower for Table 4).
TABLE1_PAGE = 43
TABLE4_PAGE = 50

_CHARACTERS = str.maketrans({"‐": "-", "‑": "-", "–": "-", "−": "-", "\xa0": " "})


def normalize(text: str) -> str:
    """Map the PDF's dashes to '-' and non-breaking spaces to spaces; join a minus sign to its number."""
    return re.sub(r"-\s+(?=\d)", "-", text.translate(_CHARACTERS))


def _number(token: str) -> float:
    value = float(token.rstrip("%"))
    return round(value / 100.0 if token.endswith("%") else value, 8)


def page_text(page: int, pdf_path: Path = PDF_PATH) -> str:
    from pypdf import PdfReader

    return normalize(PdfReader(pdf_path).pages[page - 1].extract_text())


def parse_table1(text: str) -> list[tuple]:
    """Rows (stat, horizon_years, sigma, value) of Table 1: 4 panels x 3 horizons x 11 sigmas."""
    panels = {"Panel A": "skew", "Panel B": "median", "Panel C": "pct_positive", "Panel D": "p99"}
    sigmas = [round(0.02 * k, 2) for k in range(11)]
    rows, stat = [], None
    for line in text.splitlines():
        stat = next((name for key, name in panels.items() if key in line), stat)
        parts = line.split()
        if stat and len(parts) == 12 and parts[0] in ("1", "5", "10"):
            rows += [(stat, int(parts[0]), sigma, _number(p)) for sigma, p in zip(sigmas, parts[1:])]
    if len(rows) != 132:
        raise ValueError(f"expected 132 Table 1 values, parsed {len(rows)}")
    return rows


def parse_table4(text: str) -> list[tuple]:
    """Rows (stat, horizon_years, n_stocks, value) of Table 4: 5 sizes x 6 statistics x 3 horizons."""
    sizes = {"single-stock": 1, "5-stock": 5, "25-stock": 25, "50-stock": 50, "100-stock": 100}
    labels = {"% > 0": "pct_positive", "% > T-bill": "pct_above_tbill", "% > VW mkt": "pct_above_vw"}
    horizons = (1, 10, 90)
    values: dict[int, dict[str, list[float]]] = {}
    n_stocks = None
    for line in text.splitlines():
        line = line.strip()
        match = re.match(r"Bootstrapped (\S+) (?:positions|portfolios)", line)
        if match:
            n_stocks = sizes[match.group(1)]
            values[n_stocks] = {}
        elif line.startswith("Holding return") and n_stocks is not None:
            numbers = [_number(p) for p in line.split()[2:]]
            if len(numbers) != 9:
                raise ValueError(f"expected 9 holding-return values, got {line!r}")
            for offset, stat in enumerate(("mean", "median", "skew")):
                values[n_stocks][stat] = numbers[offset::3]
        elif n_stocks is not None:
            for label, stat in labels.items():
                if line.startswith(label + " "):
                    values[n_stocks][stat] = [_number(p) for p in line[len(label):].split()]
    order = ("mean", "median", "skew", "pct_positive", "pct_above_tbill", "pct_above_vw")
    rows = [(stat, h, n, v) for n in sizes.values() for stat in order
            for h, v in zip(horizons, values[n][stat], strict=True)]
    if len(rows) != 90:
        raise ValueError(f"expected 90 Table 4 values, parsed {len(rows)}")
    return rows


def to_csv(header: list[str], rows: list[tuple]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def build(pdf_path: Path = PDF_PATH) -> dict[str, str]:
    """CSV text of both tables, keyed by file name."""
    return {
        "table1.csv": to_csv(["stat", "horizon_years", "sigma", "value"],
                             parse_table1(page_text(TABLE1_PAGE, pdf_path))),
        "table4.csv": to_csv(["stat", "horizon_years", "n_stocks", "value"],
                             parse_table4(page_text(TABLE4_PAGE, pdf_path))),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Rebuild the paper's Tables 1 and 4 as CSV.")
    parser.add_argument("--check", action="store_true", help="compare with the saved CSVs instead of writing")
    args = parser.parse_args()
    for name, text in build().items():
        path = PAPER_DIR / name
        if args.check:
            saved = path.read_text().replace("\r\n", "\n")
            print(f"{name}: {'matches' if saved == text else 'DIFFERS FROM'} {path}")
        else:
            path.write_text(text, newline="\n")
            print(f"wrote {path}")
