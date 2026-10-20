# Short Speaking Notes for the Conservative Formula

**Authors:** Yingni Chang and Yikai Shen

Brief script for all 22 slides: approximately 941 words, or 7.2 minutes at 130 words per minute. Allow about 7-9 minutes with pauses, plus questions. Optional split: Yingni, slides 1-9; Yikai, slides 10-22.

## 1. Replicating the Conservative Formula

Hello everyone. We're Yingni Chang and Yikai Shen. Our project tests a simple stock strategy that combines low volatility, momentum and shareholder payout. We reproduce the paper's historical results and examine how the strategy performs in more recent data.

## 2. What we test

Follow the three boxes from left to right. Can we reproduce the paper? How much of the return comes from familiar market factors? And does the strategy still perform well after trading costs? These comparisons help us judge both the historical result and its recent relevance.

## 3. The data

We use monthly CRSP stock data through 2024, together with delistings, dividends and factor returns. Earlier observations provide the history needed to begin investing in 1929. The three boxes highlight our cleaning choices: retain delisted stocks and terminal returns, keep one common share class per company, and respect the smaller early universe rather than assume one thousand eligible stocks were always available.

## 4. The portfolio rule

Conservative uses the lower-volatility half and favors stronger momentum and higher net payout. Speculative uses the higher-volatility half and weaker scores. Both select one hundred stocks, invest equally and rebalance quarterly. Each is long-only on its own; CMS buys Conservative and shorts Speculative. The formulas use thirty-six monthly returns for volatility and eleven price returns for momentum, skipping the latest month. Early data have a smaller eligible universe.

## 5. Building the signals

Volatility uses thirty-six months of total returns. Momentum uses eleven months of price returns, skipping the latest month. Net payout is dividend yield plus one minus current adjusted shares divided by their twenty-four-month average. Repurchases raise this proxy; issuance lowers it. Split adjustments prevent artificial changes.

## 6. Our results versus the paper

Our paper-period annual return is 14.80 percent, compared with 15.1 percent in the paper. Volatility is also close. The main gap is quarterly turnover: 38.9 percent versus 32 percent. We reproduce the broad pattern, but not every result.

## 7. Factor-adjusted returns

A high return does not automatically mean high alpha. Carhart alpha is the average return remaining after accounting for market, size, value and momentum exposures. Adding profitability and investment factors weakens the long-only alpha estimate, showing that the model matters.

## 8. How costs change the result

Trading costs reduce the strategy's advantage. For 1990 to 2024, about 36 basis points per dollar traded eliminates Carhart alpha; about 52 eliminates the average return above the market. These are break-even cost levels, not return percentages. We charge purchases and sales.

## 9. Results by period

The long history hides differences across periods. Earlier factor-adjusted results are stronger, while recent estimates are weaker. The 2017 to 2024 sample is only eight years, so its confidence interval is wide and does not establish positive alpha.

## 10. The recent sample: 1990–2024

For 1990 to 2024, annual Carhart alpha is 1.17 percent before costs and 0.85 percent after ten-basis-point costs; neither is significant, and the FF5 plus momentum alpha is negative even before costs. Lower volatility is the clearer benefit. Conservative-minus-Speculative compares the two portfolios; it includes a short leg and is different from holding Conservative alone.

## 11. Dividends and share repurchases

The professor warned against using dividends alone. We also include the change in adjusted shares to capture net repurchases. The dividends-only comparison performs worse over the paper period. Share changes remain a proxy, rather than directly observed buyback spending.

## 12. Industry allocation and stock selection

We separate industry allocation from stock selection using the same eligible universe as a reference. We also test an industry-quota portfolio. The original paper ranks across industries, so the quota changes the strategy and is an exploratory comparison, not the baseline rule.

## 13. Signal tests

We test whether the signals predict later returns after removing industry effects. The rank correlations are positive, but that alone does not guarantee a profitable trading strategy. Factor-mimicking portfolios help examine the exposures; their gross results do not include a complete trading-cost model.

## 14. Long/short and linear optimization

The long/short experiment suffers severe losses, including bankruptcy for some original holding-period settings. Linear optimization gives stronger results for some choices, but we test many settings and recent evidence is weaker. The best grid result still needs validation on unseen data.

## 15. Mean-variance portfolios

The mean-variance model balances expected return, risk and trading costs. It uses a regularized covariance estimate because we have many stocks and a short estimation window. Higher risk aversion lowers realized volatility, but these long-only portfolios still have substantial market exposure.

## 16. A buffer to reduce trading

The buffer keeps an existing holding while it remains eligible and within the best one hundred and fifty ranks. Recent quarterly turnover falls from 39.8 percent to 28.4 percent. It reduces trading, but the return improvement is uncertain because its confidence interval includes zero.

## 17. What we conclude

We reproduce much of the historical return and risk pattern, although turnover still differs. We address payout and industry positioning explicitly. In recent data, lower volatility is more consistent than positive net alpha. The extensions are useful experiments, but do not establish a superior strategy on unseen data.

## 18. 2017-2024 trading-cost scenarios

We test zero to thirty basis points in steps of five, with the same holdings. Lower costs improve the 2017-2024 profit, but the US strategy still trails its market over the full period, even before costs.

## 19. When the recent return gap developed

These wealth paths and rolling twelve-month comparisons show when performance improves or weakens. Rolling alpha is also in the notebook. These overlapping windows describe the sample and do not provide a forecast.

## 20. Costs that change with quoted spreads

We also let costs change with CRSP bid-ask spreads. We fix a 2016 reference and use only the previous month's spread. The result measures relative liquidity, without estimating our actual execution costs.

## 21. UK data and implementation

For the UK, we apply the same signals to Compustat Global ordinary London shares in pounds. We retain inactive companies and adjust for splits and dividends. Current classifications and incomplete terminal payments remain limitations.

## 22. UK and US after the paper period

The UK base case beats its own benchmark, but the severe exit-loss stress reverses that advantage. We also show a purchase-tax sensitivity. Different currencies and benchmarks prevent treating this as proof of a country effect.
