
## Requirements — Main

The body of the submission should be in Jupyter Notebook file format. You may have separate *.py files to reference in the notebook. Please submit both code and the data and make the final project runnable from start to finish. If calculation takes a long time you can pre-cache intermediary steps on the disk. 

You can choose Quantopian \ Zipline (Python), QuantConnect \ Lean (Python or C#), Backtrader (Python) trading platforms or implement the strategy yourself without an engine. You can choose either a web-based engine (using data provided by a platform) or implement a local backtest using open-source backtesting engines and data from WRDS. In the class I will show you both approaches. Last year 90% of the students implemented the strategy themselves but at that point we did not have a comprehensive demo on how to run the strategy locally with an engine. Please also note that Quantopian website was closed in October 2020, but open source zipline is available.

If you decide to use a web-based engine, at the first step just find the closest example online that works with the same data type as you intend to use. For example, if you intend to use fundamental data from 1998 to now, trade monthly 50 stocks out of 1000 in the universe, take this example and modify it accordingly. https://www.quantconnect.com/tutorials/strategy-library/momentum-effect-in-stocks

This would allow you to assess at an early stage with minimum time spent whether the study you are trying to conduct is doable in QC.

You may choose not to write the strategy on the platform and just go with Python Jupyter. Moreover, some research papers cover some systematic trading aspects but does not necessarily involve trading per se, in such a case, using just Jupyter Notebook is more appropriate (example: https://arxiv.org/pdf/1409.7720.pdf). If, for example, you use monthly data and can handle survivorship bias correctly, manipulating the data in just Jyputer Notebook \ pandas + numpy (without a platform) may be an easier and better choice.

You will have access to WRDS data source (Wharton Research Data Services), which contains a lot of great industry and research-standard databases (CRSP, Compustat, OptionMetrics etc.). Try to play with this data and incorporate it to the research while you have such an excellent opportunity. If you decide to go with more complex WRDS data and spend some time on cleaning and understanding the data (for example Fixed Income or Options data), the instructors will factor it in and add a credit for data handling. Focusing more on data and less on strategy enhancements is a totally valid case.


## Requirements — Factor Diagnostics

1. **Define a signal (for example 6 month return from 7 to 2 months ago)**
2. **Define a universe (for example S&P500, Russell 1000, Nikkei 225 etc.)**
   - A. If you measure index return from T₁ to T₂ (typically you will work with closing prices), take index weights as of one day before T₁
   - B. To evaluate forward performance of a signal from T₁ to T₂, include all stocks in your universe as of one day before T₁
3. **Calculate raw signal exposures for your universe. Neutralize signal within industries (U.S.) or sectors (all other counties) by grouping exposures, subtracting group means, and dividing by stdev (typically of the whole universe, sometime by stdev of a group, if they are drastically different from each other). Winsorize exposures from -3 to 3.**
4. **Define your rebalance strategy (daily/weekly/monthly). Backtest should be at least 5 years, 10 or more is better.**
5. **Calculate IC: rank correlation of your exposures to forward total industry-adjusted returns ("total" means adjusted for corporate actions: dividends, splits, etc. "Industry-adjusted" means your subtract equal weighed industry return)**
6. **Report average IC, moving-average IC, variance(IC), IC/stdev(IC), IC decay (e.g.) rank correlations of the exposures to the returns and to forward exposures over multiple forward periods. If satisfied with the result, move forward.**
7. **Further factor diagnostics: decile (A-C) and factor-mimicking portfolios (D-F)**
   - A. For each period form 10 decile sub-portfolios. For each decile calculate total industry-adjusted forward equal weighted returns for multiple periods – days/weeks/months – a.k.a. excess return (ER). Compute hit ratio (HR) – % of stocks outperforming industry.
   - B. Average across time for each forward period (e.g. 1,2,3,…N months). Report average ER, HR and t-stat: ER/stdev(ER).
   - C. Split your entire testing period into 2 or more sub-periods and report ER/HR/t-stats for each. Are they different?

   *Factor mimicking portfolios are most useful for multivariate case to evaluate the contribution of a new factor & also remove risk factors*

   - D. Compute factor-mimicking portfolios. When computing WLS, either use total industry-adjusted returns or (better) include industry dummies as factors. For true multivariate regression, include other risk factors (Fama-French, you can get exposures from their website)
   - E. Assume your paper portfolio is a linear combination of your lagged factor-mimicking portfolios (how many – depends on the desired turnover of your strategy and/or optimal holding period from item 6 and 7B. Try a few. Lagged portfolios can be equal weighted or exponentially decayed.
   - F. Compute cumulative excess return (over the benchmark index) of your paper portfolio, as well as information ratio, turnover, maximum drawdowns, skewness, kurtosis, and correlation of paper returns to benchmark returns.

## Requirements — Portfolio Construction & Trading

1. **Based on 1-7 decide on portfolio construction rules**
   - A. Simple: invest 1/n of AUM in buying top & selling bottom decile. Continue buying/selling for n periods (n can be 1, it regulates turnover)
   - B. At n+1 period sell/buy the portfolio you bought in the 1st period and buy/sell current top/bottom decides. Continue doing this
   - C. Keep track of all trades. Fill your paper trades at close prices less some T-cost penalty. Try varying costs: 5bps, 10bps, etc.
2. **Do linear optimization. Maximize alpha while keeping maximum industry or sector exposures constrained. As a bonus, add T-Cost (as a linear function of size. Coefficient can be higher as stock capitalization goes down and/or stock volatility goes up). Will be happy to assist with providing more details on the T-Cost. For each optimization allocate some turnover (cumulative difference between current and optimized weights)**
3. **Actually do quadratic mean-variance optimization. Let me know if you have access to any Barra or Axioma models. I'll be happy to assist you and you get extra points for doing it.**
4. **If you did simple portfolio construction (as in item 1), report cumulative portfolio performance (ER/IR/hit ratios, max drawdown, skewness, kurtosis of returns <u>as a function of n and T-costs</u>. If you did steps 2 or3, report the same stats as a function of turnover, level of T-Cost and sector constraints. Try to evaluate portfolio capacity.**
5. **Calculate correlation of portfolio returns to market. It shouldn't be high… Does outperformance come from the long or short side of portfolio? If short side, you may need to add borrow costs (2-25 bps range per month of holding the position, make it higher as stock capitalization goes lower)**
6. **Bonus: you can regress portfolio returns on industry (sector) returns and check how much of the performance can be attributed to industry (sector) returns and how much to stock selection.**


## Peper chosen — The Conservative Formula: Quantitative Investing Made Easy (Equity)

https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3145152

The paper is very interesting and the implementation requires only price historical data. For the US data, the authors utilize CRSP data going back to 1926.

Is it possible to build a simple systematic approach that beats investing in complex factor models? The research team here has proposed that a simple formula based on low return volatility, high net payout yield (dividends +/- stock buybacks), and strong price momentum gives investors exposure to the most important factor premiums in one easy-to-implement investment strategy.

The process to narrow down the largest 1000 stocks to 100 went as follows:

- First, they sorted the 1000 stocks into two groups based on their historical 36-month stock return volatility, which yields a high volatility group and a low volatility group.
- Then each stock in the low volatility group is ranked on its 12-1 month price momentum and total net payout yield.
- The momentum and net payout ranks (1-500) are simply averaged and the 100 best stocks in the final portfolio are equally weighted.

Please implement the strategy using CRSP data since 1929 as in the paper (data is available on WRDS). Some time should be devoted to studying and managing the data and it will be factored in grading. You will benefit by learning the data and will be able to run longer backtest simulation for different papers for yourself after the class (for example, you should be able to quickly change the logic to study momentum effect in the US Equities as per "Demystifying Time-Series Momentum Strategies: Volatility Estimators, Trading Rules and Pairwise Correlations" which utilized CRSP data since 1927).

Someone implemented this strategy last year, but the result was quite noisy. It was either because they did not account for the sector positioning described in Enhanced Momentum Strategies project above or because they did not correctly account for net payout dividends (=dividends to shareholders + indirect effect from stock repurchases).
