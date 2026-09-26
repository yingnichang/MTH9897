"""Audit of the pinned August 2026 Ken French snapshot against the data facts in Plan.md (Step 7).

ff_data.py validates structure and parses any well-formed file. This module checks facts about
one specific release, so it is meant to fail when a refresh changes them. Before the pin is
moved, the facts and everything that relies on them must be reviewed again.

Every check is computed from the parsed data; the audit table reports what was observed, and
require_audit stops the analysis if any fact fails.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ff_data import (FILES, Industries, _first_line, crsp_vintage, eligible_without_return, formation_eligibility,
                     zipped_csv_text)

RELEASE = "202608"
FIRST_MONTH, LAST_MONTH, N_MONTHS = pd.Period("1926-07", "M"), pd.Period("2026-08", "M"), 1202

# FF49 industries without firms in July 1926, and the first July in which each has firms.
FF49_LATE_STARTS = {"PerSv": 1927, "Paper": 1929, "Rubbr": 1930, "Soda": 1963, "FabPr": 1963, "Guns": 1963,
                    "Gold": 1963, "Softw": 1965, "Hlth": 1969}
FF49_ALL_FROM = pd.Period("1969-07", "M")
# The only zero-firm spell after an industry's first appearance: (industry, first month, last month).
FF49_ZERO_SPELLS = [("Rubbr", pd.Period("1943-07", "M"), pd.Period("1944-06", "M"))]
# The only month in which the number of eligible industries falls: (month, before, after).
FF49_ELIGIBLE_DROPS = [(pd.Period("1943-07", "M"), 43, 42)]
# Industries with a single firm: counts in two months, and the last such month overall and among
# the 40 industries present in July 1926.
FF49_SINGLE_FIRM = {pd.Period("1926-07", "M"): 5, pd.Period("1940-01", "M"): 3}
FF49_LAST_SINGLE = ("Softw", pd.Period("1973-06", "M"))
FF49_LAST_SINGLE_ORIGINAL = ("Insur", pd.Period("1963-06", "M"))
FF12_MIN_FIRMS = 4

# Compounded benchmark returns over the paper's sample (1,086 months), in decimals, to 4 places.
PAPER_SAMPLE = (pd.Period("1926-07", "M"), pd.Period("2016-12", "M"))
TBILL_RETURN = 19.2797
MARKET_RETURN = 5031.7488

# Largest |EW - VW| in a single-firm industry-month: the files round returns to 0.01 percentage points.
ROUNDING = 0.0001


class AuditError(ValueError):
    """The cached data no longer match a fact the analysis relies on."""


def _month(period: pd.Period) -> str:
    return period.strftime("%b %Y")


def _last_month(mask: pd.Series) -> pd.Period | None:
    hits = np.flatnonzero(mask.to_numpy())
    return mask.index[hits[-1]] if hits.size else None


def _zero_spells(firms: pd.DataFrame) -> list[tuple[str, pd.Period, pd.Period]]:
    """Runs of zero-firm months that start after an industry's first month with firms."""
    spells = []
    for name, counts in firms.items():
        present = counts.to_numpy() > 0
        if not present.any():
            continue
        start = None
        for k in range(int(np.argmax(present)), len(present)):
            if not present[k] and start is None:
                start = k
            elif present[k] and start is not None:
                spells.append((name, counts.index[start], counts.index[k - 1]))
                start = None
        if start is not None:
            spells.append((name, counts.index[start], counts.index[-1]))
    return spells


def _spells_text(spells) -> str:
    return "; ".join(f"{name} {_month(a)} to {_month(b)}" for name, a, b in spells) or "none"


def _count_changes(firms: pd.DataFrame) -> dict[str, int]:
    """Industry-months outside July in which a firm count rises, or falls to zero."""
    previous = firms.shift().to_numpy()
    current = firms.to_numpy()
    not_july = (firms.index.month != 7)[:, None]
    return {"rises": int((not_july & (current > previous)).sum()),
            "to_zero": int((not_july & (previous > 0) & (current == 0)).sum())}


def _common_rows(key: str, data: Industries, eligible: pd.DataFrame) -> list[tuple]:
    """Facts shared by both universes."""
    ew_missing, vw_missing = data.ew.isna().to_numpy(), data.vw.isna().to_numpy()
    changes = _count_changes(data.firms)
    gaps = len(eligible_without_return(data.ew, eligible)) + len(eligible_without_return(data.vw, eligible))
    codes = data.missing_codes
    return [
        (key, "Missing-data codes: only −99.99 occurs, never −999",
         f"−99.99: {codes[-99.99]:,}; −999: {codes[-999.0]:,}", codes[-999.0] == 0),
        (key, "EW and VW are missing in the same industry-months",
         f"{int((ew_missing != vw_missing).sum())} mismatches", bool((ew_missing == vw_missing).all())),
        (key, "Returns are missing exactly where the firm count is zero",
         f"{int((vw_missing != (data.firms.to_numpy() == 0)).sum())} mismatches",
         bool((vw_missing == (data.firms.to_numpy() == 0)).all())),
        (key, "Firm counts rise only in July, and fall to zero only in July",
         f"{changes['rises']} rises and {changes['to_zero']} falls to zero outside July",
         changes["rises"] == 0 and changes["to_zero"] == 0),
        (key, "Every eligible industry-month has EW and VW returns (formation rule)",
         f"{gaps} eligible industry-months without a return", gaps == 0),
    ]


def _ff49_rows(data: Industries, eligible: pd.DataFrame) -> list[tuple]:
    firms, index = data.firms, data.firms.index
    july = firms[index.month == 7]
    first_july = {name: int(july.index[np.argmax(counts.to_numpy() > 0)].year)
                  for name, counts in july.items() if (counts > 0).any()}
    late = {name: year for name, year in first_july.items() if year > FIRST_MONTH.year}
    late_text = ", ".join(f"{name} {year}" for name, year in sorted(late.items(), key=lambda item: item[1]))
    present_1926 = int((firms.iloc[0] > 0).sum())

    last_zero = _last_month((firms == 0).any(axis=1))
    all_from = index[0] if last_zero is None else last_zero + 1

    spells = _zero_spells(firms)

    count = eligible.sum(axis=1)
    steps = [(month, int(count.iloc[k - 1]), int(count.iloc[k])) for k, month in enumerate(index) if k]
    drops = [step for step in steps if step[2] < step[1]]
    rises = [step for step in steps if step[2] > step[1]]
    full_from = rises[-1][0] if rises else index[0]
    drops_text = "; ".join(f"{_month(m)} {a}→{b}" for m, a, b in drops) or "none"
    back = FF49_ZERO_SPELLS[0][2] + 1

    single = firms == 1
    single_counts = {month: int(single.loc[month].sum()) for month in FF49_SINGLE_FIRM}
    original = firms.columns[firms.iloc[0] > 0]

    def last_single_firm(columns) -> tuple[str, pd.Period | None]:
        month = _last_month(single[columns].any(axis=1))
        return ("none", None) if month is None else (", ".join(c for c in columns if single.loc[month, c]), month)

    last_original, last_overall = last_single_firm(original), last_single_firm(firms.columns)
    gaps = (data.ew - data.vw).abs().to_numpy()[single.to_numpy()]
    max_gap = float(np.nanmax(gaps)) if gaps.size else 0.0

    return [
        ("ff49", "Industries with firms in Jul 1926: 40", f"{present_1926}", present_1926 == 40),
        ("ff49", "First July with firms for the other nine: "
         + ", ".join(f"{name} {year}" for name, year in FF49_LATE_STARTS.items()),
         late_text, late == FF49_LATE_STARTS),
        ("ff49", f"All 49 have firms in every month from {_month(FF49_ALL_FROM)}",
         f"from {_month(all_from)}", all_from == FF49_ALL_FROM),
        ("ff49", "Only zero-firm spell after a first appearance: " + _spells_text(FF49_ZERO_SPELLS),
         _spells_text(spells), spells == FF49_ZERO_SPELLS),
        ("ff49", f"Eligible industries: 40 in Jul 1926, 49 from {_month(FF49_ALL_FROM)}; the only decrease is "
         + "; ".join(f"{a}→{b} in {_month(m)}" for m, a, b in FF49_ELIGIBLE_DROPS) + f" (back in {_month(back)})",
         f"{int(count.iloc[0])} in {_month(index[0])}; {int(count.iloc[-1])} from {_month(full_from)}; "
         f"decreases: {drops_text}",
         int(count.iloc[0]) == 40 and full_from == FF49_ALL_FROM and drops == FF49_ELIGIBLE_DROPS
         and bool((count.loc[FF49_ALL_FROM:] == 49).all())),
        ("ff49", "Single-firm industries: 5 in Jul 1926, 3 in Jan 1940; last among the original 40 "
         f"{_month(FF49_LAST_SINGLE_ORIGINAL[1])} ({FF49_LAST_SINGLE_ORIGINAL[0]}), last overall "
         f"{_month(FF49_LAST_SINGLE[1])} ({FF49_LAST_SINGLE[0]})",
         " and ".join(str(n) for n in single_counts.values())
         + f"; {_month(last_original[1])} ({last_original[0]}), {_month(last_overall[1])} ({last_overall[0]})",
         single_counts == FF49_SINGLE_FIRM and last_original == FF49_LAST_SINGLE_ORIGINAL
         and last_overall == FF49_LAST_SINGLE),
        ("ff49", "Single-firm industry-months: EW equals VW up to the files' rounding (0.01 pp)",
         f"max |EW − VW| = {100 * max_gap:.4f} pp over {int(single.to_numpy().sum()):,} industry-months",
         max_gap <= ROUNDING + 1e-12),
    ]


def _ff12_rows(data: Industries, eligible: pd.DataFrame) -> list[tuple]:
    min_firms = int(data.firms.to_numpy().min())
    n_missing = int(data.ew.isna().to_numpy().sum() + data.vw.isna().to_numpy().sum())
    count = eligible.sum(axis=1)
    return [
        ("ff12", "No missing EW or VW returns", f"{n_missing} missing", n_missing == 0),
        ("ff12", f"At least {FF12_MIN_FIRMS} firms in every industry-month", f"minimum {min_firms}",
         min_firms >= FF12_MIN_FIRMS),
        ("ff12", "Eligible industries: 12 in every month", f"{int(count.min())} to {int(count.max())}",
         bool((count == 12).all())),
    ]


def snapshot_audit(paths: dict[str, Path], industries: dict[str, Industries], factors: pd.DataFrame) -> pd.DataFrame:
    """One row per fact: file, fact (the expectation), observed (from the data) and ok."""
    releases = [crsp_vintage(_first_line(zipped_csv_text(paths[key].read_bytes()))) for key in FILES]
    index = factors.index
    sample = factors.loc[PAPER_SAMPLE[0]:PAPER_SAMPLE[1]]
    tbill, market = float((1 + sample["rf"]).prod() - 1), float((1 + sample["mkt"]).prod() - 1)
    eligible = {key: formation_eligibility(data.firms) for key, data in industries.items()}

    rows = [
        ("all", f"CRSP release {RELEASE} in every file header", ", ".join(str(r) for r in releases),
         all(r == RELEASE for r in releases)),
        ("all", f"Months: {_month(FIRST_MONTH)} to {_month(LAST_MONTH)} ({N_MONTHS:,}), identical in all files",
         f"{_month(index[0])} to {_month(index[-1])} ({len(index):,})",
         (index[0], index[-1], len(index)) == (FIRST_MONTH, LAST_MONTH, N_MONTHS)
         and all(data.vw.index.equals(index) for data in industries.values())),
        ("factors", f"Compounded T-bill return, Jul 1926 to Dec 2016 ({len(sample):,} months): {TBILL_RETURN:.4f}",
         f"{tbill:.4f}", len(sample) == 1086 and abs(tbill - TBILL_RETURN) < 5e-5),
        ("factors", f"Compounded VW market return, same months: {MARKET_RETURN:.4f}", f"{market:.4f}",
         abs(market - MARKET_RETURN) < 5e-5),
    ]
    rows += _common_rows("ff49", industries["ff49"], eligible["ff49"]) + _ff49_rows(industries["ff49"], eligible["ff49"])
    rows += _common_rows("ff12", industries["ff12"], eligible["ff12"]) + _ff12_rows(industries["ff12"], eligible["ff12"])
    table = pd.DataFrame(rows, columns=["file", "fact", "observed", "ok"])
    table["ok"] = table["ok"].astype(bool)
    return table


def require_audit(table: pd.DataFrame) -> pd.DataFrame:
    """The audit table if every fact holds; otherwise raise, naming the facts that failed."""
    failed = table[~table["ok"]]
    if len(failed):
        lines = "\n".join(f"  [{r.file}] {r.fact}: observed {r.observed}" for r in failed.itertuples())
        raise AuditError(f"{len(failed)} data fact(s) failed; review Plan.md before using this release:\n{lines}")
    return table
