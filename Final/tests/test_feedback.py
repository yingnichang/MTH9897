"""Post-presentation accounting and timing tests. Yingni Chang and Yikai Shen."""
import numpy as np
import pandas as pd
import pytest
from research.studies.feedback_costs import cost_return, lagged_costs
from research.studies.uk_comparison import adjusted_values, normalize


def test_exact_proportional_cost_reconstruction():
    gross=pd.Series([.1,-.1,.03]);trade=pd.Series([1.,.8,0.])
    net30=(1-.003*trade)*(1+gross)-1
    for c in [0,5,10,15,20,25,30]:
        expected=(1-c/10000*trade)*(1+gross)-1
        np.testing.assert_allclose(cost_return(gross,net30,c),expected,atol=2e-16,rtol=0)
    assert (cost_return(gross,net30,5)-cost_return(gross,net30,30)).ge(-2e-16).all()
    with pytest.raises(ValueError):cost_return(gross,net30,-1)


def test_spread_cost_uses_previous_calendar_month_only():
    dates=pd.date_range('2016-01-31','2017-03-31',freq='ME')
    s=pd.Series(10.,index=dates);s.loc['2017-01-31']=20;s.loc['2017-02-28']=100
    ix=pd.date_range('2017-01-31','2017-02-28',freq='ME')
    np.testing.assert_allclose(lagged_costs(s,ix,5),[5,10])
    s.loc['2017-02-28']=5000 # later quotes cannot change January or February cost
    np.testing.assert_allclose(lagged_costs(s,ix,5),[5,10])
    with pytest.raises(ValueError):lagged_costs(s.drop(pd.Timestamp('2016-12-31')),ix,5)


def test_compustat_split_and_quotation_unit_neutrality():
    # Two-for-one split: pre-split adjustment=2, post-split=1.
    p,s,tri=adjusted_values(pd.Series([100.,50.]),pd.Series([1.,1.]),
                           pd.Series([2.,1.]),pd.Series([100.,200.]),pd.Series([1.,1.]))
    np.testing.assert_allclose(p,[50,50]);np.testing.assert_allclose(s,[200,200])
    assert tri.iloc[1]/tri.iloc[0]-1==0
    p2,_,_=adjusted_values(pd.Series([1000.]),pd.Series([100.]),pd.Series([1.]),pd.Series([100.]),pd.Series([1.]))
    assert p2.iloc[0]==10


def test_uk_missing_calendar_month_does_not_create_signal_history():
    dates=pd.date_range('2020-01-31','2024-12-31',freq='ME').delete(20)
    d=pd.DataFrame(dict(date=dates,datadate=dates,gvkey='001',iid='01',tpci='0',exchg=194,curcdd='GBP',
                        prccd=100.,qunit=1.,ajexdi=1.,cshoc=1000.,trfd=1.,secstat='I'))
    p,a=normalize(d)
    gap=p.loc[p.date.eq(pd.Timestamp('2021-09-30'))].iloc[0]
    assert gap.ret_hold==0 and not gap.eligible and pd.isna(gap.ret_total)
    assert not p.loc[p.date.eq(pd.Timestamp('2023-01-31')),'hist36'].iloc[0]
    assert a['inactive_rows']==len(d) # inactive securities are retained


def test_uk_terminal_stress_changes_exit_payment_only():
    dates=pd.date_range('2020-01-31','2024-10-31',freq='ME')
    d=pd.DataFrame(dict(date=dates,datadate=dates,gvkey='001',iid='01',tpci='0',exchg=194,curcdd='GBP',
                        prccd=100.,qunit=1.,ajexdi=1.,cshoc=1000.,trfd=1.,secstat='I'))
    base,_=normalize(d,0);stress,_=normalize(d,-1)
    assert base.iloc[-1].is_exit and stress.iloc[-1].ret_hold==-1
    assert base.iloc[-1].ret_hold==0
    np.testing.assert_array_equal(base.ret_total.iloc[:-1],stress.ret_total.iloc[:-1])
