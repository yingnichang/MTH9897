# MTH9897 Bond Relative Value Assignment

This repository contains the executed Jupyter notebook for the WRDS corporate bond relative-value homework. The methodology is aligned with the MTH9897 Lectures 1-2 treatment of issuer curves, weighted calibration, DV01 hedging, accruals, liquidity, and implementation costs.

## Files

- `bond_relative_value_assignment.ipynb`: executed notebook with an auditable cleaning funnel, reliability-weighted spread curves, rich/cheap diagnostics, DV01-neutral portfolio construction, dollar PnL, turnover, and transaction-cost sensitivity.

## Headline Result

Across AAPL, AMZN, BA, CAT, DIS, and T from August 2022 through March 2025, the equal-weighted strategy earns a 2.75% gross annualized return with 4.47% annualized volatility. At an illustrative 25 bp one-way trading cost, annualized return falls to 0.45%, reinforcing the importance of liquidity and execution costs in corporate-bond relative value.

## Data

The WRDS CSV files are not committed. To rerun the notebook, place the two downloaded CSV files in a local `data/` folder:

- `WRDS_Data-Systematic_Trading-Fall2026-1.csv`
- `WRDS_Data-Systematic_Trading-Fall2026-2.csv`

The lecture PDF is also not committed. The notebook includes concise citations to the relevant lecture sections without redistributing the source material.
