from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

from src.fdic_temporal import (
    FEATURES, FrozenScoreMetrics, MonotoneCalibrator, assert_temporal_partitions,
    bank_registry, build_panel, failure_registry, financial_features,
    paired_cluster_uncertainty, policy_threshold, source_date,
)

PROTOCOL = json.loads((Path(__file__).resolve().parents[1]/'reference/fdic_temporal/PROTOCOL.json').read_text())


def fixture_sources():
    rows = []
    for year in [1992,2007,2010,2012,2014]:
        for cert in range(1,6):
            rows.append({'CERT':cert,'REPDTE':str(year)+'1231','ASSET':100.0,'EQ':10.0,'LNLSNET':60.0,'DEP':80.0,'CHBAL':5.0,'SC':25.0,'NPERFV':2.0,'ROA':1.0,'NIMY':3.0})
    banks = [{'CERT':c,'ACTIVE':1 if c==1 else 0,'ENDEFYMD':end,'ESTYMD':'01/01/1990','INSDATE':'01/01/1990'} for c,end in [(1,'12/31/9999'),(2,'05/02/2015'),(3,'05/01/2015'),(4,'03/30/2015'),(5,'04/01/2015')]]
    events = [{'CERT':2,'FAILDATE':'05/02/2015','RESTYPE':'FAILURE'},{'CERT':5,'FAILDATE':'04/01/2015','RESTYPE':'Failure'}]
    return rows,banks,events


@pytest.mark.parametrize('value', ['99991231','12/31/9999',0,None,'00000000'])
def test_open_and_missing_dates_are_not_literal_dates(value):
    assert source_date(value) is None


def test_dates_and_unsupported_ambiguous_encoding():
    assert source_date(20001231.0)==date(2000,12,31)
    assert source_date('03/01/2000')==date(2000,3,1)
    with pytest.raises(ValueError):source_date('31/12/2000')


def test_source_units_and_predictor_whitelist():
    raw,_,_ = fixture_sources()
    frame=pd.DataFrame(raw[:1]);base=financial_features(frame)
    assert tuple(base.columns)==FEATURES
    assert base.iloc[0].equity_to_assets==0.1
    assert base.iloc[0].nonperforming_assets_fraction==0.02
    assert base.iloc[0].return_on_assets_fraction==0.01
    assert base.iloc[0].net_interest_margin_fraction==0.03
    frame['CERT']=999;frame['ACTIVE']=0;frame['FAILDATE']='tomorrow';frame['failure']=1
    pd.testing.assert_frame_equal(base,financial_features(frame))
    with pytest.raises(ValueError):financial_features(frame.drop(columns='NIMY'))
    frame['ASSET']=0
    with pytest.raises(ValueError):financial_features(frame)


def test_terminal_events_competing_exits_and_at_risk_population():
    raw,banks,events=fixture_sources();panel,audit=build_panel(raw,banks,events,PROTOCOL)
    test=panel[panel.role=='test'].set_index('CERT')
    assert set(test.index)=={1,2,3}
    assert test.loc[2,'failure']==1
    assert test.loc[3,'failure']==0 and test.loc[3,'nonfailure_exit']==1
    assert audit['exclusions']['institution_inactive_at_prediction']==1
    assert audit['exclusions']['failure_already_occurred']==1
    # A later closure does not discard the same institution's earlier healthy rows.
    assert 3 in set(panel.loc[panel.role=='development','CERT'])
    assert test.loc[1,'prediction_date']=='2015-04-01'
    assert test.loc[1,'horizon_end']=='2016-04-01'


def test_failure_at_horizon_is_included_but_prediction_day_failure_is_not():
    raw,banks,events=fixture_sources();banks[1]['ENDEFYMD']='04/01/2016';events[0]['FAILDATE']='04/01/2016'
    panel,_=build_panel(raw,banks,events,PROTOCOL)
    assert panel.loc[(panel.role=='test')&(panel.CERT==2),'failure'].iloc[0]==1
    assert not ((panel.role=='test')&(panel.CERT==5)).any()


def test_assistance_not_failure_and_duplicate_event_rejected():
    _,_,events=fixture_sources()
    events.append({'CERT':3,'FAILDATE':'05/01/2015','RESTYPE':'Assistance'})
    registry=failure_registry(events,date(1993,4,1));assert 3 not in registry
    with pytest.raises(ValueError):failure_registry(events+[events[0]],date(1993,4,1))


def test_duplicate_source_and_unknown_inactive_date_cannot_be_silently_relabelled():
    raw,banks,events=fixture_sources()
    with pytest.raises(ValueError):build_panel(raw+[raw[0]],banks,events,PROTOCOL)
    banks[2]['ENDEFYMD']=None
    panel,audit=build_panel(raw,banks,events,PROTOCOL)
    assert 3 not in set(panel.CERT)
    assert audit['exclusions']['unknown_inactive_date']==5
    with pytest.raises(ValueError):bank_registry(banks+[banks[0]])
    banks[0]['ACTIVE']=1.7
    with pytest.raises(ValueError):bank_registry(banks)


def test_inconsistent_failure_after_inactive_date_has_explicit_exclusion():
    raw,banks,events=fixture_sources();banks[1]['ENDEFYMD']='05/01/2015'
    panel,audit=build_panel(raw,banks,events,PROTOCOL)
    assert 2 not in set(panel.CERT)
    assert audit['exclusions']['failure_after_registered_inactive_date']==5


def test_immature_outcomes_and_overlapping_label_horizons_rejected():
    raw,banks,events=fixture_sources();p=deepcopy(PROTOCOL);p['outcome_cutoff']='2015-12-31'
    with pytest.raises(ValueError):build_panel(raw,banks,events,p)
    panel,_=build_panel(raw,banks,events,PROTOCOL)
    panel.loc[panel.role=='calibration','horizon_end']=panel.loc[panel.role=='policy','prediction_date'].iloc[0]
    with pytest.raises(ValueError):assert_temporal_partitions(panel)


def test_weighted_ties_match_independent_library_metrics():
    y=np.array([0,1,0,1,1,0]);p=np.array([.1,.7,.7,.8,.7,.1]);w=np.array([1,2,3,2,1,4])
    metrics=FrozenScoreMetrics(y,p,.5).evaluate(w)
    assert metrics['auc']==pytest.approx(roc_auc_score(y,p,sample_weight=w))
    assert metrics['average_precision']==pytest.approx(average_precision_score(y,p,sample_weight=w))
    assert metrics['brier']==pytest.approx(np.average((y-p)**2,weights=w))
    assert metrics['log_loss']==pytest.approx(np.average(-(y*np.log(p)+(1-y)*np.log1p(-p)),weights=w))


def test_metrics_refuse_invalid_probabilities_and_handle_one_class():
    with pytest.raises(ValueError):FrozenScoreMetrics([0,1],[.2,np.nan],.5)
    with pytest.raises(ValueError):FrozenScoreMetrics([0,1],[.2,1.1],.5)
    one=FrozenScoreMetrics([0,0],[.2,.3],.5).evaluate()
    assert np.isnan(one['auc']) and np.isnan(one['average_precision'])
    assert np.isfinite(one['brier'])


def test_illustrative_cost_ties_choose_less_monitoring():
    threshold,cost=policy_threshold([1,0],[.5,.5],1.0)
    assert threshold>1 and cost==1


def test_calibration_is_monotone_and_requires_two_classes():
    p=np.array([.01,.05,.1,.2,.4,.8]);y=np.array([0,0,1,0,1,1])
    mapping=MonotoneCalibrator.fit(p,y)
    assert mapping.slope>=0
    assert (np.diff(mapping.predict(p))>=0).all()
    with pytest.raises(ValueError):MonotoneCalibrator.fit(p,np.zeros(6))


def test_cluster_bootstrap_reproducible_and_identity_difference_degenerate():
    panel=pd.DataFrame({'CERT':[1,1,2,2,3,3],'prediction_date':['a','b']*3})
    e=FrozenScoreMetrics([0,0,0,1,1,0],[.1,.2,.3,.8,.7,.4],.5)
    first=paired_cluster_uncertainty(panel,e,e,'CERT',20,77)
    second=paired_cluster_uncertainty(panel,e,e,'CERT',20,77)
    assert first==second and first['groups']==3
    assert first['metrics']['brier']['percentile_95']==[0,0]
