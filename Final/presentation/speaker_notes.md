# Speech Notes for the Conservative Formula Presentation

**Authors:** Yingni Chang and Yikai Shen

The read-aloud script contains approximately 2,029 words. At 130 words per minute, that is about 16 minutes before pauses and discussion of charts. Allow roughly 15-18 minutes with short pauses.

Presenter cues are reminders, not spoken lines. An optional split is Yingni on slides 1-9 and Yikai on slides 10-18; change this to suit your delivery.

## 1. Replicating the Conservative Formula

**Approximate speaking time:** 51 seconds, plus pauses.

**Presenter cue:** Introduce both authors and the purpose of the project.

Hello everyone. We're Yingni Chang and Yikai Shen. Our project implements the Conservative Formula proposed by David Blitz and Pim van Vliet. The idea is to combine low volatility, momentum and shareholder payout in a portfolio of one hundred stocks.

We first try to reproduce the US results over 1929 to 2016, which is the paper's sample. We then extend the backtest through 2024. The historical comparison is fairly close, but the recent results are weaker after costs and factor adjustment. I'll explain the rule first, then the data and results, including the payout and sector issues raised in the assignment.

**Transition:** Let me start with what we wanted to test.

## 2. What we test

**Approximate speaking time:** 54 seconds, plus pauses.

**Presenter cue:** Explain the distinction between replication and recent performance.

We organize the analysis around three comparisons. First, can we reproduce the paper's return, volatility and turnover? Second, how much of the return is explained by familiar equity factors? Third, what happens when we move to recent periods and include trading costs?

These questions matter because a strong result over almost ninety years does not necessarily mean that the strategy still has a useful advantage today. We use the Carhart model as our main factor adjustment and compare gross returns with returns at ten and thirty basis points per dollar traded. The fixed comparison periods were chosen before computing the post-2016 portfolio results.

**Transition:** Those comparisons depend on the data, so I'll turn to the CRSP inputs.

## 3. The data

**Approximate speaking time:** 51 seconds, plus pauses.

**Presenter cue:** Point to the coverage counts, then emphasize delistings and the early universe.

We use the full monthly CRSP files from WRDS. After cleaning, the panel has about 3.95 million security-month observations and 26,746 securities. We combine stock returns with historical company information, delistings, distributions and the market index. We also use Fama-French factors.

Two choices are especially important. We keep stocks that disappear, including their terminal returns, instead of looking only at survivors. We also use one common share class per company to avoid double counting. The earliest portfolio universe has only 393 eligible stocks. It first reaches one thousand in June 1964, so the early backtest necessarily uses a smaller universe.

**Transition:** With those files cleaned, the selection rule is fairly simple.

## 4. The portfolio rule

**Approximate speaking time:** 51 seconds, plus pauses.

**Presenter cue:** Follow the selection order on the slide.

At each quarter-end, we first require thirty-six consecutive months of return history. We then select the largest one thousand eligible stocks by market capitalization. From this group, we keep the half with the lowest historical volatility.

Within that lower-volatility pool, we rank momentum and net payout favorably, average the two ranks, and select the best one hundred stocks. Each receives an equal weight. The holdings then drift with returns for the next three months. We rebalance using information available at the previous quarter-end. Applying the history requirement before the size cut is important because reversing that order changes the universe.

**Transition:** I'll show how we calculate the three inputs to those ranks.

## 5. Building the signals

**Approximate speaking time:** 51 seconds, plus pauses.

**Presenter cue:** Explain each signal briefly; spend most of the time on payout.

Volatility is the standard deviation of thirty-six monthly total returns, expressed in annual units. Momentum compounds eleven monthly price returns and skips the most recent month. Portfolio performance, in contrast, uses total returns including distributions and delistings.

Net payout combines dividend yield with the change in adjusted shares. We use the latest share count relative to its twenty-four-month average. Repurchases increase the signal, while issuance decreases it. Both prices and shares are split-adjusted, so a stock split should not create an artificial buyback. The twelve-month dividend window is a disclosed choice because the paper does not fully specify that part.

**Transition:** Now we can compare the backtest with the published figures.

## 6. Our results versus the paper

**Approximate speaking time:** 48 seconds, plus pauses.

**Presenter cue:** Point to the return/risk comparison and the growth chart.

Over the paper's sample, our Conservative portfolio compounds at 14.80 percent a year before costs, compared with 15.10 percent in the paper. Our volatility is 17.06 percent, compared with 16.50 percent. The broad return-and-risk result is therefore close.

The main unresolved difference is quarterly turnover: we get 38.9 percent, compared with 32.0 percent. Some control and regression results differ as well. Share-class choices, capitalization and dividend estimation could contribute, but we cannot separate their effects. We leave these gaps visible rather than adjusting the strategy to force a match.

**Transition:** Close raw returns are only part of the comparison; let's look at factor-adjusted returns.

## 7. Factor-adjusted returns

**Approximate speaking time:** 52 seconds, plus pauses.

**Presenter cue:** Define alpha before discussing the factor models.

Alpha here is the return left after accounting for the factors in the regression. A high raw return can still have little alpha if the portfolio mainly holds known factor exposures.

For the Conservative long-only portfolio, annual Carhart alpha over the paper sample is 3.23 percent. When we use the five Fama-French factors plus momentum over 1963 to 2016, the estimate falls to -0.11 percent. Adding profitability and investment changes the interpretation substantially. We also compare the Conservative-minus-Speculative contrast with the paper. The post-1963 comparisons are closer than the full-sample ones, but that does not establish the cause of the remaining difference.

**Transition:** Trading costs are another reason gross return can be misleading.

## 8. How costs change the result

**Approximate speaking time:** 54 seconds, plus pauses.

**Presenter cue:** Explain basis points and the single-counted turnover convention.

We charge costs on both purchases and sales. Thirty basis points means a charge of zero point three percent per dollar traded. Quarterly turnover on the slide is single-counted, so a purchase and sale are not counted twice in that measure.

At thirty basis points, the paper-period annual compound return falls to 13.73 percent. For 1990 to 2024, the break-even cost for Carhart alpha is approximately 36 basis points. Break-even means the cost at which the estimated advantage reaches zero. In the period after 2016, gross excess return and alpha are already nonpositive. These are flat cost scenarios, not a complete model of historical liquidity or market impact.

**Transition:** Let's look at how the estimates change across periods.

## 9. Results by period

**Approximate speaking time:** 50 seconds, plus pauses.

**Presenter cue:** Trace the early-to-recent pattern; do not read every table cell.

The subperiods show why the long history needs to be broken up. The earlier Carhart estimates are stronger, while the recent estimates are weaker. The rolling plots show a similar pattern, although adjacent windows overlap and should not be treated as independent observations.

For 2017 to 2024, gross Carhart alpha is -1.21 percent. Its ninety-five-percent interval runs from -5.12 percent to 2.69 percent. That interval is wide because the sample contains only eight years. We do not find strong evidence of outperformance in that period, but an insignificant estimate is not proof that expected alpha is exactly zero.

**Transition:** We will now focus on the recent sample in more detail.

## 10. The recent sample: 1990–2024

**Approximate speaking time:** 46 seconds, plus pauses.

**Presenter cue:** Give the net-alpha estimate, interval and lower-risk result.

This is our main recent comparison. After thirty-basis-point trading costs, annual Carhart alpha is 0.20 percent. The ninety-five-percent interval is roughly -1.98 percent to 2.39 percent, so it includes zero. That makes a strong claim about recent factor-adjusted outperformance difficult to support.

The more consistent benefit is lower volatility than the market. The Conservative-minus-Speculative contrast still has a stronger result, but that includes shorting the Speculative portfolio. It is a different comparison from holding the Conservative portfolio alone, and its attribution result does not include actual borrow or financing costs.

**Transition:** Next are the two implementation checks highlighted in the assignment.

## 11. Dividends and share repurchases

**Approximate speaking time:** 55 seconds, plus pauses.

**Presenter cue:** Emphasize the assignment's payout warning and the matched comparison.

This is one of the specific issues raised in the assignment. Dividend yield alone misses the indirect payout from repurchases. For example, with a three-percent dividend yield, ninety adjusted shares today and a one-hundred-share average, the net payout signal is thirteen percent. Issuance works in the opposite direction.

In the matched backtest, the net-payout rule earns 14.80 percent gross annually, compared with 13.44 percent using dividends alone. We hold the other rules constant so that we are comparing the payout ranking. This shows that the share-count term matters. It is still a proxy for net repurchases after issuance, not directly observed buyback cash spending or a causal estimate of the effect of buybacks.

**Transition:** The other concern is industry positioning.

## 12. Industry allocation and stock selection

**Approximate speaking time:** 60 seconds, plus pauses.

**Presenter cue:** Explain the reference universe and then the industry quota rule.

For sector positioning, we use Fama-French twelve industries. We compare our portfolio with a cap-weighted reference from the same formation universe, so a broad-market universe difference does not get mistaken for industry allocation.

Over the paper sample, industry allocation contributes about 0.82 percent a year and stock selection about 3.80 percent. A separate universe-to-market term completes the monthly identity. These are arithmetic contributions, not contributions to CAGR.

We also follow the course's quota idea: if an industry contains fifteen percent of universe stocks, it receives about fifteen of the one hundred holdings. That variant earns 14.51 percent gross annually. It changes the paper's global screen and was considered after the baseline results, so we treat it as an exploratory comparison.

**Transition:** We also test the signals outside the original stock-selection rule.

## 13. Signal tests

**Approximate speaking time:** 53 seconds, plus pauses.

**Presenter cue:** Define IC and explain why rank correlation differs from a mean return spread.

We next examine the signals separately. We remove industry means, standardize the exposures and clip extremes. The information coefficient, or IC, is the rank correlation between a signal and later industry-adjusted returns.

The composite's one-month IC is about 0.047. We also look at deciles, persistence and longer holding horizons. A positive rank correlation does not always imply a strong mean spread when returns are skewed. The factor-mimicking portfolios help separate signal exposures from industry, size and historical Fama-French controls. Their gross information ratio falls as we average more old portfolios, along with turnover. They are diagnostic portfolios with leverage, rather than a fully costed trading strategy.

**Transition:** That leads to the trading and portfolio-construction experiments.

## 14. Long/short and linear optimization

**Approximate speaking time:** 59 seconds, plus pauses.

**Presenter cue:** Separate the failed trading experiment from the optimizer grid.

The long/short exercise buys the top composite decile and sells the bottom decile. We compare holding periods, trading costs and monthly borrow fees. The original buy-and-hold cohorts lose all capital in the early data for several holding periods. We then examine monthly reweighting, which still has an extremely deep drawdown. That alternative was chosen after seeing the losses.

The linear optimizer gives stronger-looking recent results for some settings. It caps individual stocks, constrains industries and limits turnover. But two of the four 95% intervals exclude zero for the four displayed recent examples, and those intervals are unadjusted for testing many settings. The post-2016 estimates are weaker. We would need an unseen test before treating the best grid result as reliable.

**Transition:** The next model adds a covariance penalty.

## 15. Mean-variance portfolios

**Approximate speaking time:** 54 seconds, plus pauses.

**Presenter cue:** Use the table to compare the two risk-aversion settings.

The quadratic model adds portfolio variance to the objective, alongside expected return and trading cost. We estimate covariance using the last thirty-six monthly returns. With about one thousand stocks and only thirty-six observations, sample covariance needs regularization, so we combine it equally with diagonal covariance.

For 1990 to 2024, risk aversion five gives net CAGR of 11.59 percent and volatility of 12.51 percent. At risk aversion twenty, those figures are 10.39 percent and 11.51 percent. More risk aversion lowers realized volatility, but market correlations remain high. These long-only portfolios are not market-neutral. We chose these settings after examining the baseline and have not established that they are optimal.

**Transition:** Finally, we test a simpler change aimed at reducing turnover.

## 16. A buffer to reduce trading

**Approximate speaking time:** 50 seconds, plus pauses.

**Presenter cue:** Point to the turnover reduction and the confidence interval.

The buffer asks whether we need to sell a holding immediately when its rank slips below one hundred. We keep it while it remains eligible and among the best one hundred and fifty ranks, then fill vacancies. We fixed that buffer size before testing the variant.

Quarterly turnover falls from 39.8 percent to 28.4 percent. The net paired difference is 0.34 percent a year, but its interval includes zero. The modification reduces trading, while also changing holdings, so we cannot attribute the whole return difference to costs. We view it as a useful trading experiment, not proof of a better signal.

**Transition:** These comparisons lead us to the main conclusion.

## 17. What we conclude

**Approximate speaking time:** 54 seconds, plus pauses.

**Presenter cue:** Pause on the main conclusion and the unresolved turnover difference.

Our implementation reproduces much of the paper's historical return and risk pattern, but it is not an exact replication. Turnover and some regression results still differ. We have also checked the two issues highlighted in the assignment: net payout includes the adjusted share-count term, and industry positioning is measured and tested separately.

For recent data, lower volatility is more consistent than positive net alpha. The buffer and optimizers change trading and risk, but their results do not yet show a stronger strategy on unseen data. Our conclusion is that this is a useful, understandable factor portfolio, with important limits to a claim of persistent outperformance.

**Transition:** We'd like to finish with a few questions about implementation and next steps.

## 18. Questions for the professor

**Approximate speaking time:** 44 seconds, plus pauses.

**Presenter cue:** Invite guidance; pause after each question and allow discussion.

We would appreciate guidance on a few implementation choices. Is our twelve-month dividend yield plus the share-count term based on a twenty-four-month average the intended payout definition? Should our main result keep the paper's global ranking or use an industry adjustment? And which turnover convention should we use when comparing our higher turnover with the paper?

You mentioned sharing the data-cleaning work. Could we compare our dividends, split adjustments and delistings with your reference? Finally, should we investigate the weaker recent extension further, or document it as a finding? Which checks would you prioritize? Thank you.

# Questions to Prepare For

**Did you reproduce the paper exactly?**

No. Return and volatility are close, but quarterly turnover is 38.9% versus 32%, and some regression/control results differ. We cannot isolate the cause without the authors' exact cleaned inputs and conventions.

**How do you account for share repurchases?**

Payout is dividend yield plus one minus latest split-adjusted shares divided by their 24-month average. Repurchases raise the signal; issuance lowers it. We check split neutrality and compare the rule with dividends alone. Share changes are a net proxy, not reported buyback cash flow.

**Why isn't the paper baseline sector-neutral?**

The paper explicitly compares scores across sectors. We preserve that rule for the replication and separately use industry-adjusted diagnostics, allocation/selection attribution and a count-proportional FF12 quota strategy.

**Does an insignificant alpha mean the strategy does not work?**

It means the estimate does not provide strong evidence of nonzero factor-adjusted return at the chosen confidence level. It does not prove expected alpha is exactly zero. The strategy can still provide lower volatility and exposure to known factors.

**Which experiments use an unseen sample?**

The main comparison periods were fixed before computing post-2016 portfolio returns. The later sector and quadratic experiments, and the monthly-reweighted long/short, were considered after results were seen. We do not claim an unseen validation sample for those variants.

**Are the capacity and cost assumptions realistic?**

They are simplified scenarios. Costs are proportional to traded dollars, sometimes scaled by size and volatility. Capacity uses monthly volume and a 10% participation assumption, normalized to 2024 market size. Market impact, daily scheduling and actual borrow availability are omitted.
