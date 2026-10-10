# Conservative Formula — final project

Open `conservative_formula_first_draft.ipynb` in JupyterLab or VS Code from this `Final` folder.
Install the packages in `requirements.txt`, then restart the kernel and run all cells.

The notebook runs offline in **demo mode**. Saved outputs use seeded synthetic data, not CRSP or
real investment results. Setting `MODE = "crsp"` reads the normalized CRSP panel produced by the
pipeline below. The previous homework folders are not inputs to this project.

`build_notebook.py` rebuilds the unexecuted notebook; do not run it over your edited notebook
without preserving your changes. Outputs go to `output/demo/` or `output/crsp/`.

## CRSP data pipeline

`crsp_pipeline/` extracts the US stock data from WRDS, normalizes them to the notebook's input
contract, and writes audit tables and a provenance manifest. Run every command from `Final/`.

```bash
python -m crsp_pipeline extract --user <wrds_username>   # WRDS -> data/raw/*.parquet  (~10-20 min)
python -m crsp_pipeline build                            # data/raw -> panel, benchmark, audits (~1-2 min)
python -m pytest tests -q                                # deterministic fixture tests
```

**Credentials.** The extractor connects directly to WRDS PostgreSQL
(`wrds-pgdata.wharton.upenn.edu:9737`, SSL). It takes the password from `WRDS_PASSWORD`, from
the standard pgpass file (`%APPDATA%\postgresql\pgpass.conf` on Windows, one line:
`wrds-pgdata.wharton.upenn.edu:9737:wrds:<user>:<password>`), or from an interactive prompt.
WRDS may send a Duo push on the first connection. The `wrds` Python package is deliberately
not used: it pins pandas below 2.3, and the notebook is tested with pandas 3.0.6.

**Status (2026-10-09).** The pipeline has run against WRDS (extracted 2026-10-10 01:16 UTC;
`crsp.msf` ends 2024-12-31). The panel has 3,954,476 security-months for 26,746 securities, and all
build invariants pass. In the audits, implied dividends agree with `msedist` cash distributions in
more than 99% of rows, the CRSP and Fama–French market series correlate above 0.996 in every
decade, and only 110 delisting returns required imputation. Two findings affect the backtest. First,
fewer than 1,000 history-eligible common stocks exist before June 1964 (393 at the December 1928
formation). Second, 447 holding-period months of universe members have a CRSP record with a missing
return. Both require a documented convention before the empirical backtest is run.

### Sources

Legacy-format (SIZ) CRSP monthly tables in schema `crsp` (override with `--library`):

| Table | Fields | Use |
|---|---|---|
| `msf` | permno, permco, date, ret, retx, prc, shrout, cfacpr, cfacshr, vol | returns, prices, shares, adjustment factors |
| `msenames` | permno, permco, namedt, nameendt, shrcd, exchcd, siccd, ticker, comnam, shrcls | point-in-time security type, exchange, industry |
| `msedelist` | permno, dlstdt, dlstcd, dlret, dlretx, dlprc, nwperm | terminal returns |
| `msedist` | permno, distcd, divamt, facpr, facshr, exdt, ... | independent dividend cross-check |
| `msi` | date, vwretd, ... | CRSP value-weighted market including distributions |
| `ff.factors_monthly` | dateff, mktrf, smb, hml, rf, umd | one-month T-bill rate; factors for later attribution |

The extract covers every security that ever had share code 10 or 11, for all months from
1925-12-31 through 2024-12-31. Eligibility is then applied month by month, so a stock that leaves
the universe keeps its subsequent holding-period returns. The legacy files were frozen at the
December 2024 release, which fixes the endpoint. CRSP's newer CIZ files compute monthly returns
and delistings differently, and support for them is not implemented. Before querying, the extractor
checks every table's columns against `information_schema` and stops if a field is missing.
`data/raw/extract_log.json` records the SQL, row counts, file hashes, extract time, and the latest
`msf` date.

### Normalization conventions

| Item | Convention |
|---|---|
| Dates | CRSP last-trading-day stamps converted to calendar month ends |
| Classification | `msenames` matched point in time (`namedt ≤ date ≤ nameendt`); never header codes |
| Eligible | name record, share code 10/11, exchange 1/2/3, positive price and shares, not a terminal row, and the largest common-stock class of its PERMCO that month |
| History | `hist36`: 36 calendar-consecutive non-missing total returns ending at the formation month (paper p. 4). The paper screens on history **before** the top-1,000 capitalization cut |
| Total return | `msf.ret`; in the delisting month compounded once with the delisting return, `(1+ret)(1+dlret)−1`. A row is appended if CRSP has no monthly row for that month. Rows after a delisting month are dropped and counted |
| Missing delisting return | performance codes 500 and 520–584: −30% (NYSE/AMEX) or −55% (NASDAQ), following Shumway (1997) and Shumway and Warther (1999); other codes: 0. Every case is flagged in `delist_source` |
| Adjusted price / shares | `price_adj = abs(prc)/cfacpr`, `shares_adj = shrout × cfacshr`; a split changes neither |
| Dividends | `div_cash_adj = (ret − retx) × price_adj[t−1]`. Equal `ret` and `retx` gives a confirmed zero; a missing input or calendar gap gives NaN (unknown) |
| Market cap | `mktcap = abs(prc) × shrout / 1000` in USD millions (security); `mktcap_company` sums the PERMCO's common classes |
| Industry | Fama–French 12 from point-in-time SIC; missing or zero SIC is `Unknown`, kept separate from `Other` |
| Benchmark | `market_ret` = CRSP `vwretd`, `rf` = Fama–French `rf`; decimal monthly; full contiguous coverage from 1926-07 through the endpoint is asserted |

`crsp_pipeline/signals.py` implements the notebook's Section 4 signals in vectorized form. A test
checks that it matches the notebook's loop implementation on the fixtures. The net-issuance
denominator is the mean of the 24 share counts *including* the formation month.

### Outputs

| File | Content |
|---|---|
| `data/crsp_monthly_normalized.parquet` | security-month panel: the notebook's contract columns plus `permco`, codes, `ff12`, `hist36`, `mktcap_company`, raw CRSP fields, delisting fields, `exclusion` reason |
| `data/benchmark_monthly.csv` | `date, market_ret, rf` |
| `data/ff_factors_monthly.csv` | Fama–French 3 factors, momentum, and rf |
| `data/audit/formation_coverage.csv` | quarter-end eligible and universe counts. Compares the history-first universe with the notebook's current cap-first ordering, and reports industry coverage |
| `data/audit/exclusions_by_decade.csv` | quarter-end rows by exclusion reason |
| `data/audit/missingness_by_decade.csv` | missing returns, dividends, shares, and industry among eligible rows |
| `data/audit/delistings.csv` | events by code category, return source, placement, and prior-quarter universe membership |
| `data/audit/dividend_reconciliation.csv` | implied dividends against `msedist` cash distributions, under two distribution-code definitions |
| `data/audit/benchmark_check.csv` | CRSP VW against Fama–French market by decade |
| `data/audit/worked_examples.csv` | raw fields and payout signals: IBM (payer), AAPL 2020 split, Berkshire classes, largest issuer, repurchaser, and delistings |
| `data/manifest.json` | code commit, conventions, sample counts, output hashes, embedded extract log |

`data/raw/` and the parquet panel are git-ignored because of their size; the GitHub file limit is
100 MB. The raw files and panel must reach the grader through the course-approved channel. CRSP
license terms apply.

### Next work, in order

1. Decide the treatment of the pre-1964 universe shortfall and of missing returns for held stocks.
2. In the notebook, screen on `hist36 & eligible` before taking the 1,000 largest (critique item 3).
   Switch to `crsp_pipeline.signals.build_signals`; the per-security loop is slow at CRSP scale.
3. Add expected-calendar and initial-formation checks to the backtest (critique item 7). Then
   run 1929–2016 for comparison with the paper, before extending to 2024.

## Reference-paper review

The [paper-alignment review](PAPER_ALIGNMENT_REVIEW.md) compares this draft
with the March 2018 reference paper and the Project 8 requirements. It documents
the supported share-count payout method, needed universe-selection changes,
missing paper comparisons, and the priorities for a real CRSP replication.
These are review findings and proposed revisions; the notebook remains the
original synthetic first draft.

## Presentation

The [22-slide PDF](presentation/conservative_formula_presentation.pdf) accompanies the first
draft; its numbers are the synthetic demonstration and are labeled as such. The
[presentation folder](presentation/) contains the generator source, data snapshot, speaker notes,
and rebuild instructions.
