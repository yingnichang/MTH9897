# Final project review against the reference paper

Reviewed: October 3, 2026.

Sources:
- Pim van Vliet and David Blitz, *The Conservative Formula: Quantitative Investing made Easy*, March 2018. Reviewed the user-supplied 21-page PDF; [SSRN paper record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152). All page references below are PDF page positions (1–21).
- [MTH 9897 Final Projects 2026](https://drive.google.com/file/d/1ld6X7TFv-JyIGyPzIweB4BcfW95ztIYS/view), general submission requirements and Project 8.
- [Reviewed GitHub draft](https://github.com/yingnichang/MTH9897/tree/86ca091/Final), notebook, generator, README and presentation notes at commit 86ca091. Notebook blob: c474bfb1f8ea9f0d5e7ddc0f23912afb6b38705a.

Status: this document records findings and recommended revisions. The strategy implementation and saved research results have not been revised as part of this documentation update.

## Assessment

The draft uses the paper's three signals and implements much of its conservative portfolio construction. However, it remains a synthetic demonstration. Its experiments emphasize signal-removal comparisons and recent-period extensions, while several central comparisons from the paper are absent.

The final project should first implement and evaluate the paper's US strategy with historical CRSP data. An original-period replication for January 1929–December 2016 will make the comparison interpretable. Later-period results and the draft's additional experiments can follow as clearly identified extensions. The course explicitly requires CRSP since 1929, data handling, and a runnable notebook with its inputs; it does not explicitly require every international or factor-model test in the paper.

## Corrections to the earlier review

1. **The share-count payout construction has direct support in the paper.** Page 4 describes dividend yield combined with the latest shares outstanding relative to a 24-month average. The draft's share-count approach is therefore not an arbitrary substitute for the paper's method. The paper emphasizes that accounting data are unnecessary (pp. 3 and 10). A Compustat cash-buyback implementation is not required for this baseline. The remaining work is to validate the dividend window, adjustment basis, data fields, and corporate-action treatment.

2. **Return-history eligibility belongs before the top-1,000 cutoff.** Page 4 excludes stocks without at least 36 months of returns from eligibility for its top-1,000 universes. My previous favorable assessment of taking the largest 1,000 before checking all signals was too broad. For return-history eligibility, selecting the next-largest eligible stock is appropriate.

3. **Cross-sector ranking is the original baseline.** Page 4 explicitly compares factor scores across sectors. Sector exposure analysis is useful given the instructor's concern, but sector-neutral selection or sector caps should be labeled as extensions.

## Methodology alignment

| Topic | Paper | Current draft | Recommended treatment |
|---|---|---|---|
| Data and period | US CRSP; original results for 1929–2016, using earlier return history | Synthetic panel for 2000–2025; investment returns from 2003 | Acquire and normalize CRSP; first report the original period, then later years |
| Universe eligibility | At least 36 months of return history before inclusion in top-1,000 universes (p. 4) | Market-cap cutoff precedes removal of missing volatility | Apply history eligibility first, then rank eligible stocks by market cap |
| Volatility partition | Lower-volatility 500 out of 1,000, before momentum/NPY selection (p. 4) | Drops missing volatility, momentum and NPY jointly, then takes half of survivors | Establish the volatility partition before handling missing ranking signals; disclose remaining missing-data policy |
| Momentum | 12–1 month price momentum (p. 4) | Eleven compounded price-return months, skipping formation month | Consistent with the stated convention |
| Net payout | Dividend yield and shares relative to their 24-month average (p. 4) | Trailing-12-month dividend yield plus 1 minus shares/24-month mean | Share-count idea is supported; dividend window and averaging endpoints remain documented implementation assumptions |
| Selection | Average favorable momentum and NPY ranks; select 100 | Implements this when the data are complete | Retain after correcting universe and partition order |
| Weights and schedule | Equal weights; quarterly rebalancing (p. 4) | Equal weights; quarterly targets and monthly drift | Broadly aligned; document execution and dividend-reinvestment conventions |
| Speculative counterpart | Highest-volatility half; 100 worst combined momentum/NPY scores (p. 4) | Absent | Add for the paper's main comparisons |
| Baseline costs | Figures 3–4 and Table 1 are gross of implementation costs and taxes | Main constructed-portfolio results deduct 10 bps per dollar traded | Report gross original-period replication and separate net results |
| Cost scenarios | US 10 and 30 bps per dollar traded; single-counted quarterly turnover (Table 4) | 0, 10, 25 and 50 bps; annualized turnover | Add 30 bps and quarterly turnover; keep other scenarios as extensions |
| Sectors | Rank across sectors (p. 4) | No sector constraint | Consistent baseline; report sector exposures separately |

The two universe issues have different effects. A large recent IPO can occupy a top-1,000 slot before being discarded, excluding the next-largest seasoned stock. Separately, if 100 high-volatility stocks lack payout observations, taking half of the remaining 900 produces a 450-stock low-volatility pool rather than the paper's 500-stock partition.

Relevant source: [choose_weights](https://github.com/yingnichang/MTH9897/blob/86ca091/Final/build_notebook.py#L330-L355).

The paper does not fully specify every implementation detail: missing payout observations, insufficient historical universe size, tie-breaking, share-class aggregation, execution prices, and terminal-event accounting all need explicit conventions. Its free-float market-cap and 500% return-cap discussion appears in the international-data paragraph; do not automatically impose those details on US CRSP without confirming their intended scope.

## Paper content to bring into the final notebook

### 1. Research motivation and a precise replication question

Explain the paper's practical aim: obtain exposure to multiple established equity factors using a liquid, long-only portfolio, a small number of market-based inputs, and quarterly trading (pp. 2–3).

A suitable main question is: “Can we reproduce the Conservative Formula's US performance over 1929–2016 using CRSP, and how do documented data and implementation choices affect the result?”

The existing “Does it still work?” question fits the later-period extension once the historical baseline is established.

### 2. Conservative, Speculative, and Market comparisons

Add the speculative portfolio defined on p. 4. It is a long-only portfolio of stocks with the opposite characteristics; the analytical long-short spread is a separate return series.

Reproduce the central comparisons:
- Figure 3 (p. 15): growth of $100 for Conservative, Speculative, and the CRSP value-weighted total-return market.
- Figure 4 (p. 15): returns by decade for those same portfolios. State exact period boundaries and identify partial decades.
- Keep drawdown plots as an additional diagnostic.

The current wealth chart substitutes other controls for the speculative portfolio. Its through-2016/2017–2018/2019+ comparison does not reproduce the decade analysis.

Relevant draft sections: [wealth chart](https://github.com/yingnichang/MTH9897/blob/86ca091/Final/build_notebook.py#L533-L545) and [period analysis](https://github.com/yingnichang/MTH9897/blob/86ca091/Final/build_notebook.py#L573-L598).

### 3. Standalone signal comparisons from Table 1

The paper compares its combined formula with independently selected, equally weighted, quarterly rebalanced single-factor portfolios.

Add standalone low-volatility, momentum, and NPY portfolios using a documented common eligible universe. The draft already has a low-volatility-only comparator. Its “No momentum” portfolio still uses low volatility plus payouts; “No payout” still uses low volatility plus momentum. Those are useful two-signal experiments, but they are not standalone NPY and momentum portfolios.

Include arithmetic annualized return, compounded annual return, volatility, and a precisely defined Sharpe ratio. A further Table 1 comparison scales portfolios to the formula's risk using the risk-free asset. That is a retrospective equal-risk comparison, not a new rolling volatility-targeting strategy.

Small and book-to-market value portfolios extend the Table 1 reproduction, but the latter introduces accounting data beyond the core conservative strategy. They need not delay the core US replication.

Relevant draft: [signal comparisons](https://github.com/yingnichang/MTH9897/blob/86ca091/Final/build_notebook.py#L549-L569).

### 4. Factor attribution using the correct portfolio

Table 2 (p. 19) regresses the Conservative-minus-Speculative (CMS) spread on factor returns. A long-only Conservative excess-return regression addresses a different question.

For a manageable replication, start with CAPM, Fama–French three factors, and Carhart's additional momentum factor. A five-factor-plus-momentum comparison uses the shorter available sample beginning in July 1963. Report the actual regression sample, annualization method and inference convention.

The paper's 13.9% full-sample CAPM alpha is for CMS. Its 6.2% long-only CAPM alpha in Figure 6 is a different quantity. Do not compare those directly. For CMS, use R_Conservative − R_Speculative; do not subtract the risk-free rate again.

These regressions substantially strengthen a paper-based project, but the course brief does not explicitly require reproducing every model.

### 5. Turnover and trading costs

Table 4 (p. 21) reports US quarterly single-counted turnover of 32%, with 10/30 bps per dollar traded. The annual cost arithmetic is approximately:

Annual cost = quarterly one-way turnover × 2 × 4 × cost per dollar traded.

Thus 32% × 2 × 4 × 10 bps is approximately 0.26% annually; 30 bps gives approximately 0.77%. The draft's use of full buy-plus-sell stock notional is compatible with this accounting convention. State whether averages include the initial investment and how cash from exits is handled.

Keep the draft's more severe cost cases as additional sensitivity tests.

## Published numbers to compare, not assumed project findings

The following are the authors' reported results, not results established by this draft.

| Source and sample | Published result |
|---|---|
| Table 1, 1929–2016 | Conservative CAGR 15.1%; annual volatility 16.5% |
| Table 1, 1929–2016 | CRSP market CAGR 9.3%; annual volatility 18.7% |
| Table 2A, 1929–2016 | CMS CAPM alpha 13.9%; t-statistic 7.07 |
| Table 2A, 1929–2016 | CMS four-factor alpha 8.8%; t-statistic 7.00 |
| Table 2B, 1963–2016 | CMS six-factor alpha 3.3%; t-statistic 2.95 |
| Table 2D, 1963–2016 | CMS AQR model including momentum: alpha 1.0%; t-statistic 0.97 |
| Table 4, US | Gross return 15.24%; quarterly turnover 32%; high-cost net return 14.47% |

Two source discrepancies deserve explicit notes:
- Table 1 says Sharpe subtracts the 30-day Treasury bill return, but its printed values numerically match the printed simple returns divided by volatility (15.5/16.5 ≈ 0.94; 10.6/18.7 ≈ 0.57). Reconcile this definition before treating the printed Sharpe row as an exact target. Retain a clearly stated excess-return Sharpe calculation.
- Table 4's US gross return is 15.24%, while Table 1's compounded return is 15.1%. Preserve each table's label and value rather than silently treating them as identical.

Differences from a modern replication may reflect database revisions, sample coverage, or implementation choices. Investigate and report those differences; numerical agreement should follow from the method and data.

## Suggested final notebook order

1. Paper motivation, findings, and replication scope.
2. CRSP extraction, field mapping, and historical data audit.
3. Exact baseline rules and a table of documented departures.
4. Gross 1929–2016 Conservative, Speculative, and Market results.
5. Decade analysis and standalone low-volatility/momentum/NPY comparisons.
6. CMS factor attribution and 10/30 bps transaction-cost comparisons.
7. Extensions: later years, signal removal, sector exposure/constraints, and additional cost scenarios.
8. Discussion of replication differences, limitations, and reproducibility.

International markets, US midcaps, every Fama–French sorted portfolio, all macroeconomic regimes, all q/AQR models, and the compounding appendix are broader replication options. They are not all explicit course requirements.

## Remaining implementation checks

The preceding review's two real-data issues remain relevant:
- Require benchmark coverage of the full intended investment calendar and a valid first formation target; the current benchmark-driven calendar can silently shorten the backtest.
- Move timing and gap unit checks onto controlled fixtures. The current tests assume the first real security has at least 60 observations.

The preceding review successfully executed all 11 notebook code cells in demo mode with compatible dependencies. That establishes demo executability only. No CRSP empirical results were produced or verified in this review.
