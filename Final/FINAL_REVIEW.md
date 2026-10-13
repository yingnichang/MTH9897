# Conservative Formula Final Review

Reviewed October 12, 2026. The project implements the US Conservative Formula on CRSP from January 1929 through December 2024, with the paper comparison ending in December 2016. Three review passes cover the assignment and paper, data and accounting, and independent calculations and deliverables. The checks below pass after the corrections. The results are a close replication of return and risk, with material differences from the paper still disclosed.

## Pass 1 Paper and assignment alignment

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

The final review filled the missing quadratic optimization exercise. It also added historical FF3 stock loadings to the factor-mimicking regressions. These extensions and the new sector variant were introduced after observing the baseline; their parameters are exploratory, without an unseen holdout or a claim of optimality.

## Pass 2 Data and accounting

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

## Pass 3 Independent verification and deliverables

The full research pipeline was rebuilt from the licensed inputs after the fixes. It completed all 12 studies and produced 85 aggregate result files. Every file hash, current study source identity, dependency identity and consumed cache identity verifies. Staged Git blobs also preserve all 85 result hashes, all recorded research source hashes and the data-manifest hash.

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

The main deliverable is [the executed notebook](conservative_formula_first_draft.ipynb). The [PDF slides](presentation/conservative_formula.pdf), generating code, notes and aggregate results are included in Git. Run instructions are in [README.md](README.md).

`python package_submission.py` creates `output/submission/MTH9897_Conservative_Formula_Final.zip` with the notebook, PDF, source, aggregates, all seven raw parquet inputs, normalized inputs and the licensed worked examples needed for all 18 input-hash checks. The ZIP contains licensed CRSP observations and belongs in the authorized course submission channel; it is excluded from Git.
