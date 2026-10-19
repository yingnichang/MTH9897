"""Narrative and tables for the professor-feedback extension.

Authors: Yingni Chang and Yikai Shen. All numbers come from verified results.
"""
from research import results


def load(root=results.RESULTS):
    return {k:results.load(study,name,root)[0] for k,study,name in [
        ('cost','feedback_costs','cost_summary.csv'),('spread','feedback_costs','spread_coverage.csv'),
        ('uk','uk_comparison','summary.csv'),('coverage','uk_comparison','coverage.csv'),
        ('tax','uk_comparison','tax_sensitivity.csv')]}


def pct(x):return f'{100*float(x):.2f}%'


def cost_rows(d):
    q=d['cost'];q=q.loc[q.period.eq('2017–2024')&q.cost_model.eq('flat')]
    return [['Cost (bps)','Annual return','Above market / yr','Carhart alpha / yr','Final $100']] + [
        [f'{r.reference_bps:.0f}',pct(r.compounded),pct(r.excess_vs_market),pct(r.carhart_alpha),f'${r.terminal_wealth_100:.2f}']
        for r in q.itertuples()]


def country_rows(d):
    s=d['uk'];base=s.loc[s.hold_rule.eq('100')&s.cost_bps.eq(10)]
    rows=[['2017-2024, net 10 bps','Annual return','Own benchmark','Above market / yr']]
    for country,loss,label in [('US',None,'US, USD'),('UK',0,'UK base, GBP'),('UK',-1,'UK exit stress, GBP')]:
        q=base.loc[base.country.eq(country)]
        r=(q.loc[q.exit_loss.eq(loss)] if loss is not None else q).iloc[0]
        rows.append([label,pct(r.compounded),pct(r.market_cagr),pct(r.market_excess_annual)])
    tx=d['tax'];r=tx.loc[tx.hold_rule.eq('100')&tx.exit_loss.eq(0)&tx.cost_bps.eq(10)].iloc[0]
    uk=base.loc[base.country.eq('UK')&base.exit_loss.eq(0)].iloc[0]
    rows.append(['UK plus 50bps buy tax',pct(r.compounded),pct(uk.market_cagr),pct(r.market_excess_annual)])
    return rows


def extras(root=results.RESULTS):
    d=load(root);sp=d['spread'];cv=d['coverage'];cv=cv.loc[cv.hold_rule.eq('100')&cv.exit_loss.eq(0)]
    return [
        dict(title='2017-2024 trading-cost scenarios',rows=cost_rows(d),widths=[.12,.19,.24,.24,.21],
             intro='Same holdings and trades at every cost level. Both purchases and sales pay the quoted bps.',
             notes='Annual return is compounded. Above-market return is 12 times the mean monthly strategy-minus-market return. Alpha uses the US Carhart model. All recent alpha intervals include zero.'),
        dict(title='When the recent return gap developed',figure=('feedback_costs','fig_time_series.png'),
             notes='Monthly wealth and trailing 12-month compounded return gaps. Rolling windows overlap and describe this sample. They do not establish a forecast or a structural break.'),
        dict(title='Costs that change with quoted spreads',figure=('feedback_costs','fig_spreads.png'),
             notes=f"Cost in month t = reference bps x previous-month average half spread / fixed 2016 average. Quote coverage ranges from {100*sp.quote_coverage.min():.1f}% to {100*sp.quote_coverage.max():.1f}%. Quotes proxy relative costs and omit impact."),
        dict(title='UK data and implementation',rows=[['Item','UK extension'],
             ['Source','Compustat Global daily, 2013-2024. Last observation of each month.'],
             ['Sample','UK-incorporated London ordinary GBP issues. Includes inactive securities.'],
             ['Same portfolio rule','36-month volatility, 12-1 momentum, net payout, quarterly equal weights.'],
             ['Universe and holdings',f"{int(cv.universe_n.min())}-{int(cv.universe_n.max())} eligible universe names, 100 holdings. A top-10% variant is separate."],
             ['Own-market comparator','Same eligible UK universe, cap weights reset quarterly, gross.'],
             ['Interpretation','Current country/exchange headers, missing terminal payments and local currencies limit comparability.']],
             widths=[.25,.75],prose=True,
             notes='Adjusted price = PRCCD / QUNIT / AJEXDI. Adjusted shares = CSHOC x AJEXDI. Total-return index = adjusted price x TRFD. No UK factor alpha is estimated.'),
        dict(title='UK and US after the paper period',rows=country_rows(d),widths=[.37,.19,.20,.24],
             intro='Same 2017-2024 window and 100-stock rule. Compare each strategy with its own country benchmark.',
             notes='UK base sells disappearing positions at last known value. Exit stress loses all remaining value. The separate tax scenario adds 0.5% on purchases with no exemption assumed. UK figures are GBP, US figures USD. The UK advantage reverses under the exit stress. This is exploratory evidence.'),
    ]


def extension_notes(root=results.RESULTS):
    d=load(root);q=d['cost'];q=q.loc[q.period.eq('2017–2024')&q.cost_model.eq('flat')].set_index('reference_bps')
    rows=country_rows(d)
    scripts=[
        f"Following the professor's feedback, we keep the portfolio fixed and vary costs from zero to thirty basis points in steps of five. Annual return falls from {pct(q.loc[0,'compounded'])} before costs to {pct(q.loc[30,'compounded'])} at thirty basis points. At five basis points it is {pct(q.loc[5,'compounded'])}. These are still positive absolute returns, but the market grows faster over these eight years. Lower costs help without creating positive full-period market excess or alpha. The final column shows what happens to an initial one hundred dollars.",
        "The time-series view explains what an eight-year average can hide. The top panel shows the actual wealth paths. The lower panel compares the most recent twelve months of strategy and market returns. The sign can change during the sample. We also calculate trailing thirty-six-month Carhart alpha with Newey-West intervals in the notebook. Those windows overlap, and the short windows produce uncertain estimates. We use them to describe changing performance, rather than claim that we can forecast the next regime.",
        "The transcript also suggests scaling costs with average spreads. We use CRSP closing bid and ask quotes for the eligible large-stock universe. We fix the reference average using 2016, then use only the previous month's spread to set the next month's cost. A five-basis-point reference therefore need not remain five in every month. The chart shows the changing cost assumption and quote coverage. It is a market-wide quote proxy. It does not measure our actual execution price, commissions or market impact.",
        "For the UK comparison, we download Compustat Global daily data and take each month's final available observation. We use ordinary London shares quoted in pounds, retain inactive companies, and use earlier observations to build the same thirty-six-month history. We adjust prices and shares for splits, then use the total-return factor to include distributions. Our benchmark holds the same eligible UK universe at capitalization weights. Current country and exchange headers and incomplete terminal payments make this a qualified extension. We do not use US factors to claim UK alpha.",
        f"At ten basis points, the US strategy returns {rows[1][1]} annually against {rows[1][2]} for its benchmark. The UK base sample returns {rows[2][1]} against {rows[2][2]}. The UK exit stress returns {rows[3][1]} against {rows[3][2]} for its comparator, reversing the relative advantage. Adding a fifty-basis-point purchase tax to the ordinary ten-basis-point costs gives {rows[4][1]} for the UK base case. The relative UK result is more encouraging in this sample, but pounds and dollars represent different investor exposures. The benchmark definitions also differ. We should check historical classifications, terminal payments and a common-currency benchmark before calling this a robust country effect.",
    ]
    return [dict(title=e['title'],paragraphs=[s],cue='Explain the comparison and its limits.',transition='') for e,s in zip(extras(root),scripts)]


def add_report(r):
    d=load(r.root)
    r.heading('17. Follow-up to presentation feedback')
    r.p('The professor suggested a finer recent-period cost grid, costs that change with average spreads, and a UK comparison. We keep the original US stock-selection rule and report these follow-ups separately. The transcript does not specify a forecasting model. Our time-series analysis therefore examines annual returns, rolling return gaps and rolling factor alpha.')
    r.sub('US costs, 2017-2024')
    rows=cost_rows(d);r.table(rows[0],rows[1:],[.12,.18,.24,.24,.22])
    r.p('The table charges every dollar purchased or sold, including the initial investment. Annual return is compounded; market excess is 12 times the average monthly strategy-minus-CRSP-market return. Carhart alpha is annualized from a monthly US four-factor regression with Newey-West 12-lag intervals. All seven recent alpha intervals contain zero. Positive absolute profit coexists with market underperformance even before costs.')
    r.figure('feedback_costs','fig_time_series.png','Recent wealth paths and overlapping trailing 12-month return gaps.',height=280)
    r.figure('feedback_costs','fig_rolling_alpha.png','Trailing 36-month Carhart alpha and HAC 95% intervals. Overlapping windows are descriptive, with no formal break-date or forecasting claim.',height=190)
    r.sub('Lagged spread scaling')
    r.p('We use actual CRSP closing BID and ASK fields, not intraday high and low. After checking positive and ordered quotes, we compute the quoted half spread as 5,000 x (ASK-BID) / midpoint in bps. Full relative spreads above 50% are excluded. Each month averages the largest 1,000 eligible history-qualified stocks. Coverage must exceed 80% in every month.')
    r.p('For each reference level c in 0, 5, ..., 30 bps, cost in month t is c times the prior calendar-month average half spread divided by the fixed 2016 average. This uses only information available before the return month. The reference level describes 2016 conditions rather than the realized 2017-2024 average. Costs affect rebalance trades only. Closing quotes measure relative liquidity, not actual execution costs.')
    q=d['cost'];q=q.loc[q.period.eq('2017–2024')&q.cost_model.eq('lagged_spread')]
    r.table(['2016 reference bps','Mean modeled bps','Annual return','Market excess / yr'],[[f'{x.reference_bps:.0f}',f'{x.mean_bps:.2f}',pct(x.compounded),pct(x.excess_vs_market)] for x in q.itertuples()],[.25]*4)
    r.figure('feedback_costs','fig_spreads.png','Lagged quote-scaled costs and monthly quote coverage.',height=250)
    r.sub('UK sample and cleaning')
    r.p('WRDS query 11803424 supplies 7,906,471 daily rows from January 2013 through December 2024 for FIC=GBR. We keep the final available daily observation per issue and calendar month. The analysis keeps EXCHG=194, TPCI=0 and CURCDD=GBP, with the largest eligible issue per company each month. Active and inactive securities remain. The sample contains 178,848 monthly observations across 2,008 issues before history and portfolio screens. No stock-level records appear in the public repository.')
    r.p('Compustat adjusted price is PRCCD / QUNIT / AJEXDI, adjusted shares are CSHOC x AJEXDI, and the total-return index is adjusted price x TRFD. A factor of one replaces TRFD only for issues whose entire observed factor series is missing, following the WRDS no-dividend convention. Month-to-month ratios require consecutive calendar months. Gaps invalidate signal histories. For held positions, missing months carry at zero and remain ineligible for new purchases. Dividend cash uses the same monthly total-return-minus-price-return proxy as the US calculation, multiplied by prior adjusted price. The split-adjusted share-count term remains part of net payout.')
    cv=d['coverage'];cv=cv.loc[cv.hold_rule.eq('100')&cv.exit_loss.eq(0)]
    r.p(f"First formation is December 2016, followed by 96 investment months. The eligible universe ranges from {int(cv.universe_n.min())} to {int(cv.universe_n.max())} names. We retain the 100-stock baseline, and also report a proportional top-10% holding rule. Quarter-end signals earn returns only in the next month. The UK comparator uses the same history-qualified largest-1,000 universe, capitalization weights and quarterly timing. This differs from the broad CRSP US index. UK cash earns zero because no UK short-rate series is supplied. No UK Sharpe or factor alpha is claimed.")
    r.table(country_rows(d)[0],country_rows(d)[1:],[.37,.19,.20,.24])
    r.figure('uk_comparison','fig_comparison.png','Country performance relative to each own-market comparator. Local currency returns do not represent a common USD investor.',height=220)
    r.p('We lack CRSP-equivalent observed UK terminal payments. The base scenario liquidates disappearing issues at the last known value in the next month. A severe stress assigns a 100% loss to every disappearing issue, including those that may have merged for positive consideration. Both the portfolio and its UK comparator use the same scenario. This is a sensitivity range, not an estimate of actual delisting losses.')
    r.p('The generic 0-30 bps scenarios exclude taxes. A separate UK test charges 0.5% on purchase notional, including the initial purchase, in addition to the symmetric trading cost. It assumes no exemptions. HMRC documents the principal electronic share-purchase SDRT rate at <link href="https://www.gov.uk/tax-buy-shares/buy-shares-electronically" color="#087C86">0.5%</link>. The scenario is deliberately explicit rather than treating 5-30 bps as a complete UK implementation cost.')
    r.p('The UK base results are more encouraging in this selected sample. The severe exit stress reverses its market excess, so the apparent advantage depends on terminal-value assumptions. Current country, exchange and issue-type classifications introduce historical-selection uncertainty. UK GBP and US USD returns have different currency exposures. Benchmarks differ, UK delisting payments are incomplete and a UK factor model is absent. This extension follows presentation feedback after the sample was already seen. It does not establish a robust country effect or justify changing the original formula to maximize these eight years of results.')
    r.p('Source methodology: WRDS, <link href="https://wrds-www.wharton.upenn.edu/pages/support/support-articles/compustat/global/computing-returns/" color="#087C86">Computing Returns</link>. Public metadata in data/uk_source.json and results/uk_comparison/run_meta.json record the export hash, variables and transformations. Licensed source data remain in the private course package.', 'small')

