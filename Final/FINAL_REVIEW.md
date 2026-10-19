# Conservative Formula Calculation Checks

**Project authors:** Yingni Chang and Yikai Shen

We checked the implementation against the paper, examined the input data and accounting, and independently reconstructed the signals and portfolio returns. The checks were completed on October 12, 2026. This appendix records what we verified and what remains unresolved. The backtest covers January 1929 through December 2024; comparisons with the paper stop at December 2016.

## 1. Comparing the method with the paper

The reference is Blitz and van Vliet, *The Conservative Formula: Quantitative Investing Made Easy* (2018), supplied as [the research paper](The%20Conservative%20Formula%20Quantitative%20Investing%20Made%20Easy.pdf). Page 4 defines the construction order and the adjusted-share payout proxy. The original [assignment](Instructions.md) also requires factor diagnostics and portfolio construction exercises.

| Requirement | Implementation and review finding |
|---|---|
| Eligible universe | Common shares on NYSE, AMEX and Nasdaq; 36 consecutive monthly returns before the size cut. One common share class per company. The largest 1,000 history-eligible stocks are chosen before sorting on volatility. |
| Low volatility | Annualized standard deviation of the preceding 36 monthly total returns; the lower-volatility half of the universe is retained. |
| Momentum | Cumulative price return over 11 months, excluding the most recent month. Total returns are used for portfolio performance. |
| Net payout | Trailing dividend yield plus the share-count repurchase proxy, using split-adjusted shares and the paper's 24-month average denominator. |
| Selection and trading | Favorable momentum and payout ranks are averaged; the best 100 receive equal weights. Quarter-end information determines the next month's holdings. Weights drift between quarterly rebalances; terminal proceeds become cash. |
| Sector treatment | The paper explicitly compares scores across sectors. Its baseline remains global. Industry-neutral factor diagnostics, industry-constrained optimizers, industry attribution, and a separate sector-by-sector variant address the professor's concern. |
| Diagnostics | Industry-neutral, clipped exposures; industry-adjusted forward returns; IC mean, variance, moving estimates, decay and persistence; decile returns, stock hit ratios and subperiod comparisons. |
| Multivariate factor portfolios | Style exposures, industry dummies, size and trailing stock-level FF3 loadings enter WLS. Historical loadings are estimated at formation; future market-factor returns are not used as stock exposures. |
| Construction exercises | Long/short holding-period and cost comparisons, trade ledgers, borrow costs, linear optimization, quadratic mean-variance optimization, capacity estimates and risk statistics are included. |
| Deliverables | An executed Jupyter notebook, an 18-slide PDF, speaker notes, generating code, aggregate results, and a separate private data package. |

We added the quadratic model, historical FF3 stock loadings and the sector variant after examining the baseline. Their parameters are exploratory and have not been validated on an unseen sample.

## 2. Checking the data and accounting

The full WRDS exports produce 3,954,591 security-months for 26,746 securities. The data start in December 1925 and end in December 2024. The review verifies all 18 raw, normalized and audit file hashes in `data/manifest.json`, and finds no duplicate security-months or duplicate eligible company-months. There are 3,747,988 eligible observations.

Split adjustment uses `abs(PRC) / CFACPR` for prices and `SHROUT * CFACSHR` for shares. Splits therefore change neither the economic price history nor the adjusted share count. Missing historical returns are kept missing for signal windows. A separate held-return convention handles stale prices, gaps and terminal events, with every case counted in the audits.

The panel includes 22,869 terminal delisting events: 20,022 observed delisting returns, 2,530 imputed returns and 317 zero conventions. The raw non-active delisting extract has one event per security, so retaining its final event does not discard an earlier terminal event in this extract. Imputation and missing-return conventions remain assumptions, particularly in early data.

### Net payout includes repurchases and issuance

At formation month `t`, the implemented signal is:

```text
dividend yield = sum of adjusted cash dividends over t−11,...,t / adjusted price at t
net repurchase proxy = 1 − adjusted shares at t / mean adjusted shares over t−23,...,t
net payout yield = dividend yield + net repurchase proxy
```

For example, a 3% dividend yield and 90 current adjusted shares versus a 100-share average give 13% net payout yield. Issuance has the opposite sign. Synthetic tests independently check repurchases, issuance and split neutrality. Direct window calculations on 1,200 actual observations reproduce volatility, momentum, dividends, issuance and net payout to within `8.0e−15`.

The dividend proxy is inferred from total minus price return and the preceding adjusted price. It is checked against CRSP distributions and reconciles approximately 96.8%–99.85% of checkable ordinary-cash observations by decade. Distribution timing, special distributions and incomplete observations remain disclosed limitations. Adjusted share changes measure net repurchases after issuance; they are not directly observed buyback cash expenditures and can reflect other corporate actions.

The dividends-only comparison holds the original universe, low-volatility pool, complete-case membership, momentum rule, portfolio size, rebalance dates and cost assumptions constant. It replaces only the payout ranking.

| Strategy, 1929–2016 | Gross annual compound return | Net annual compound return at 30 bps |
|---|---:|---:|
| Original net payout formula | 14.80% | 13.73% |
| Dividends-only counterfactual | 13.44% | 12.39% |
| Separate sector quota variant | 14.51% | 13.37% |

The net payout strategy's paired net-return difference versus dividends alone is 1.22 percentage points a year in arithmetic terms, with a Newey–West 95% interval of [0.56, 1.87]. The difference shows that omitting the share-count term materially changes this implementation; it does not prove a causal buyback effect. See `results/professor_checks/payout_comparison.csv` and `payout_components.csv`.

### Sector positioning is measured and tested

The professor's Enhanced Momentum example allocates selection slots separately within sectors, proportional to their universe counts or capitalization. The added variant uses FF12 industries, allocates 100 slots in proportion to universe stock counts with largest-remainder rounding, selects the low-volatility half within each industry, and then ranks momentum and payout within that industry. Every one of its 384 formations holds 100 stocks. Its largest industry-weight deviation from the count-proportional target is 0.7 percentage points. This changes the paper's global volatility screen and is reported separately.

The baseline's sector weights are also compared with a capitalization-weighted reference drawn from its formation universe. Constituents and industry labels are fixed each quarter, weights drift, and exits become cash. Monthly arithmetic attribution satisfies:

```text
baseline − CRSP market = industry allocation + stock selection + reference universe − CRSP market
```

The selection component includes the allocation/selection interaction. Over 1929–2016, the annual arithmetic contributions are 0.82 percentage points from industry allocation, 3.80 from stock selection and 0.18 from the reference-to-market difference, totaling 4.80. All 1,152 monthly identities reconcile within `7.9e−16`. These are arithmetic contributions, not compounded CAGR contributions or causal estimates. See `sector_attribution.csv`, `sector_exposures.csv` and `sector_monthly.csv` in `results/professor_checks/`.

## 3. Reconstructing the calculations independently

We rebuilt all 12 studies from the licensed inputs and saved 85 aggregate files. Their hashes agree with the results manifest, as do the source, dependency and cache records. The published files preserve those hashes.

| Independent verification | Coverage and outcome |
|---|---|
| Selection reconstructed separately | 384 quarterly formations and 38,400 selected names; identical to the engine. |
| Dollar holdings and cash recursion | All 1,152 gross and cost-adjusted monthly baseline returns; maximum difference `1.1e−15`. |
| Carhart regression and covariance | Independent normal equations and Newey–West lag products over 1,056 paper-period months; maximum alpha/standard-error difference `4.9e−17`. |
| Sector attribution | All 1,152 monthly allocation/selection/reference identities reconcile. |
| Quadratic optimization | Both fixed risk aversions across 384 formations each; all 768 solver runs return `Solved`. Maximum physical constraint violation `4.91e−9`; no risk-window lookahead or turnover relaxation. Five infeasible industry lower bounds per variant are explicitly relaxed and recorded. |
| Test suite | 139 tests pass. Two warnings arise from correlation of constant values in a synthetic fixture. |
| Jupyter execution | All 16 code cells execute without errors in empirical and synthetic modes. A fresh staged checkout, without licensed data, also executes all 16 empirical cells from its aggregate results. |
| Presentation | All 18 PDF pages render successfully. Contact sheets and dense tables were visually inspected; the exporter checks page boundaries, textbox heights and table wrapping. |

Two corrections affect reliability. The return-scaled linear sensitivity now converts annual volatility to a three-month horizon with `sqrt(3/12)`, rather than `sqrt(3)`. The licensed diagnostics cache now carries a verified content hash and data/source/package producer identity; altered or foreign caches are rejected. Completed studies are checkpointed atomically so a later failure cannot lose earlier provenance.

The quadratic objective subtracts portfolio variance and linear trading costs from expected return. It uses 36 months of historical total returns, 50% diagonal covariance shrinkage, 2% stock caps, industry bands of ±5 percentage points around universe capitalization weights, and a 40% two-way turnover budget after the initial allocation. The solver is [Clarabel](https://clarabel.org/stable/python/getting_started_py/). An independent dense constrained optimization test agrees with the quadratic objective. Covariance scaling assumes no serial correlation. Expected returns use only completed trailing three-month IC observations.

## Remaining differences and interpretation

The original formula earns 14.80% gross annual compound return with 17.06% volatility over 1929–2016, versus the paper's 15.1% and 16.5%. Market return is 9.15%, versus 9.3%. Quarterly turnover remains 38.9%, versus 32%; the difference is unresolved. Some Small-control statistics and full-sample Table 2 regression alphas also differ materially, while the post-1963 FF5 plus momentum comparisons are closer. The notebook reports these differences directly.

The first formation has only 393 eligible stocks; the universe first reaches 1,000 in June 1964. Using security rather than aggregate company capitalization, choosing one share class, imputing some terminal returns, and inferring dividends introduce documented conventions. The CRSP release identifier is unavailable, although extract receipts, timestamps and input hashes are retained. The data-handling conventions follow the available [CRSP methodology reference](https://www.crsp.org/wp-content/uploads/guides/CRSP_Calculations_and_Index_Methodologies.pdf).

Recent returns do not justify a claim that the formula reliably beats the market after known factors and costs. Over 1990–2024, its net-at-30-bps annual Carhart alpha is 0.20%, with a 95% interval of approximately [−1.98%, 2.39%]. Quadratic variants remain strongly correlated with the market. The original long/short buy-and-hold cohorts fail in the early sample; the monthly-reweighted alternative is labeled as a subsequent convention and still has severe drawdowns. These outcomes are retained rather than adjusted to create a favorable result. Capacity estimates use monthly volume and a normalization to December 2024 market size, without an impact model or actual borrow availability.

## Submission files

The main deliverable is [the executed notebook](conservative_formula_final.ipynb). The [PDF slides](presentation/conservative_formula.pdf), generating code, notes and aggregate results are included in Git. Run instructions are in [README.md](README.md).

`python package_submission.py` creates `output/submission/MTH9897_Conservative_Formula_Final.zip` with the notebook, PDF, source, aggregates, all seven raw parquet inputs, normalized inputs and the licensed worked examples needed for all 18 input-hash checks. The ZIP contains licensed CRSP observations and belongs in the authorized course submission channel; it is excluded from Git.

## Post-presentation follow-up, 2026-10-18

**Authors: Yingni Chang and Yikai Shen.**

The feedback adds a US cost grid from 0 to 30 bps in 5-bps steps, annual returns, trailing 12-month return gaps,
36-month Carhart alpha with HAC intervals, and lagged quoted-spread scaling. Reference spreads use only 2016;
the next month's cost uses the previous calendar month. Original US holdings and earlier return series are unchanged.

At 5 bps, 2017-2024 US CAGR is 10.83%; at 30 bps it is 9.97%, versus 13.01% for the CRSP market. The full-period
market excess and Carhart alpha are negative even before costs. Lower cost does not establish outperformance.
The time-series analysis is descriptive; overlapping rolling estimates do not provide a forecast or a formal break test.

The new WRDS Compustat Global export contains 7,906,471 daily UK-incorporation observations from 2013 through 2024.
The London ordinary GBP sample has 178,848 monthly observations across 2,008 issues before formation screens,
including inactive securities. Price uses PRCCD/QUNIT/AJEXDI, shares use CSHOC*AJEXDI and total-return index uses TRFD.
The same volatility, momentum and net-payout rule applies with quarterly formation. No US factors are used for UK alpha.

At 10 bps the UK base CAGR is 7.23%, versus 5.40% for its own-universe cap-weight comparator. A separate scenario
adds 50 bps on purchases, giving 6.34% CAGR. Under a deliberately severe 100%-loss assumption for every disappearing
issue, strategy CAGR falls to 1.65% against 3.55% for its stressed comparator: the relative advantage reverses.
This sensitivity, current country/exchange/type headers, local currencies and different comparator definitions prevent
a robust country-effect claim. Historical classifications and observed terminal payments remain priorities.

Validation includes new split/quotation-unit, gap, exit-loss and past-only spread tests. All 144 scientific and
presentation tests passed. Separately recomputing compounded returns and market excess from the monthly cash flows
reproduced all 35 country/cost/exit summary rows within 1e-14. The seven US cost scenarios are monotone and all recent
Carhart confidence intervals include zero. The executed notebook has 19 code cells, with no error outputs.
The PDF presentation has 22 pages, with aligned full and short notes. New and changed PDF pages were rendered and
visually reviewed. The private course ZIP contains the UK export and original CRSP quote export needed to rebuild
these tests. Licensed observations remain excluded from GitHub.


## Notebook-first submission

The main deliverable is now `conservative_formula_final.ipynb`. Its visible RUN_MODE setting controls cached,
analysis and full execution through `submission_runner.py`, with all report results displayed in subsequent
cells. Full mode invokes raw-data cleaning before all study scripts; analysis mode reuses normalized inputs.
Cached mode validates result and source hashes and works without private inputs. Preflight checks stop a
recompute before any stage runs if required private files are absent. Stage failures stop notebook execution.
The private ZIP includes the code, all input data and cached outputs. No email or forum message is sent by this code.
