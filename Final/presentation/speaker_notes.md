# Speaker notes

## 1. Does the Conservative Formula still work?

This presentation accompanies the first draft of Project 8 for MTH 9897. It asks whether the Conservative Formula still works. The implementation and displayed numerical outputs currently use seeded synthetic data. State this clearly before discussing any chart. Real CRSP analysis remains the next stage. Suggested talk length: 12 to 15 minutes, plus questions.
Sources: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152
Project: https://github.com/yingnichang/MTH9897/tree/main/Final

## 2. Research question

The core question is whether combining the signals improves the risk-return tradeoff relative to simple controls. These are hypotheses, not findings. The code can already perform the comparisons. This presentation makes no claim about real investment performance. A favorable demo result would not validate the strategy, and an unfavorable one would not refute the paper.
Sources: notebook Sections 1 and 12. https://github.com/yingnichang/MTH9897/tree/main/Final

## 3. The portfolio selection rule

The paper's full-data recipe starts with the largest 1,000 stocks at each quarter end. Keep the lower-volatility half, rank within that pool on momentum and net payout yield, and equal-weight the best 100. In the notebook, the 1,000-stock cap precedes the complete-case screen. If history is missing, the low-volatility pool may have fewer than 500 names. Formation audits report the actual counts. Do not imply every historical period has all 1,000 eligible stocks.
Sources: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152
https://www.robeco.com/docm/docu-202302-guide-to-conservative-investing.pdf
Notebook Sections 2 and 5.

## 4. Signal definitions in the draft

Volatility is annualized monthly sample standard deviation over 36 consecutive months. Momentum compounds 11 monthly price returns and skips the formation month. The payout measure uses the trailing twelve-month cash dividend yield plus one minus current adjusted shares divided by their trailing twenty-four-month mean. A falling share count increases this proxy. Dividends, prices, and shares require consistent split adjustments. The proxy needs reconciliation with the instructor or paper implementation before calling the study an exact replication.
Sources: notebook Sections 2 and 4. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152

## 5. Information timing

Use December as an example. Volatility includes returns through December, while momentum excludes December and compounds January through November. The portfolio first earns the following January return. The code carries monthly weight drift during the holding quarter. Month-end execution is idealized. A deployable strategy would use a subsequent tradable price and may need further lags for delayed fields. Avoid saying that timing eliminates every possible source of look-ahead bias.
Source: notebook Sections 2, 4 and 6.

## 6. Historical study and demonstration data

The course asks for CRSP performance beginning in 1929. Three years of earlier return history are needed for the first formation. The delivered draft instead uses 1,100 artificial securities from 2000 through 2025, with the first investment month in January 2003. There are no real delistings in the synthetic panel. The notebook tests terminal settlement separately using a hand-computed example. Do not confuse the scenario dates with observed market crises. The existing workspace bond files cannot support this equity study.
Sources: course brief pages 1 and 5. Notebook Sections 2 and 3. https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_%26_Indexes_Databases_Summary_of_CIZ_Differences_to_Legacy_Files.pdf

## 7. Portfolio accounting

Between quarterly rebalances, stock weights drift with total returns. The next rebalance compares target weights with the drifted holdings. Traded stock notional sums buys and sells, including the initial purchase. The engine subtracts a proportional cost haircut before the next monthly return. A full replacement has two units of traded notional. Terminal proceeds earn the audited final return and then move to cash. Unknown held-stock returns raise an exception. This is a research cost approximation and excludes taxes and nonlinear impact.
Source: notebook Sections 6 and 7.

## 8. Experiments

The full formula is the baseline. Dropping one signal at a time estimates its incremental contribution within this particular design. The signal strategies share a common complete-case sample and portfolio size. Separate universe benchmarks distinguish stock selection from equal weighting. The paper sample through 2016, the 2017–2018 transition, and the period from 2019 onward are fixed comparisons. A historical post-publication period is not an untouched prospective holdout for a researcher working in 2026.
Source: notebook Sections 5 and 9–11.

## 9. Demonstration wealth paths

Every line on this slide comes from artificial data. We start at one dollar in December 2002 and show year-end wealth from compounded monthly returns through December 2025. The strategies pay ten basis points per dollar traded. The synthetic market benchmark is gross of implementation costs. Annual sampling reduces clutter and is not an annual rebalancing assumption. These curves show how the reporting works and cannot establish an investment premium.
Source: slide_data.json, annual_wealth, generated from synthetic_demo_monthly_returns.csv. Seed 9897.

## 10. Demonstration performance measures

These are descriptive results over 276 synthetic investment months. CAGR compounds monthly returns. Annualized volatility scales monthly standard deviation by square root of twelve. Sharpe subtracts the supplied monthly risk-free return, which is 0.15 percent each month in the demo. Maximum drawdown includes initial wealth. Even if a row looks favorable, it is not a finding about CRSP stocks. All strategy figures include ten basis points per dollar traded, while the market row does not pay an execution charge.
Source: slide_data.json, performance, from synthetic_demo_performance.csv.

## 11. Synthetic signal comparisons

This slide illustrates the proposed ablation test. The chart shows annualized Sharpe ratios for the full combination and versions that remove one component. The simulated differences are small and do not prove any signal adds or subtracts value in real markets. In the empirical study, discuss uncertainty, drawdowns, turnover, and changes in exposures alongside Sharpe. These comparisons should use pre-specified rules rather than searching for the best-looking variation.
Source: slide_data.json, performance. All values refer to 2003–2025 synthetic returns with 10 bps trading costs.

## 12. Synthetic trading-cost sensitivity

The portfolio positions stay fixed across all four scenarios. Costs increase from zero to fifty basis points per dollar bought or sold. The downward change in compounded return demonstrates the cost accounting, not a measured historical cost curve. In real data, estimate turnover and consider spreads and market impact by period and trade size. The simulator currently uses a proportional cost haircut and omits taxes and nonlinear execution effects.
Source: slide_data.json, costs, from synthetic_demo_cost_sensitivity.csv.

## 13. Empirical conclusions remain open

The project now has a transparent implementation and pre-specified extensions. It does not yet answer whether the strategy works. The next stage is to assemble audited CRSP history, reconcile the payout definition, and repeat the experiments. After that, add factor attribution and robust uncertainty estimates. Sector constraints are an optional extension after the baseline. A final presentation should replace the synthetic results with empirical outputs and revise the conclusion accordingly.
Source: notebook Sections 12 and 13.

## 14. References and project files

Primary paper: Pim van Vliet and David Blitz, March 2018 working paper, The Conservative Formula: Quantitative Investing Made Easy, SSRN 3145152. The published Journal of Portfolio Management version lists David Blitz and Pim van Vliet, volume 44, issue 7. Supporting overview: Robeco, The Introductory Guide to Conservative Investing, 2023. Data conventions: CRSP Summary of CIZ Differences to Legacy Files. Course source: MTH 9897 Final Projects 2026, pages 1 and 5.
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152
https://www.robeco.com/docm/docu-202302-guide-to-conservative-investing.pdf
https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_%26_Indexes_Databases_Summary_of_CIZ_Differences_to_Legacy_Files.pdf
https://github.com/yingnichang/MTH9897/tree/main/Final
