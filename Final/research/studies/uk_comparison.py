"""UK stock-level extension, 2017-2024. Yingni Chang and Yikai Shen.

Compustat Global data are private. Country/exchange/type headers are current,
not point-in-time. This is an exploratory sample comparison, not an exact UK
replication. Exit-loss scenarios expose missing terminal payment information.
"""
import json
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from crsp_pipeline.normalize import consecutive
from research import engine, report, results
from research.studies._common import FINAL
from research.studies.feedback_costs import COSTS

NAME = 'uk_comparison'
FIXED_END = pd.Timestamp('2024-12-31')
DEPENDS = ('feedback_costs',)
FILES = {n: dict(description=d, window='2017-01 .. 2024-12', returns='gross and net', role='exploratory') for n,d in [
 ('summary.csv','UK fixed-100 and proportional portfolios, exit stress, US reference, cost grid'),
 ('monthly.csv','Monthly country strategy, comparator and net returns; local currencies'),
 ('coverage.csv','UK formation counts and missing-data diagnostics'),
 ('annual.csv','Calendar-year UK and US strategy and own-market returns'),
 ('tax_sensitivity.csv','UK generic costs plus 0.5% purchase-side SDRT scenario; no exemptions assumed'),
 ('run_meta.json','Download identity, cleaning, terminal scenarios and interpretation limits'),
 ('fig_comparison.png','Country wealth relative to own benchmark and cost sensitivity'),
]}
RAW = FINAL/'data/raw/uk/compustat_global_uk_2013_2024.zip'


def monthly_source(output):
    """Month's final available daily observation; no active-only screen."""
    receipt=json.loads((FINAL/'data/uk_source.json').read_text())
    if results.sha256(RAW)!=receipt['sha256']: raise ValueError('UK raw source hash mismatch')
    cache=Path(output)/'uk_monthly_input.parquet'
    mf=cache.with_suffix('.metadata.json')
    if cache.exists() and mf.exists():
        m=json.loads(mf.read_text())
        if m['source_sha256']==receipt['sha256'] and m['sha256']==results.sha256(cache):
            return pd.read_parquet(cache),receipt
    parts=[]
    with zipfile.ZipFile(RAW) as z:
        with z.open(z.namelist()[0]) as f:
            for d in pd.read_csv(f,chunksize=400000,low_memory=False,
                                 dtype={'gvkey':str,'iid':str,'tpci':str}):
                d['date']=pd.to_datetime(d.datadate)+pd.offsets.MonthEnd(0)
                parts.append(d.sort_values('datadate').groupby(['gvkey','iid','date']).tail(1))
    d=pd.concat(parts).sort_values('datadate').groupby(['gvkey','iid','date']).tail(1).reset_index(drop=True)
    d.to_parquet(cache,index=False)
    mf.write_text(json.dumps({'source_sha256':receipt['sha256'],'sha256':results.sha256(cache)},indent=2))
    return d,receipt


def adjusted_values(price, unit, adjustment, shares, trf):
    """Compustat: adjusted price=PRCCD/QUNIT/AJEXDI; shares=CSHOC*AJEXDI."""
    ap=price/unit/adjustment
    return ap, shares*adjustment, ap*trf


def normalize(d, exit_loss=0):
    # Ordinary GBP issues on the UK exchanges represented by header codes.
    # 194 is London; 349 is AIM. Use London main market for a large-stock test.
    d=d.loc[d.curcdd.eq('GBP') & d.tpci.eq('0') & d.exchg.eq(194)].copy()
    keys=sorted((d.gvkey+'_'+d.iid).unique())
    d['permno']=(d.gvkey+'_'+d.iid).map({k:i+1 for i,k in enumerate(keys)})
    d=d.sort_values(['permno','date']).reset_index(drop=True)
    for c in ['prccd','qunit','ajexdi','cshoc','trfd']:
        d[c]=pd.to_numeric(d[c],errors='coerce')
    # Only an issue whose entire observed TRFD history is missing gets factor 1.
    never=d.groupby('permno').trfd.transform('count').eq(0)
    d.loc[never,'trfd']=1.
    p,s,tri=adjusted_values(d.prccd,d.qunit,d.ajexdi,d.cshoc,d.trfd)
    d['price_adj'],d['shares_adj'],d['tri']=p,s,tri
    d['mktcap']=d.prccd/d.qunit*d.cshoc
    g=d.groupby('permno')
    contiguous=(d.date.dt.year*12+d.date.dt.month).sub((g.date.shift().dt.year*12+g.date.shift().dt.month)).eq(1)
    same_currency=d.curcdd.eq(g.curcdd.shift())
    d['ret_price']=(d.price_adj/g.price_adj.shift()-1).where(contiguous & same_currency)
    d['ret_total']=(d.tri/g.tri.shift()-1).where(contiguous & same_currency)
    # Same dividend-cash proxy as US normalization; retains monthly TRF distributions.
    cash=(d.ret_total-d.ret_price)*g.price_adj.shift()
    bad_negative=cash.lt(-1e-8)
    d['div_cash_adj']=cash.clip(lower=0).where(~bad_negative)
    d['eligible']=d[['price_adj','shares_adj','mktcap']].gt(0).all(axis=1) & d.ret_total.notna()
    # One largest currently reported class per company, each month, without future size.
    winners=d.loc[d.eligible].sort_values(['date','gvkey','mktcap','permno'],ascending=[True,True,False,True]).drop_duplicates(['date','gvkey']).index
    d['eligible']=d.index.isin(winners)
    d['hist36']=consecutive(d,d.ret_total.notna(),36)
    d['is_exit']=False
    d['ret_hold']=d.ret_total
    d['ret_hold_source']=np.where(d.ret_total.notna(),'crsp','no_prior_row') # engine contract label only
    # Complete each issue's observed calendar, carrying unobserved months at zero,
    # ineligible for formation. Never bridge a missing month in the signal history.
    rows=[]
    for _,x in d.groupby('permno',sort=False):
        x=x.set_index('date')
        last=x.index.max()
        terminal=last<pd.Timestamp('2024-12-31')
        final=last+pd.offsets.MonthEnd(1) if terminal else last
        x=x.reindex(pd.date_range(x.index.min(),final,freq='ME'))
        x['permno']=x.permno.ffill()
        for c in ['eligible','hist36','is_exit']: x[c]=x[c].fillna(False).astype(bool)
        missing=x.ret_total.isna()
        x.loc[missing,'ret_hold']=0.
        x.loc[missing,'ret_hold_source']='stale_carry'
        # Entry has no past return and cannot be held; preserve the engine contract.
        x.iloc[0,x.columns.get_loc('ret_hold')]=np.nan
        x.iloc[0,x.columns.get_loc('ret_hold_source')]='no_prior_row'
        if terminal:
            x.loc[final,['ret_hold','ret_total']]=exit_loss
            x.loc[final,'ret_hold_source']='crsp'
            x.loc[final,'is_exit']=True
        rows.append(x.rename_axis('date').reset_index())
    out=pd.concat(rows,ignore_index=True).sort_values(['permno','date']).reset_index(drop=True)
    out['permno']=out.permno.astype(int)
    # Recompute signals on completed calendars so missing months invalidate windows.
    out['hist36']=consecutive(out,out.ret_total.notna() & ~out.is_exit,36)
    return out,dict(input_monthly_rows=len(d),issues=len(keys),inactive_rows=int(d.secstat.eq('I').sum()),
                    missing_share_rows=int(d.cshoc.isna().sum()),negative_distribution_rows=int(bad_negative.sum()),
                    gap_or_terminal_rows=int(out.ret_hold_source.eq('stale_carry').sum()),
                    terminal_events=int(out.is_exit.sum()),exit_loss=exit_loss)


def run(ctx):
    out=ctx.out(NAME)
    raw,receipt=monthly_source(ctx.output)
    idx=pd.date_range('2017-01-31','2024-12-31',freq='ME')
    zero=pd.Series(0.,index=idx)
    bench=pd.DataFrame({'market_ret':zero,'rf':zero})
    monthly=[]; summaries=[]; coverage=[]; diagnostics=[]; tax_rows=[]
    for loss in [0.,-1.]:
        p,diag=normalize(raw,loss); diagnostics.append(diag)
        p,_=engine.validate_inputs(p,bench.reset_index(names='date'))
        sig=engine.attach_signals(p)
        # Domestic cap-weight benchmark uses same history/size universe and timing.
        tm,c=engine.formation_targets(sig,['Universe cap weight'],start=idx[0],last=idx[-1])
        market=engine.backtest(p,bench,tm['Universe cap weight'],idx[0],idx[-1],0)['gross']
        for hold in [100,'pct10']:
            tm,c=engine.formation_targets(sig,['Conservative'],start=idx[0],last=idx[-1],n_hold=hold)
            logs=[]
            run=engine.backtest(p,bench,tm['Conservative'],idx[0],idx[-1],0,trade_log=logs)
            trades=pd.concat(logs)
            buys=trades.assign(buy=trades.trade.clip(lower=0)).groupby('formation').buy.sum()
            buys.index=buys.index+pd.offsets.MonthEnd(1)
            tax=.005*buys.reindex(idx,fill_value=0)
            c['hold_rule']=str(hold);c['exit_loss']=loss;coverage.append(c)
            for bps in COSTS:
                r=report.net_from_gross(run,bps)
                taxed=(1-run.traded_notional*bps/10000-tax)*(1+run.gross)-1
                tx=report.statistics(taxed,zero)
                tax_rows.append(dict(hold_rule=str(hold),exit_loss=loss,cost_bps=bps,stamp_duty_buy_bps=50,
                    compounded=tx['compounded'],market_excess_annual=12*(taxed-market).mean(),
                    terminal_wealth100=100*(1+taxed).prod()))
                st=report.statistics(r,zero)
                summaries.append(dict(country='UK',currency='GBP',hold_rule=str(hold),exit_loss=loss,cost_bps=bps,
                    **{k:st[k] for k in ['months','compounded','arithmetic','volatility','max_drawdown']},
                    market_cagr=report.statistics(market,zero)['compounded'],
                    market_excess_annual=12*(r-market).mean(),terminal_wealth100=100*(1+r).prod(),
                    turnover=report.quarterly_turnover(run)['one_way_per_quarter']))
                monthly.append(pd.DataFrame(dict(date=idx,country='UK',currency='GBP',hold_rule=str(hold),exit_loss=loss,
                    cost_bps=bps,portfolio_return=r.to_numpy(),market_return=market.to_numpy(),
                    traded_notional=run.traded_notional.to_numpy(),stale_weight=run.stale_weight.to_numpy())))
    us=pd.read_csv(ctx.result('feedback_costs','monthly.csv'),parse_dates=['date'])
    us=us.loc[us.cost_model.eq('flat')]
    uss=pd.read_csv(ctx.result('feedback_costs','cost_summary.csv')).rename(columns={'excess_vs_market':'market_excess_annual','terminal_wealth_100':'terminal_wealth100'})
    uss=uss.loc[uss.cost_model.eq('flat') & uss.period.eq('2017–2024')]
    for _,x in uss.iterrows():
        summaries.append(dict(country='US',currency='USD',hold_rule='100',exit_loss=np.nan,cost_bps=x.reference_bps,
            **{k:x[k] for k in ['months','compounded','arithmetic','volatility','max_drawdown','market_cagr','market_excess_annual','terminal_wealth100']}))
    for bps,g in us.groupby('reference_bps'):
        monthly.append(pd.DataFrame(dict(date=g.date,country='US',currency='USD',hold_rule='100',exit_loss=np.nan,
            cost_bps=bps,portfolio_return=g.portfolio_return,market_return=g.market_return)))
    s=pd.DataFrame(summaries);m=pd.concat(monthly,ignore_index=True);c=pd.concat(coverage,ignore_index=True)
    pd.DataFrame(tax_rows).to_csv(out/'tax_sensitivity.csv',index=False)
    s.to_csv(out/'summary.csv',index=False);m.to_csv(out/'monthly.csv',index=False);c.to_csv(out/'coverage.csv',index=False)
    m['year']=m.date.dt.year
    annual=m.groupby(['country','currency','hold_rule','exit_loss','cost_bps','year'],dropna=False).agg(
        portfolio_return=('portfolio_return',lambda r:(1+r).prod()-1),market_return=('market_return',lambda r:(1+r).prod()-1)).reset_index()
    annual.to_csv(out/'annual.csv',index=False)
    meta=dict(authors=['Yingni Chang','Yikai Shen'],source=receipt,cleaning=diagnostics,
        formula='price=PRCCD/QUNIT/AJEXDI; shares=CSHOC*AJEXDI; total-return index=adjusted price*TRFD',
        dividend_proxy='Monthly (total return-price return)*prior adjusted price; same cash-proxy convention as US',
        sample='FIC=GBR, EXCHG=194 (London), TPCI=0, CURCDD=GBP; largest eligible issue per GVKEY each month; no active-only filter',
        timing='2013-2024 inputs, 36 calendar-month history; Dec 2016 first formation, Jan 2017 first return; quarterly',
        benchmark='UK same eligible top-1000 universe, cap weights reset quarterly, gross. US CRSP VW broad market.',
        cash='UK idle cash earns zero: no UK risk-free data used. No UK alpha or Sharpe claimed.',
        terminal='At first month after final observation, liquidate at last known value (base) or lose 100% of remaining value (stress). No observed CRSP-equivalent delisting payments. Stress is not an estimate.',
        limitations='Exploratory and selected after feedback. Header country/exchange/type classifications are current. London main-market sample is narrower than all UK equities. Currency returns are local, no FX hedge or common USD investor return. Prices can be stale; gap cash carry at zero. No UK factor regression. Generic 0-30bps scenarios exclude tax and impact. A separate scenario charges 0.5% SDRT on all purchases, including entry, with no exemption assumed.',
        sdrt_reference='https://www.gov.uk/tax-buy-shares/buy-shares-electronically',
        official_returns='https://wrds-www.wharton.upenn.edu/pages/support/support-articles/compustat/global/computing-returns/')
    (out/'run_meta.json').write_text(json.dumps(meta,indent=2,default=str))
    fig,axes=plt.subplots(1,2,figsize=(12.5,4.5),layout='constrained')
    for country,color in [('US','#203449'),('UK','#087c86')]:
        sub=m.loc[m.country.eq(country)&m.hold_rule.eq('100')&m.cost_bps.eq(10)&(m.exit_loss.eq(0)|m.exit_loss.isna())].sort_values('date')
        ratio=(1+sub.portfolio_return).cumprod()/(1+sub.market_return).cumprod()
        axes[0].plot(sub.date,ratio,label=f'{country}, net 10bps',color=color)
        sub=s.loc[s.country.eq(country)&s.hold_rule.eq('100')&(s.exit_loss.eq(0)|s.exit_loss.isna())].sort_values('cost_bps')
        axes[1].plot(sub.cost_bps,100*sub.market_excess_annual,marker='o',label=country,color=color)
    stress=s.loc[s.country.eq('UK')&s.hold_rule.eq('100')&s.exit_loss.eq(-1)].sort_values('cost_bps')
    axes[1].plot(stress.cost_bps,100*stress.market_excess_annual,'--',color='#aa6752',label='UK, all exits lose 100%')
    axes[0].axhline(1,color='gray',lw=.7);axes[1].axhline(0,color='gray',lw=.7)
    axes[0].set(title='Wealth relative to each own-market benchmark',ylabel='Strategy wealth / benchmark wealth')
    axes[1].set(title='Cost sensitivity, 2017-2024',xlabel='Cost per traded dollar (bps)',ylabel='Annual arithmetic market excess (%)')
    for a in axes:a.legend(fontsize=8);a.grid(alpha=.15)
    fig.savefig(out/'fig_comparison.png',dpi=190);plt.close(fig)

