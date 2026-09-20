# MTH9897 Bond Relative Value Assignment

This repository contains the executed Jupyter notebook for the WRDS corporate bond relative-value homework. The analysis applies the issuer-curve, weighted-calibration, DV01-hedging, accrued-interest, liquidity, and trading-cost ideas Professor Boroditsky discussed in class.

## Files

- `bond_relative_value_assignment.ipynb`: executed notebook with an auditable cleaning funnel, reliability-weighted spread curves, rich/cheap diagnostics, DV01-neutral portfolio construction, dollar PnL, turnover, and transaction-cost sensitivity.
- `output/pdf/MTH9897_Bond_Relative_Value_Report.pdf`: standalone 10-page academic report with an executive summary, methodology, three portfolio tests, performance and cost analysis, robustness checks, outlier review, and conclusions.

## Headline Result

The notebook compares three portfolio constructions across AAPL, AMZN, BA, CAT, DIS, and T from August 2022 through March 2025. Gross annualized returns are 2.75% for the baseline top-three portfolio, 4.48% for the concentrated top-two version, and 5.99% for the liquidity-aware top-three version. The selected liquidity-aware portfolio earns 3.60% annualized after an illustrative 25 bp one-way turnover charge, but nearly all of the improvement disappears when AAPL is excluded.

## Data

The source WRDS CSV files are committed at the repository root. To rerun the notebook, place copies in the local `data/` folder:

- `WRDS_Data-Systematic_Trading-Fall2026-1.csv`
- `WRDS_Data-Systematic_Trading-Fall2026-2.csv`

The class PDF is not committed. The notebook cites the relevant slides without redistributing the source material.
