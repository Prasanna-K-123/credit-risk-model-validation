"""Frozen retrospective temporal experiment: snapshot build, actual fitting and replay."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import time
import warnings

import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler

from src.fdic_temporal import (
    FEATURES, ROLES, FrozenScoreMetrics, MonotoneCalibrator, assert_temporal_partitions,
    build_panel, paired_cluster_uncertainty, policy_threshold, sha256,
)

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT/'reference/fdic_temporal'


def jsonable(value):
    if isinstance(value, dict):
        return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float,np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(data),indent=2,allow_nan=False)+'\n')


def protocol():
    j = json.loads((REFERENCE/'PROTOCOL.json').read_text())
    if tuple(j['features']) != FEATURES:
        raise ValueError("Code and registered predictor whitelist disagree")
    return j


def build_snapshot(raw: Path):
    receipt = json.loads((raw/'collection_receipt.json').read_text())
    p = protocol()
    if receipt['protocol_sha256'] != sha256(REFERENCE/'PROTOCOL.json'):
        raise ValueError("Collection used a different protocol")
    for v in receipt['combined'].values():
        if sha256(ROOT/v['path']) != v['sha256']:
            raise ValueError("Combined raw source integrity failure")
    data = {n:json.loads((raw/f'{n}.json').read_text()) for n in ['financials','institutions','failures']}
    panel, audit = build_panel(**data, protocol=p)
    pins = []
    directory = REFERENCE/'source_financials'
    directory.mkdir(parents=True, exist_ok=True)
    financial = pd.DataFrame(data['financials'])
    for reporting,group in financial.groupby('REPDTE',sort=True):
        dest = directory/(str(reporting)[:4]+'.json.gz')
        # Recover exact source objects, preserving nulls, encodings and numeric values.
        source_rows = [r for r in data['financials'] if str(r['REPDTE']) == str(reporting)]
        payload = json.dumps(source_rows,separators=(',',':'),allow_nan=False).encode()
        dest.write_bytes(gzip.compress(payload,mtime=0))
        pins.append({'kind':'financials','path':str(dest.relative_to(ROOT)),'bytes':dest.stat().st_size,'sha256':sha256(dest),'rows':len(source_rows)})
    for name in ['institutions','failures']:
        dest = REFERENCE/(name+'.json.gz')
        payload = json.dumps(data[name],separators=(',',':'),allow_nan=False).encode()
        dest.write_bytes(gzip.compress(payload,mtime=0))
        pins.append({'kind':name,'path':str(dest.relative_to(ROOT)),'bytes':dest.stat().st_size,'sha256':sha256(dest),'rows':len(data[name])})
    write_json(REFERENCE/'source_snapshot.json',{'protocol_sha256':sha256(REFERENCE/'PROTOCOL.json'),'source_extracts':pins,'source_receipt':receipt,
        'extract': 'Compact selected original source objects; every predictor/label is rebuilt from these. Full API response envelopes/schemas are not redistributed. These are current historical values, not original-release vintages.'})
    write_json(REFERENCE/'eligibility_audit.json',audit)
    print('Pinned compact source objects:',len(panel),'eligible rows;',len(pins),'source extracts. No prediction scores calculated.',flush=True)


def load_panel():
    p = protocol()
    snapshot = json.loads((REFERENCE/'source_snapshot.json').read_text())
    if snapshot['protocol_sha256'] != sha256(REFERENCE/'PROTOCOL.json'):
        raise ValueError("Pinned panel/protocol mismatch")
    data = {name:[] for name in ['financials','institutions','failures']}
    for v in snapshot['source_extracts']:
        path = ROOT/v['path']
        if sha256(path) != v['sha256'] or path.stat().st_size != v['bytes']:
            raise ValueError("Pinned compact-source hash/byte mismatch")
        part = json.loads(gzip.decompress(path.read_bytes()))
        if len(part) != v['rows']:
            raise ValueError("Pinned source count mismatch")
        data[v['kind']].extend(part)
    frame,audit = build_panel(**data,protocol=p)
    if audit != json.loads((REFERENCE/'eligibility_audit.json').read_text()):
        raise ValueError('Rebuilt source eligibility, exclusions or failure coverage changed')
    if tuple(frame.columns[-len(FEATURES):]) != FEATURES:
        raise ValueError("Pinned predictor schema mismatch")
    assert_temporal_partitions(frame)
    years = pd.to_datetime(frame.report_date).dt.year
    for role in ROLES:
        if not years[frame.role == role].isin(p['report_years'][role]).all():
            raise ValueError("Row entered an unregistered temporal partition")
    return frame,p


def fit_without_convergence_warning(model,x,y):
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter('always',ConvergenceWarning)
        model.fit(x,y)
    if any(issubclass(w.category,ConvergenceWarning) for w in seen):
        raise ValueError("Registered model did not converge")
    return model


def full_logistic(c,p):
    q = p['models']['logistic']
    return make_pipeline(SimpleImputer(strategy='median'),RobustScaler(),LogisticRegression(C=c,solver=q['solver'],max_iter=q['max_iter'],tol=q['tol'],random_state=p['seed']))


def cohort_diagnostics(test, predictions, thresholds, fn_weight):
    rows = []
    for when, g in test.groupby('prediction_date',sort=True):
        idx = g.index.to_numpy()
        y = g.failure.to_numpy()
        for name,values in predictions.items():
            probs = values[idx]
            m = FrozenScoreMetrics(y,probs,thresholds[name],fn_weight).evaluate()
            capacity = int(np.ceil(0.01*len(g)))
            # A deterministic public identifier breaks exact score ties, never learns a rule.
            order = np.lexsort((g.CERT.to_numpy(),-probs))
            caught = int(y[order[:capacity]].sum())
            rows.append({'prediction_date':when,'model':name,'rows':len(g),'failures':int(y.sum()),'nonfailure_exits':int(g.nonfailure_exit.sum()),
                'review_capacity':capacity,'captured_failures_at_capacity':caught,'precision_at_capacity':caught/capacity,
                'recall_at_capacity':caught/y.sum() if y.sum() else None,**m})
    return pd.DataFrame(rows)


def run():
    started = time.perf_counter()
    frame,p = load_panel()
    parts = {r:frame.loc[frame.role == r].copy().reset_index(drop=True) for r in ROLES}
    for role in ['development','selection','calibration','policy']:
        if set(parts[role].failure.unique()) != {0,1}:
            raise ValueError(f'{role} has no usable two-class outcome sample; do not silently change years')
    train,select = parts['development'],parts['selection']
    x,y = train[list(FEATURES)],train.failure.to_numpy()
    if x.notna().sum().eq(0).any():
        raise ValueError('Development feature is entirely missing')
    valx,valy = select[list(FEATURES)],select.failure.to_numpy()
    trials, chosen, models = [],{},{}
    for family in ['logistic','hist_gradient_boosting']:
        if family == 'logistic':
            candidates = p['models'][family]['C_candidates']
        else:
            candidates = p['models'][family]['leaf_candidates']
        scored = []
        for index,choice in enumerate(candidates):
            t = time.perf_counter()
            if family == 'logistic':
                model = full_logistic(choice,p)
            else:
                q = p['models'][family]
                model = HistGradientBoostingClassifier(max_leaf_nodes=choice,max_iter=q['max_iter'],learning_rate=q['learning_rate'],
                    min_samples_leaf=q['min_samples_leaf'],max_bins=q['max_bins'],l2_regularization=q['l2_regularization'],early_stopping=False,random_state=p['seed'])
            fit_without_convergence_warning(model,x,y)
            probs = model.predict_proba(valx)[:,1]
            loss = FrozenScoreMetrics(valy,probs,0.5).evaluate()['log_loss']
            trials.append({'family':family,'candidate':choice,'development_rows':len(train),'selection_rows':len(select),'selection_log_loss':loss,'fit_seconds':time.perf_counter()-t})
            scored.append((loss,index,choice,model))
            print('Fitted registered',family,'candidate',choice,'on development only.',flush=True)
        _,_,choice,model = min(scored,key=lambda v:(v[0],v[1]))
        chosen[family]=choice
        models[family]=model
    capital = fit_without_convergence_warning(full_logistic(1.0,p),train[['equity_to_assets']],y)
    probability = float(y.mean())
    predictors = {'constant':lambda df:np.full(len(df),probability), 'capital_only':lambda df:capital.predict_proba(df[['equity_to_assets']])[:,1]}
    calibration = parts['calibration']
    calibrators = {}
    for family,model in models.items():
        predictors[family+'_raw'] = lambda df,model=model:model.predict_proba(df[list(FEATURES)])[:,1]
        raw = predictors[family+'_raw'](calibration)
        mapping = MonotoneCalibrator.fit(raw,calibration.failure.to_numpy())
        calibrators[family]=mapping
        predictors[family+'_calibrated'] = lambda df,model=model,mapping=mapping:mapping.predict(model.predict_proba(df[list(FEATURES)])[:,1])
    print('Selected models and separate-year calibration fixed; final scores begin now.',flush=True)
    policy = parts['policy'];test = parts['test'];fn_weight = p['policy']['false_negative_weight']
    thresholds,policy_costs = {},{}
    for name,predict in predictors.items():
        threshold,cost = policy_threshold(policy.failure.to_numpy(),predict(policy),fn_weight)
        thresholds[name],policy_costs[name] = threshold,cost
    predictions = {name:predict(test) for name,predict in predictors.items()}
    evaluators = {name:FrozenScoreMetrics(test.failure.to_numpy(),values,thresholds[name],fn_weight) for name,values in predictions.items()}
    metrics = {}
    for name,e in evaluators.items():
        decision = predictions[name] >= thresholds[name]
        metrics[name] = {**e.evaluate(),'threshold':thresholds[name],'policy_selection_cost':policy_costs[name],
            'test_monitor_count':int(decision.sum()),'test_caught_failures':int(test.failure.to_numpy()[decision].sum()),
            'test_missed_failures':int(test.failure.sum()-test.failure.to_numpy()[decision].sum())}
    paired = {}
    for unit in p['uncertainty']['units']:
        paired[unit] = paired_cluster_uncertainty(test,evaluators['hist_gradient_boosting_calibrated'],evaluators['logistic_calibrated'],unit,p['uncertainty']['replicates'],p['seed'])
    out = test[['CERT','report_date','prediction_date','horizon_end','failure','failure_date','nonfailure_exit']].copy()
    for name,values in predictions.items():out['p_'+name]=values
    cohorts = cohort_diagnostics(test,predictions,thresholds,fn_weight)
    summary = {'protocol_sha256':sha256(REFERENCE/'PROTOCOL.json'),'source_snapshot_sha256':sha256(REFERENCE/'source_snapshot.json'),
        'population':{r:{'rows':len(df),'certificates':int(df.CERT.nunique()),'failure_events':int(df.failure.sum()),'nonfailure_exits':int(df.nonfailure_exit.sum()),'first_prediction':df.prediction_date.min(),'last_prediction':df.prediction_date.max(),'latest_horizon':df.horizon_end.max()} for r,df in parts.items()},
        'development_rows_equal_for_full_models':True,'registered_candidates_per_full_model':3,'selected':chosen,'calibration':{k:asdict(v) for k,v in calibrators.items()},
        'test_metrics':metrics,'paired_uncertainty':paired,'test_nonfailure_monitor_none_cost_per_row':fn_weight*float(test.failure.mean()),'test_monitor_all_cost_per_row':1-float(test.failure.mean()),
        'test_missing_fraction':test[list(FEATURES)].isna().mean().to_dict(),'test_prevalence':float(test.failure.mean()),'development_prevalence':probability,
        'limitations':['Current historical revisions, not original information vintages','Assumed April 1 availability, not verified publication time','Institutional failure with competing nonfailure exits, not borrower PD','Annual observation cadence; rare later-regime failures','Repeated certificates across roles are intentional, not unseen-bank validation','Bank and annual-cohort bootstrap are separate dependence sensitivities','Fixed small candidate grid; not a claim of global model optimality','Illustrative monitoring weights/capacity, no observed financial benefit'],
        'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,'seconds':time.perf_counter()-started,'api_cash_spend':0,'cpu_electricity_unpriced':True}}
    return out,cohorts,pd.DataFrame(trials),jsonable(summary)


def verify(out,cohorts,trials,summary):
    saved = pd.read_csv(REFERENCE/'test_predictions.csv',float_precision='round_trip')
    if not out[['CERT','report_date','prediction_date','failure']].equals(saved[['CERT','report_date','prediction_date','failure']]):
        raise ValueError('Frozen prediction rows/labels changed')
    columns = [c for c in out if c.startswith('p_')]
    max_error = float(np.max(np.abs(out[columns].to_numpy()-saved[columns].to_numpy())))
    if not np.allclose(out[columns],saved[columns],rtol=1e-8,atol=1e-9):
        raise ValueError('Frozen fitted probabilities did not reproduce')
    old = json.loads((REFERENCE/'summary.json').read_text())
    for key in ['protocol_sha256','source_snapshot_sha256','population','selected','test_missing_fraction']:
        if summary[key] != old[key]:raise ValueError(f'Frozen {key} changed')
    for name,metrics in summary['test_metrics'].items():
        for key,value in metrics.items():
            prior = old['test_metrics'][name][key]
            if not np.isclose(value,prior,rtol=1e-8,atol=1e-9):raise ValueError(f'Metric changed: {name}/{key}')
    for unit in summary['paired_uncertainty']:
        for key,v in summary['paired_uncertainty'][unit]['metrics'].items():
            prior=old['paired_uncertainty'][unit]['metrics'][key]
            if v['valid_replicates']!=prior['valid_replicates'] or not np.allclose(v['percentile_95'],prior['percentile_95'],rtol=1e-8,atol=1e-9):
                raise ValueError('Frozen dependence sensitivity changed')
    print('PASS: pinned source/panel, chronology, selected fits, full predictions, policies, metrics and paired resampling replay. Max probability error',max_error,flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-snapshot',type=Path)
    parser.add_argument('--verify',action='store_true')
    args = parser.parse_args()
    if args.build_snapshot:
        build_snapshot(args.build_snapshot.resolve());return
    out,cohorts,trials,summary = run()
    if args.verify:
        verify(out,cohorts,trials,summary);return
    if (REFERENCE/'summary.json').exists():
        raise ValueError('Evidence exists; use --verify instead of overwriting frozen results')
    out.to_csv(REFERENCE/'test_predictions.csv',index=False,float_format='%.17g')
    cohorts.to_csv(REFERENCE/'cohort_diagnostics.csv',index=False,float_format='%.17g')
    trials.to_csv(REFERENCE/'selection_trials.csv',index=False,float_format='%.17g')
    summary['test_predictions_sha256']=sha256(REFERENCE/'test_predictions.csv')
    write_json(REFERENCE/'summary.json',summary)
    print('Completed actual registered retrospective temporal experiment; all final rows retained.',flush=True)


if __name__ == '__main__':main()
