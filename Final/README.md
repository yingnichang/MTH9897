# Conservative Formula — final project

> **⚠ Important update (2026-10-10): research question.** This project is a **critical
> replication** of Blitz & van Vliet (2018), not a demonstration that a simple formula beats the
> market. A 1929–2016 replication shows whether the paper's US results can be reproduced. That is the
> benchmark, not the conclusion. The conclusion then answers three questions:
>
> 1. **Known factors.** Is the return only a bundle of known premia (low volatility, momentum,
>    payout)? The primary measure is the Carhart four-factor alpha, with FF5 + momentum as a
>    robustness check. CAPM alpha is reported only for comparison with the paper.
> 2. **Decay.** Has performance weakened over time? Results are reported for fixed subperiods
>    (1929–1962, 1963–1989, 1990–2016, 2017–2024, the last after the paper's sample), with rolling
>    10-year excess return and alpha. The headline conclusion uses **1990–2024**.
> 3. **Costs.** How much survives realistic trading costs? Results are reported net at 10 and
>    30 bps, with the break-even cost per dollar traded for each subperiod.
>
> The subperiods and measures were fixed before any CRSP backtest result was seen. Long-sample
> averages can be driven by early, less efficient markets with small universes and high real costs,
> and published anomalies often weaken after publication.

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

**Status (2026-10-10).** The pipeline has run against WRDS (extracted 2026-10-10 01:16 UTC;
`crsp.msf` ends 2024-12-31). The panel has 3,954,476 security-months for 26,746 securities, and all
build invariants pass. In the audits, implied dividends agree with `msedist` cash distributions in
more than 99% of rows, the CRSP and Fama–French market series correlate above 0.996 in every
decade, and only 110 delisting returns required imputation. Two findings affect the backtest. First,
fewer than 1,000 history-eligible common stocks exist before June 1964 (393 at the December 1928
formation); the universe then takes all history-eligible names. Second, 447 holding-period months
of universe members (356 securities, 403 runs of consecutive missing months) have a CRSP record
with a missing return, mostly no-trade months on the NYSE before 1950 and a few suspensions. They
are handled by stale-price carry (`ret_hold`, below). In 239 of these months the gap ends inside
the same holding quarter. When CRSP reports no price inside the gap, its resumption return covers
the whole gap, and buy-and-hold is reproduced. When CRSP shows a price but no return in a gap month,
its resumption return starts from that price. Such a month therefore earns the price ratio to the
last price if that price is at most three months old; this covers 3 holding months (July 1962:
+2.7%, +2.2% and −3.5%), which then also reproduce buy-and-hold, apart from distributions inside the
gap, which are unknown. Four longer runs that show a price in the gap have no price within three
months; they all straddle a rebalance, and their move into the in-gap price is recorded as zero.
Two further runs fail the audit's price-only check only because a special distribution fell in
the gap; CRSP's return includes it and is correct. In the other 208 months the gap straddles a
rebalance: the price change during the gap is lost, and the position is rebalanced at its last
traded price (`data/audit/missing_returns.csv`). The backtest does not yet use `ret_hold`.

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
| Holding return | `ret_hold`, with `ret_hold_source`: `ret_total` where observed (`crsp`, every terminal row included). In a missing-return month after the security's first row: if CRSP reports a positive price that month and the last positive price is at most 3 calendar months earlier, the price-only ratio `price_adj[t] / price_adj[last] − 1` (`price_ratio`; distributions inside the gap are unknown); otherwise 0 (`stale_carry`: the position is held at its last price). The resumption month keeps CRSP's return: for gaps of up to 10 months with no price inside the gap, that return spans the gap; if CRSP shows a price in a gap month, it starts from that price, which `price_ratio` picks up when the last price is recent enough and which otherwise is recorded as a zero move. NaN on a first row without a return (`no_prior_row`). `ret_total`, `hist36` and the signals keep the missing value, so a gap still breaks every signal window. Counts by decade in `missing_returns.csv` |
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
| `data/audit/missing_returns.csv` | missing-return months by `ret_hold_source`; universe holding months with a missing return (stale carry or in-gap price ratio), split into gaps that end within the quarter and gaps that straddle a rebalance; run lengths; whether CRSP's resumption return spans the gap, and for checkable runs that do not, whether CRSP shows a price in the gap (aggregate counts only) |
| `data/audit/delistings.csv` | events by code category, return source, placement, and prior-quarter universe membership |
| `data/audit/dividend_reconciliation.csv` | implied dividends against `msedist` cash distributions, under two distribution-code definitions |
| `data/audit/benchmark_check.csv` | CRSP VW against Fama–French market by decade |
| `data/audit/worked_examples.csv` | raw fields and payout signals: IBM (payer), AAPL 2020 split, Berkshire classes, largest issuer, repurchaser, and delistings |
| `data/manifest.json` | code commit, conventions, sample counts, output hashes, embedded extract log |

`data/raw/` and the parquet panel are git-ignored because of their size; the GitHub file limit is
100 MB. The raw files and panel must reach the grader through the course-approved channel. CRSP
license terms apply.

### Next work, in order

1. Use `ret_hold` for holding-period returns in the backtest.
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
