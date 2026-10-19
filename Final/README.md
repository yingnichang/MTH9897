# Replicating the Conservative Formula

**Yingni Chang and Yikai Shen**
MTH 9897 Systematic Trading, Project 8

We implement Blitz and van Vliet's Conservative Formula using monthly CRSP data. The paper comparison covers
1929-2016, and the extended backtest ends in December 2024. We examine net payout, industry positioning,
factor-adjusted returns and trading costs, then compare several portfolio rules.

The replication earns 14.80% compounded annually before costs, compared with the paper's 15.1%. Volatility is
17.06%, compared with 16.5%. The main unresolved difference is quarterly turnover: 38.9% versus 32%.
Recent net Carhart alpha is much weaker and its confidence interval includes zero. The notebook discusses
these results and the assumptions behind them.

## Files to read

| File | Purpose |
|---|---|
| [conservative_formula_first_draft.ipynb](conservative_formula_first_draft.ipynb) | Executed notebook and main course deliverable |
| [Written report](output/pdf/conservative_formula_report.pdf) | Methods, results, figures and discussion in PDF form |
| [Presentation](presentation/conservative_formula.pdf) | 22 slides for the final presentation |
| [Speech notes PDF](output/pdf/conservative_formula_speech_notes.pdf) | Read-aloud scripts for all 22 slides, presenter cues and likely questions |
| [Editable speech notes](presentation/speaker_notes.md) | The same scripts in Markdown, with per-slide timing |
| [Short speech notes PDF](output/pdf/conservative_formula_short_speech_notes.pdf) | A few sentences per slide for a shorter presentation |
| [Editable short notes](presentation/speaker_notes_short.md) | Brief scripts for all 22 slides |
| [Calculation checks](FINAL_REVIEW.md) | Paper comparison, data checks and independent return reconstruction |

The notebook's filename is retained from the initial draft, but it contains the completed analysis.
All project materials credit Yingni Chang and Yikai Shen. The reference paper and source data retain their own attribution.

## Main code

`research/run_all.py` is the main calculation entry point. From `Final/`, run:

```bash
python -m research.run_all
```

It runs 14 studies and saves their tables and figures in `results/`. Stock selection and baseline accounting
are in `research/engine.py`; the data import and cleaning code are in `crsp_pipeline/`.

`build_notebook.py` creates the notebook and `execute_notebook.py` runs its cells. `build_report_pdf.py` creates
the written report. `presentation/build_pdf.py` creates the PDF slides from saved results and a read-only layout template.
`presentation/build_speech_notes.py` creates the rehearsal PDF and editable script. Allow approximately 19-21 minutes for the full speech, plus questions; the short script takes about 7-9 minutes.

## Open the saved analysis

The notebook reads saved aggregate results, so it can run without the licensed stock-level data. Install
Python 3.12 and the dependencies, then execute the notebook:

```bash
python -m pip install -r requirements.txt
python execute_notebook.py
```

To regenerate the documents after editing their source:

```bash
python build_notebook.py
python execute_notebook.py
python build_report_pdf.py
python presentation/build_pdf.py
python presentation/build_speech_notes.py
python presentation/build_short_speech_notes.py
```

`requirements-lock.txt` records the tested versions. Some packages are Windows-specific; use
`requirements.txt` on another platform. The original PPTX is a read-only layout input. The updated presentation deliverable is the PDF; current scripts and notes target its 22 pages.

## Rebuild from the private data package

The private course ZIP is `output/submission/MTH9897_Conservative_Formula_Final.zip`. It contains the raw parquet
inputs, normalized inputs, code, notebook, report, slide and speech-note PDFs, and results. After extracting it, run from `Final/`:

```bash
python -m pip install -r requirements.txt
python -m crsp_pipeline build
python -m research.run_all
python build_notebook.py
python execute_notebook.py
python build_report_pdf.py
python presentation/build_pdf.py
python presentation/build_speech_notes.py
python presentation/build_short_speech_notes.py
python -m pytest tests -q
python package_submission.py
```

The full research run took about 16 minutes in the reviewed environment; runtime varies by machine. If you already
have normalized inputs, you can skip the data build. If starting with WRDS web archives, first run
`python -m crsp_pipeline.import_web`. Live extraction is also available with
`python -m crsp_pipeline extract --user <wrds_username>`; it requires a WRDS account and may require Duo authentication.

CRSP security-level data belong in the authorized course submission channel. GitHub contains source, aggregate
results and non-security-level audit tables. The ZIP, raw inputs, normalized panel and security-level worked examples
are excluded from Git.

## Data and portfolio assumptions

The normalized panel has 3,954,591 security-months for 26,746 securities, from December 1925 through December 2024.
We retain common shares on NYSE, AMEX and Nasdaq, use historical classifications, and choose one common share class
per company. The 36-month history screen comes before the largest-1,000 size cut. Only 393 eligible stocks exist at
the first formation; the universe first reaches 1,000 in June 1964.

Prices and shares are split-adjusted. Payout combines a trailing 12-month dividend yield with
`1 - current adjusted shares / 24-month average adjusted shares`. Dividends are inferred from total minus price
returns and checked against CRSP distributions. Net share changes include repurchases after issuance and may also
reflect other corporate actions.

We retain terminal returns and document missing delisting-return imputations. Missing history stays missing for
signals. Held positions instead use the recorded stale-price or price-ratio convention; they are not silently
deleted. Portfolio weights drift between rebalances, and terminal proceeds earn RF until reinvestment.

The original paper compares scores across sectors. We keep that global rule for the replication and study
industry neutrality separately. FF12 quotas, historical FF3 controls and the quadratic model were examined after
the baseline results and are exploratory. The recent data were already observed when these variants were tested.

## Studies and saved results

| Study | Contents |
|---|---|
| `data_audit` | Input coverage, cleaning counts and source receipts |
| `replication` | Paper-period returns, controls, turnover and deviations |
| `attribution` | CAPM, FF3, Carhart and FF5-plus-momentum regressions |
| `critical_tests` | Subperiods, costs, confidence intervals and rolling estimates |
| `paper_targets` | Direct comparisons with the paper's tables |
| `diagnostics` | Industry-adjusted IC, decay, persistence and deciles |
| `fmp` | Factor-mimicking portfolios with industry, size and historical FF3 controls |
| `longshort` | Holding periods, costs, borrow, trade ledgers and capacity |
| `optimization` | Linear optimization across industry, turnover and cost settings |
| `rank_buffer` | The 150-rank buffer and paired return differences |
| `mean_variance` | Quadratic optimization at two risk-aversion settings |
| `professor_checks` | Net payout, industry quotas, attribution and independent accounting |

`results/manifest.json` records all 85 aggregate files and their hashes, source files, dependencies and data identity.
The notebook and PDFs use the same saved results and reject modified files. Each completed study is checkpointed,
so an interrupted run can resume with selected studies. Cached security-level inputs also have verified producer identities.

```bash
python -m research.run_all --only critical_tests
python -m research.run_all --only critical_tests --with-deps
python -m research.run_all --only data_audit replication attribution paper_targets --end 2016-12-31 --results results_rehearsal
```

The first command requires current dependencies; `--with-deps` rebuilds missing or stale ones. The last command
runs the paper-period comparison in a separate directory. Studies that require the complete 2024 sample reject
a shorter end date before writing results.

For an offline synthetic example, set `CF_MODE=demo` before running `execute_notebook.py`; it writes
`output/demo_run.ipynb` and does not replace the empirical notebook. To rebuild the research from inside the
empirical notebook, set `CF_RECOMPUTE=1` before starting its kernel.

Capacity figures use monthly volume and a normalization to December 2024 market size, not CPI-adjusted dollars.
They omit market impact and actual borrow availability. The calculation checks document the other unresolved
data and modeling limitations.

## Follow-up after the presentation

The updated notebook and report add a fixed 0-30 bps grid in 5-bps steps, annual returns and rolling time-series
comparisons for 2017-2024. A separate model scales costs with previous-month CRSP closing bid-ask spreads relative
to a fixed 2016 reference. This describes changing liquidity without claiming actual execution prices or a forecast.

`research/studies/feedback_costs.py` runs those tests. `research/studies/uk_comparison.py` applies the formula to
Compustat Global UK ordinary London GBP shares. Its raw 2013-2024 daily export provides warm-up history for
January 2017 returns. `data/uk_source.json` records query 11803424, variables and the download hash. The private ZIP
includes that raw export and the original CRSP quote export needed for a full rebuild. These licensed observations
are excluded from GitHub.

The UK test reports an own-universe capitalization-weighted comparator, an exit-loss stress, a top-10% holding
sensitivity, and a separate 0.5% purchase-side SDRT scenario in addition to ordinary trading costs. Local GBP/US USD
returns, different benchmarks, current UK classifications and incomplete UK terminal payments limit inference.
No UK factor alpha or Sharpe is claimed. This is a sample comparison, not a verified country effect.

Recompute only the follow-up analyses from private inputs:

```bash
python -m research.run_all --only feedback_costs uk_comparison
```

The new slides are pages 18-22; the final presentation ends with the UK/US results. Both speech-note versions match all 22 pages.
The main stock-selection rule and earlier US results are unchanged.
