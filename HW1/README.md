# MTH9897 Bond Relative Value Assignment

This repository contains the executed Jupyter notebook for the WRDS corporate bond relative-value homework. The analysis applies the issuer-curve, weighted-calibration, DV01-hedging, accrued-interest, liquidity, and trading-cost ideas Professor Boroditsky discussed in class.

## Files

- `bond_relative_value_assignment.ipynb`: executed notebook with an auditable price-quality screen, reliability-weighted spread curves, rich/cheap diagnostics, three DV01-neutral portfolio passes, dollar PnL, turnover, and transaction-cost sensitivity.
- `output/pdf/MTH9897_Bond_Relative_Value_Report.pdf`: standalone academic report that explains the data correction, compares the raw and cleaned backtests, and interprets the result conservatively.
- `scripts/generate_pdf_report.py`: one-command entry point that executes the notebook analysis, rebuilds the report figures, writes the PDF, and validates the result.
- `scripts/report/`: report data extraction, chart generation, and ReportLab layout code.

## Headline Result

The notebook evaluates three portfolio passes across AAPL, AMZN, BA, CAT, DIS, and T from August 2022 through March 2025. A two-sided price-quality check identifies one isolated Apple month-end mark: CUSIP `037833BX7` falls from 91.76 to 25.17 in February 2025 and returns to 92.24 in March. The main analysis excludes that mark before both curve fitting and return construction, while preserving the untouched backtest as a sensitivity check.

After cleaning, gross annualized returns are 0.15% for the baseline top-three portfolio, 0.39% for the concentrated top-two portfolio, and 0.10% for the liquidity-aware top-three portfolio. Pass 2 has the strongest cleaned gross result, but its annualized return falls to -1.98% after an illustrative 25 bp one-way turnover charge. The earlier unfiltered returns of 2.75%, 4.48%, and 5.99% are reported only to show how strongly one bad mark distorted the original backtest.

## Data

The source WRDS CSV files are committed at the repository root and are read from there directly:

- `WRDS_Data-Systematic_Trading-Fall2026-1.csv`
- `WRDS_Data-Systematic_Trading-Fall2026-2.csv`

The class PDF is not committed. The notebook cites the relevant slides without redistributing the source material.

## Rebuild the PDF Report

Install the report dependencies and run the generator from the repository root:

```powershell
python -m pip install -r requirements-report.txt
python scripts/generate_pdf_report.py
```

The generator reads `bond_relative_value_assignment.ipynb`, uses the WRDS files from `data/` when present and otherwise uses the committed root copies, writes temporary charts under `tmp/pdfs/`, and replaces `output/pdf/MTH9897_Bond_Relative_Value_Report.pdf` only after successfully producing and validating all 10 pages.
