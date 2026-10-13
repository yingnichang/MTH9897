# Speaker notes

**Authors:** Yingni Chang and Yikai Shen

Presentation notes. Data and tables are from the accompanying notebook.

## 1. Replicating the Conservative Formula

We use monthly CRSP data to implement the paper's rule, then extend the backtest through 2024. The first comparison uses the paper's own sample. The later analysis asks whether the return survives factor adjustment and trading costs.

## 2. What we test

We compare the published return and risk first. Then we examine known factors, changes across periods and trading costs. These comparisons were fixed before computing the post-2016 portfolio returns. The additional variants are separate experiments.

## 3. The data

The data work matters here. We retain delisted stocks, use historical company and exchange information, and separate missing signal inputs from returns on already-held positions. The early universe is much smaller than 1,000 names.

## 4. The portfolio rule

We require 36 months of return history before the size cut. After that, we use the low-volatility half and combine momentum and payout ranks. The largest share class represents each company. We document the choices that the paper leaves open.

## 5. Building the signals

Momentum uses price returns and excludes the latest month. Portfolio returns include distributions. For payout, both prices and shares need split adjustment: a split should not appear as a repurchase. The 12-month dividend window is our disclosed convention.

## 6. Our results versus the paper

The main return and volatility figures are close. The turnover difference is larger and remains unresolved. We have not changed the rule to force agreement. Share classes, the size measure and payout estimation may affect the result, but we cannot separate their effects.

## 7. Factor-adjusted returns

The factor model changes the interpretation of the historical return. Adding profitability and investment reduces estimated alpha substantially. The post-1963 comparisons are closer than the full-sample ones; a different sample should not be mistaken for evidence of the cause of the gap.

## 8. How costs change the result

We charge both purchases and sales. Break-even is the cost per dollar traded at which market excess return or Carhart alpha reaches zero. Flat cost scenarios do not capture historical changes in liquidity or market impact.

## 9. Results by period

The earlier estimates are stronger than the recent ones. The sample after 2016 is only eight years, so its interval is wide. We do not interpret an insignificant estimate as proof that expected alpha is exactly zero.

## 10. The recent sample: 1990–2024

After costs, the recent alpha interval includes zero. The portfolio still has lower volatility than the market. The Conservative-minus-Speculative contrast remains different from the long-only portfolio's performance against the market.

## 11. Dividends and share repurchases

This is the payout issue raised in the assignment. We compare NPY with dividends alone using otherwise identical portfolio rules. The share-count term changes both selections and returns. It measures net repurchases after issuance, rather than reported buyback cash spending.

## 12. Industry allocation and stock selection

We compare with the same formation universe so that industry allocation is not confused with a broad-market universe difference. The attribution includes the selection interaction. We then apply the course's count-proportional quotas, which change the paper's global screen.

## 13. Signal tests

These tests use industry-neutral exposures and industry-adjusted returns. Rank IC and a mean decile spread can tell different stories when returns are skewed. The factor-mimicking portfolios are gross diagnostic portfolios and may have substantial leverage.

## 14. Long/short and linear optimization

The initial buy-and-hold long/short loses all capital in the early data. Monthly reweighting was considered after seeing that outcome, and still gives severe drawdowns. The linear optimizer results also need caution: the displayed intervals are unadjusted for testing several settings.

## 15. Mean-variance portfolios

With only 36 observations for about 1,000 stocks, sample covariance needs regularization. We use half sample covariance and half diagonal covariance. More risk aversion lowers realized volatility, but these long-only portfolios remain highly correlated with the market. We chose these settings after examining the baseline.

## 16. A buffer to reduce trading

We fixed the 150-rank buffer before testing it. It reduces turnover, and its net point estimate is positive, but the paired interval includes zero. Since it also changes holdings, we cannot attribute the entire difference to cost savings.

## 17. What we conclude

We reproduce much of the historical return-and-risk pattern. The remaining turnover and regression gaps prevent an exact replication claim. For recent data, lower volatility is more consistent than positive net alpha. The extra strategies need an unseen test before stronger claims would be justified.

## 18. Running the project

The notebook and both PDFs read saved aggregate results. The full calculation starts with the private CRSP inputs and runs through research.run_all. Source data, cleaning audits and run instructions are included in the private submission package.
