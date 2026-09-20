# MTH9897 Bond Relative Value Assignment

This repository contains the executed Jupyter notebook for the WRDS corporate bond relative-value homework. The analysis applies the issuer-curve, weighted-calibration, DV01-hedging, accrued-interest, liquidity, and trading-cost ideas Professor Boroditsky discussed in class.

## Files

- `bond_relative_value_assignment.ipynb`: executed notebook with an auditable cleaning funnel, reliability-weighted spread curves, rich/cheap diagnostics, three DV01-neutral portfolio passes, dollar PnL, turnover, and transaction-cost sensitivity.
- `output/pdf/MTH9897_Bond_Relative_Value_Report.pdf`: standalone 10-page academic report that explains what changed in each portfolio pass, why return improved, and which robustness checks qualify the result.

## Headline Result

The notebook evaluates three successive portfolio passes across AAPL, AMZN, BA, CAT, DIS, and T from August 2022 through March 2025. Gross annualized returns are 2.75% for the baseline top-three portfolio, 4.48% after concentrating on the two strongest signals, and 5.99% after adding liquidity to the ranking. The selected liquidity-aware portfolio earns 3.60% annualized after an illustrative 25 bp one-way turnover charge, but nearly all of the improvement disappears when AAPL is excluded.

## Data

The source WRDS CSV files are committed at the repository root. To rerun the notebook, place copies in the local `data/` folder:

- `WRDS_Data-Systematic_Trading-Fall2026-1.csv`
- `WRDS_Data-Systematic_Trading-Fall2026-2.csv`

The class PDF is not committed. The notebook cites the relevant slides without redistributing the source material.
