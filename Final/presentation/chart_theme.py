"""Presentation-only chart styling from verified aggregates.

Authors: Yingni Chang and Yikai Shen. Does not change research outputs or backtests.
"""
from io import BytesIO
from types import SimpleNamespace
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cycler import cycler
import pandas as pd
from research import results

NAVY='#102C3B';TEAL='#087F83';SAGE='#7CA7A0';COPPER='#B56E4F';SLATE='#627987';CREAM='#F5F3EE'
STYLE={'figure.facecolor':CREAM,'axes.facecolor':CREAM,'axes.edgecolor':'#CBD5D1',
       'axes.labelcolor':'#183342','text.color':'#183342','xtick.color':'#536B73','ytick.color':'#536B73',
       'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,
       'axes.prop_cycle':cycler(color=[TEAL,NAVY,SAGE,COPPER,SLATE]),'font.size':10,
       'legend.frameon':False,'grid.color':'#D7DEDA','grid.linewidth':.6}


def finish(fig):
    for ax in fig.axes:
        ax.tick_params(length=0,pad=5)
        ax.grid(axis='y',alpha=.7)
    b=BytesIO();fig.savefig(b,format='png',dpi=210);plt.close(fig)
    from PIL import Image
    data=b.getvalue()
    with Image.open(BytesIO(data)) as im:w,h=im.size
    return SimpleNamespace(width=w,height=h,image=SimpleNamespace(blob=data))


def chart(number,root=results.RESULTS):
    load=lambda study,name,**kw:results.load(study,name,root,**kw)[0]
    with plt.rc_context(STYLE):
        if number==6:
            d=load('replication','returns_monthly.csv',parse_dates=['date'],index_col='date')
            fig,ax=plt.subplots(figsize=(5.6,3.5),layout='constrained')
            for key,label,color in [('Conservative_gross','Conservative',TEAL),('Speculative_gross','Speculative',SLATE),('Market','Market (CRSP VW)',COPPER)]:
                w=pd.concat([pd.Series([100.],index=[d.index[0]-pd.offsets.MonthEnd(1)]),100*(1+d[key]).cumprod()])
                ax.plot(w.index,w,color=color,lw=1.7,label=label)
            ax.set(yscale='log',ylabel='Value of $100 (log scale, gross)',title='Growth of $100, 1929–2016')
            ax.legend(fontsize=8)
        elif number==9:
            d=load('critical_tests','rolling.csv',parse_dates=['window_end'])
            fig,axes=plt.subplots(2,1,figsize=(5.1,5.1),sharex=True,layout='constrained')
            for col,ax,label in [('excess_vs_market',axes[0],'Excess over CRSP VW (%/yr)'),('carhart_alpha',axes[1],'Carhart alpha (%/yr)')]:
                for kind,ls,color in [('gross','-',TEAL),('net30','--',COPPER)]:
                    g=d.loc[d.returns.eq(kind)]
                    ax.plot(g.window_end,100*g[col],ls,color=color,lw=1.7,label=f'Conservative, {kind}')
                ax.axhline(0,color=SLATE,lw=.6)
                for date in ['1963-01-31','1990-01-31','2017-01-31']:ax.axvline(pd.Timestamp(date),color=SLATE,lw=.7,ls=':')
                ax.set_ylabel(label);ax.legend(fontsize=7,loc='upper left')
            axes[0].set_title('Rolling 120-month windows\nDotted boundaries: 1963, 1990, 2017',fontsize=10)
        elif number==13:
            d=load('diagnostics','ic_decay.csv');p=load('diagnostics','persistence.csv')
            names={'lowvol_z':'Low volatility','momentum_z':'Momentum (12-1)','npy_z':'Net payout yield','composite_z':'Composite'}
            fig,axes=plt.subplots(2,1,figsize=(5.1,5.2),layout='constrained')
            for name,label in names.items():
                for frame,ax in [(d,axes[0]),(p,axes[1])]:
                    g=frame.loc[frame.exposure.eq(name)].sort_values('h')
                    ax.plot(g.h,g['mean'],marker='o',ms=3,lw=1.5,label=label)
            axes[0].set(xlabel='Horizon h (months)',ylabel='Mean rank IC',title='IC decay')
            axes[1].set(xlabel='Lag h (months)',ylabel='Mean rank correlation',title='Exposure persistence')
            axes[0].axhline(0,color=SLATE,lw=.6);axes[0].legend(fontsize=7,ncol=2)
        elif number==14:
            d=load('optimization','grid.csv')
            fig,ax=plt.subplots(figsize=(5.5,4.5),layout='constrained')
            for delta,color in [('2%',TEAL),('5%',COPPER),('none',SLATE)]:
                for cost,marker in [(10,'o'),(30,'s')]:
                    g=d.loc[d.role.eq('spec')&d.delta.eq(delta)&d.c0_bps.eq(cost)].sort_values('turnover_one_way_per_quarter')
                    ax.plot(100*g.turnover_one_way_per_quarter,g.ir,marker=marker,color=color,lw=1.7,label=f'Band {delta}; {cost}bps')
            ax.set(xlabel='One-way quarterly turnover (%)',ylabel='Net information ratio',title='Linear optimizer: 1929–2024')
            ax.legend(fontsize=8,ncol=2)
        elif number in {19,20}:
            d=load('feedback_costs','monthly.csv',parse_dates=['date'])
            fig,axes=plt.subplots(2,1,figsize=(11.4,4.3),layout='constrained')
            if number==19:
                for cost,color,ls in [(0,TEAL,'-'),(5,SAGE,'--'),(15,NAVY,':'),(30,SLATE,'-.')]:
                    g=d.loc[d.cost_model.eq('flat')&d.reference_bps.eq(cost)].sort_values('date')
                    axes[0].plot(g.date,g.wealth_100,color=color,ls=ls,lw=1.8,label=f'{cost} bps')
                    axes[1].plot(g.date,100*g.rolling12_compound_gap,color=color,ls=ls,lw=1.8,label=f'{cost} bps')
                g=d.loc[d.cost_model.eq('flat')&d.reference_bps.eq(0)].sort_values('date')
                axes[0].plot(g.date,100*(1+g.market_return).cumprod(),color=COPPER,lw=2,label='CRSP market')
                axes[0].set_ylabel('Wealth from $100');axes[1].set_ylabel('Trailing 12-month gap (pp)')
                axes[1].axhline(0,color=SLATE,lw=.6)
                for ax in axes:ax.legend(fontsize=9,ncol=5,loc='upper left')
            else:
                for cost,color in [(5,SAGE),(15,TEAL),(30,NAVY)]:
                    g=d.loc[d.cost_model.eq('lagged_spread')&d.reference_bps.eq(cost)].sort_values('date')
                    axes[0].plot(g.date,g.applied_bps,color=color,lw=1.8,label=f'{cost} bps at 2016 spread')
                cover=load('feedback_costs','spread_coverage.csv',parse_dates=['date'])
                axes[0].set_ylabel('Modeled cost (bps)');axes[0].legend(fontsize=9,ncol=3)
                axes[1].plot(cover.date,100*cover.quote_coverage,color=TEAL,lw=1.8)
                axes[1].set(ylabel='Quote coverage (%)',ylim=(0,105))
            for ax in axes:ax.set_xlim(pd.Timestamp('2017-01-01') if number==19 else pd.Timestamp('2016-01-01'),pd.Timestamp('2024-12-31'))
        else:return None
        return finish(fig)
