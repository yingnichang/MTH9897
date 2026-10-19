"""Post-presentation cost sensitivity and descriptive time-series analysis.

Authors: Yingni Chang and Yikai Shen. No new stock-selection parameters are fitted.
Quotes are month-end BID/ASK, not intraday highs/lows or measured execution costs.
"""
import json
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from crsp_pipeline import config
from research import report, results, stats

NAME = 'feedback_costs'
FIXED_END = pd.Timestamp('2024-12-31')
DEPENDS = ('critical_tests',)
COSTS = (0, 5, 10, 15, 20, 25, 30)
FILES = {name: dict(description=description, window=window, returns='gross and net', role=role)
         for name, description, window, role in [
    ('cost_summary.csv', 'Fixed 0-30bps scenarios across fixed periods, plus recent lagged-spread scenarios', '1929–2024; 2017–2024 focus', 'primary'),
    ('monthly.csv', 'Recent monthly portfolio returns, actual modeled bps, wealth and 12-month return gaps', '2017-01 .. 2024-12', 'primary'),
    ('annual.csv', 'Calendar-year strategy and market returns at each fixed cost', '2017 .. 2024', 'primary'),
    ('rolling_alpha.csv', 'Overlapping trailing 36-month Carhart regressions, descriptive only', '2019-12 .. 2024-12', 'check'),
    ('spread_coverage.csv', 'Top-1000 eligible universe quote coverage and average half spread', '2016-01 .. 2024-12', 'check'),
    ('run_meta.json', 'Source hashes, conventions, calibration and exact net10/net30 reconstruction checks', 'run record', 'check'),
    ('fig_costs.png', 'US recent cost grid: absolute return, market excess and Carhart alpha', '2017–2024', 'primary'),
    ('fig_time_series.png', 'Wealth and trailing 12-month compounded return gap', '2017–2024', 'primary'),
    ('fig_spreads.png', 'Lagged quoted-spread cost scaling and quote coverage', '2017–2024', 'check'),
    ('fig_rolling_alpha.png', 'Trailing 36-month Carhart alpha with HAC intervals', '2019-12 .. 2024-12', 'check'),
]}


def cost_return(gross, net30, bps):
    """Exact affine interpolation of the unchanged engine's proportional cost haircut."""
    if np.any(np.asarray(bps) < 0):
        raise ValueError('Trading costs cannot be negative')
    out = gross-(gross-net30)*bps/30
    if out.le(-1).any():
        raise ValueError('Cost scenario exhausts capital')
    return out


def lagged_costs(spreads, index, base):
    """Normalize to a fixed 2016 reference; use only the previous calendar month."""
    reference = spreads.loc['2016-01-31':'2016-12-31']
    if len(reference) != 12 or reference.isna().any() or reference.mean() <= 0:
        raise ValueError('Need all 12 positive-reference calibration months in 2016')
    previous = pd.DatetimeIndex(index)-pd.offsets.MonthEnd(1)
    lag = spreads.reindex(previous)
    if lag.isna().any():
        raise ValueError('Missing prior-calendar-month spread; no forward filling')
    return pd.Series(base*lag.to_numpy()/reference.mean(), index=index)


def quote_proxy(ctx):
    folder = config.RAW/'wrds_complete'
    source = folder/'crsp_monthly_legacy_1925_2024.zip'
    receipt = json.loads((folder/'download_manifest.json').read_text())['files'][source.name]
    h = results.sha256(source)
    if h != receipt['sha256']:
        raise ValueError('Original WRDS quote source hash mismatch')
    cache = Path(ctx.output)/'feedback_quotes.parquet'
    meta_file = cache.with_suffix('.metadata.json')
    identity = {'source_sha256': h, 'transform': 'permno,date,bid,ask;2016-2024;deduplicate;v1'}
    valid_cache = (cache.exists() and meta_file.exists()
                   and json.loads(meta_file.read_text()).get('input') == identity
                   and json.loads(meta_file.read_text()).get('cache_sha256') == results.sha256(cache))
    if not valid_cache:
        chunks = []
        with zipfile.ZipFile(source) as z:
            with z.open(z.namelist()[0]) as stream:
                for p in pd.read_csv(stream, usecols=lambda c: c.lower() in {'permno','date','bid','ask'},
                                     chunksize=300000, low_memory=False):
                    p.columns = p.columns.str.lower()
                    chunks.append(p.loc[p.date.ge('2016-01-01') & p.date.le('2024-12-31')])
        quotes = pd.concat(chunks, ignore_index=True).drop_duplicates()
        cache.parent.mkdir(parents=True, exist_ok=True)
        quotes.to_parquet(cache, index=False)
        meta_file.write_text(json.dumps({'input': identity, 'cache_sha256': results.sha256(cache)}, indent=2))
    q = pd.read_parquet(cache)
    q['date'] = pd.to_datetime(q.date)+pd.offsets.MonthEnd(0)
    if q.duplicated(['permno','date']).any():
        raise ValueError('Conflicting security-month quotes')
    for col in ['bid','ask']: q[col] = pd.to_numeric(q[col], errors='coerce')
    p = pd.read_parquet(config.PANEL_FILE, columns=['date','permno','eligible','hist36','mktcap'])
    p = p.loc[p.date.between('2016-01-31','2024-12-31') & p.eligible & p.hist36 & p.mktcap.gt(0)]
    p = p.sort_values(['date','mktcap','permno'], ascending=[True,False,True]).groupby('date').head(1000)
    p = p.merge(q, on=['date','permno'], how='left', validate='one_to_one')
    spread = (p.ask-p.bid)/((p.ask+p.bid)/2)
    good = p.bid.gt(0) & p.ask.ge(p.bid) & spread.le(.5)
    p['half_spread_bps'] = (5000*spread).where(good)
    coverage = p.groupby('date').agg(universe_n=('permno','size'), valid_quotes=('half_spread_bps','count'),
                                    mean_half_spread_bps=('half_spread_bps','mean'),
                                    median_half_spread_bps=('half_spread_bps','median'))
    coverage['quote_coverage'] = coverage.valid_quotes/coverage.universe_n
    expected = pd.date_range('2016-01-31','2024-12-31',freq='ME')
    if not coverage.index.equals(expected) or coverage.quote_coverage.lt(.8).any():
        raise ValueError('Insufficient quote coverage: need every month and at least 80% of the universe')
    return coverage, {'quote_source_sha256':h, 'quote_query':receipt['url'],
                      'private_quote_cache_sha256':results.sha256(cache)}


def summarize(r, market, rf, fac):
    alpha = stats.ols(r-rf, fac[stats.MODELS['Carhart']],12)
    s = report.statistics(r,rf)
    return {**s, 'terminal_wealth_100':float(100*(1+r).prod()),
            'profit_on_100':float(100*((1+r).prod()-1)),
            'excess_vs_market':float(12*(r-market).mean()),
            'market_cagr':float((1+market).prod()**(12/len(r))-1),
            'carhart_alpha':alpha['alpha_annual'], 'alpha_t_nw':alpha['alpha_t_nw'],
            'alpha_ci_low':alpha['alpha_ci95_low'], 'alpha_ci_high':alpha['alpha_ci95_high']}


def run(ctx):
    out = ctx.out(NAME)
    series = pd.read_csv(ctx.result('critical_tests','returns_monthly.csv'), parse_dates=['date'],
                         index_col='date',float_precision='round_trip')
    fac = pd.read_csv(config.FACTORS_FILE,parse_dates=['date'],index_col='date')
    gross, net30 = series['Conservative | gross'], series['Conservative | net30']
    reconstructed = cost_return(gross,net30,10)
    residual = float((reconstructed-series['Conservative | net10']).abs().max())
    if residual > 2e-15: raise AssertionError('Does not reproduce engine net10')
    coverage, source = quote_proxy(ctx)
    coverage.to_csv(out/'spread_coverage.csv',date_format='%Y-%m-%d')
    recent = series.loc['2017-01-31':'2024-12-31']
    assert recent.index.equals(pd.date_range('2017-01-31','2024-12-31',freq='ME'))
    rows, monthly, annual, rolling = [], [], [], []
    for period in report.PERIODS:
        w = report.period_slice(series,period)
        for c in COSTS:
            r = cost_return(w['Conservative | gross'],w['Conservative | net30'],c)
            rows.append(dict(period=period,cost_model='flat',reference_bps=c,mean_bps=c,
                             **summarize(r,w['Market (CRSP VW) | gross'],w.rf,fac.loc[w.index])))
    for model in ['flat','lagged_spread']:
        for c in COSTS:
            bps = pd.Series(c,index=recent.index) if model=='flat' else lagged_costs(coverage.mean_half_spread_bps,recent.index,c)
            r = cost_return(recent['Conservative | gross'],recent['Conservative | net30'],bps)
            if model!='flat':
                rows.append(dict(period='2017–2024',cost_model=model,reference_bps=c,mean_bps=float(bps.mean()),
                                 **summarize(r,recent['Market (CRSP VW) | gross'],recent.rf,fac.loc[r.index])))
            wealth = 100*(1+r).cumprod()
            market = recent['Market (CRSP VW) | gross']
            gap12 = (1+r).rolling(12).apply(np.prod,raw=True)-(1+market).rolling(12).apply(np.prod,raw=True)
            monthly.append(pd.DataFrame(dict(date=r.index,cost_model=model,reference_bps=c,applied_bps=bps,
                                            portfolio_return=r,market_return=market,wealth_100=wealth,
                                            rolling12_compound_gap=gap12)))
            if model=='flat':
                for year, yr in r.groupby(r.index.year):
                    annual.append(dict(year=year,cost_bps=c,portfolio_return=float((1+yr).prod()-1),
                                       market_return=float((1+market.loc[yr.index]).prod()-1)))
                if c in [0,5,15,30]:
                    for end in range(35,len(r)):
                        w = r.iloc[end-35:end+1]
                        a = stats.ols(w-recent.rf.loc[w.index],fac.loc[w.index,stats.MODELS['Carhart']],12)
                        rolling.append(dict(window_end=w.index[-1],cost_bps=c,months=36,
                                            alpha=a['alpha_annual'],ci_low=a['alpha_ci95_low'],ci_high=a['alpha_ci95_high']))
    summary = pd.DataFrame(rows)
    pd.concat(monthly,ignore_index=True).to_csv(out/'monthly.csv',index=False,date_format='%Y-%m-%d')
    pd.DataFrame(annual).to_csv(out/'annual.csv',index=False)
    roll = pd.DataFrame(rolling);roll.to_csv(out/'rolling_alpha.csv',index=False,date_format='%Y-%m-%d')
    summary.to_csv(out/'cost_summary.csv',index=False)
    meta = dict(authors=['Yingni Chang','Yikai Shen'],feedback_date='2026-10-18',
                source_interpretation='Cost scenarios by period and scaling with average spreads; no ARIMA request identified.',
                reconstruction_net10_max_abs_error=residual,**source,
                calibration='2016 mean of monthly equal-weighted top-1000 eligible-stock quoted half spreads',
                timing='Previous calendar month only; 2016 reference fixed before 2017; no future normalization',
                quote_filters='BID>0; ASK>=BID; full relative spread<=50%; coverage>=80% every month',
                limitations='Month-end quote proxy, not execution cost. Relative market-wide scaling; no trade-specific impact or commissions. Rolling windows overlap, are descriptive and have only 36 months.',
                panel_sha256=results.sha256(config.PANEL_FILE),factor_sha256=results.sha256(config.FACTORS_FILE))
    (out/'run_meta.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    plot_outputs(out,summary,pd.concat(monthly,ignore_index=True),coverage,roll)


def plot_outputs(out,summary,monthly,coverage,roll):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    w = summary.loc[summary.period.eq('2017–2024') & summary.cost_model.eq('flat')]
    fig,axes = plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
    for ax,col,label in zip(axes,['compounded','excess_vs_market','carhart_alpha'],['Net CAGR (%)','Annual arithmetic excess over market (%)','Annual Carhart alpha (%)']):
        ax.plot(w.reference_bps,100*w[col],'-o',color='#176B87')
        ax.axhline(0,color='gray',lw=.7);ax.set(xlabel='Cost per dollar traded (bps)',ylabel=label)
    fig.suptitle('US Conservative Formula, 2017–2024: lower costs do not change stock selection')
    fig.savefig(out/'fig_costs.png',dpi=180);plt.close(fig)
    fig,axes = plt.subplots(2,1,figsize=(11,6.3),layout='constrained')
    for c in [0,5,15,30]:
        m = monthly.loc[monthly.cost_model.eq('flat') & monthly.reference_bps.eq(c)]
        axes[0].plot(m.date,m.wealth_100,label=f'{c} bps')
        axes[1].plot(m.date,100*m.rolling12_compound_gap,label=f'{c} bps')
    m = monthly.loc[monthly.cost_model.eq('flat') & monthly.reference_bps.eq(0)]
    axes[0].plot(m.date,100*(1+m.market_return).cumprod(),'k--',label='CRSP market')
    axes[0].set(ylabel='Wealth from $100');axes[1].set(ylabel='Trailing 12-month compound gap (pp)')
    axes[1].axhline(0,color='gray',lw=.7)
    for ax in axes:ax.legend(ncol=5,fontsize=9)
    fig.savefig(out/'fig_time_series.png',dpi=180);plt.close(fig)
    fig,axes = plt.subplots(2,1,figsize=(10,5.4),layout='constrained')
    for c in [5,15,30]:
        m=monthly.loc[monthly.cost_model.eq('lagged_spread') & monthly.reference_bps.eq(c)]
        axes[0].plot(m.date,m.applied_bps,label=f'{c} bps at 2016 spread')
    axes[0].set(ylabel='Modeled cost (bps)');axes[0].legend(fontsize=9)
    axes[1].plot(coverage.index,100*coverage.quote_coverage,color='#176B87')
    axes[1].set(ylabel='Eligible-universe quote coverage (%)',ylim=(0,105))
    fig.savefig(out/'fig_spreads.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,3.7),layout='constrained')
    for c in [0,30]:
        m=roll.loc[roll.cost_bps.eq(c)]
        ax.plot(m.window_end,100*m.alpha,label=f'{c} bps')
        ax.fill_between(m.window_end,100*m.ci_low,100*m.ci_high,alpha=.12)
    ax.axhline(0,color='gray',lw=.7);ax.set(ylabel='Annual Carhart alpha (%)',title='Trailing 36-month estimates: overlapping, descriptive windows')
    ax.legend();fig.savefig(out/'fig_rolling_alpha.png',dpi=180);plt.close(fig)
