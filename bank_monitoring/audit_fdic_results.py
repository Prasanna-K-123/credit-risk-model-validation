"""Descriptive audit of frozen predictions; no fitting or model selection.

The 2022--2025 subgroup is explicitly post hoc and must not be presented as
another untouched test. This audit never modifies the registered model.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REF = ROOT / 'reference/fdic_temporal'


def audit():
    summary = json.loads((REF / 'summary.json').read_text())
    raw = REF / 'test_predictions.csv'
    if hashlib.sha256(raw.read_bytes()).hexdigest() != summary['test_predictions_sha256']:
        raise ValueError('Frozen prediction bytes changed')
    df = pd.read_csv(raw, float_precision='round_trip')
    cohort = pd.read_csv(REF / 'cohort_diagnostics.csv')
    if len(df) != summary['population']['test']['rows'] or int(df.failure.sum()) != summary['population']['test']['failure_events']:
        raise ValueError('Final population count differs from frozen summary')
    failures = df.loc[df.failure.eq(1), ['CERT', 'prediction_date', 'failure_date']].copy()
    result = {'scope': 'Descriptive audit after the registered final evaluation; no refit, tuning or new untouched test.',
              'late_group': 'Post hoc prediction dates 2022-04-01 through 2025-04-01, motivated by observed annual diagnostics.',
              'models': {}}
    for name, metrics in summary['test_metrics'].items():
        p = df['p_' + name]
        monitor = p.ge(metrics['threshold'])
        if int(monitor.sum()) != metrics['test_monitor_count'] or int(df.loc[monitor, 'failure'].sum()) != metrics['test_caught_failures']:
            raise ValueError('Frozen monitoring count mismatch')
        ranked = np.zeros(len(df), dtype=bool)
        annual = []
        for when, group in df.groupby('prediction_date', sort=True):
            scores = p.loc[group.index].to_numpy()
            capacity = int(np.ceil(0.01 * len(group)))
            indices = group.index.to_numpy()[np.lexsort((group.CERT.to_numpy(), -scores))[:capacity]]
            ranked[indices] = True
            y = group.failure.to_numpy()
            caught = int(df.loc[indices, 'failure'].sum())
            saved = cohort.loc[cohort.model.eq(name) & cohort.prediction_date.eq(when)]
            if len(saved) != 1 or int(saved.iloc[0].captured_failures_at_capacity) != caught or int(saved.iloc[0].review_capacity) != capacity:
                raise ValueError('Annual capacity diagnostic mismatch')
            annual.append({'prediction_date': when, 'rows': len(group), 'failures': int(y.sum()),
                           'expected_failure_count': float(scores.sum()), 'monitor_count': int(monitor.loc[group.index].sum()),
                           'caught_by_frozen_policy': int(df.loc[group.index[monitor.loc[group.index]], 'failure'].sum()),
                           'capacity': capacity, 'caught_at_capacity': caught})
        late = df.prediction_date.ge('2022-04-01')
        result['models'][name] = {'expected_failure_count': float(p.sum()), 'observed_failure_count': int(df.failure.sum()),
            'policy_monitor_count': int(monitor.sum()), 'policy_caught': int(df.loc[monitor, 'failure'].sum()),
            'policy_false_positives': int((monitor & df.failure.eq(0)).sum()),
            'policy_precision': float(df.loc[monitor, 'failure'].mean()) if monitor.any() else None,
            'annual_capacity_total': int(ranked.sum()), 'capacity_caught_total': int(df.loc[ranked, 'failure'].sum()),
            'late_posthoc': {'rows': int(late.sum()), 'failures': int(df.loc[late, 'failure'].sum()),
                'expected_failure_count': float(p.loc[late].sum()), 'policy_monitor_count': int((monitor & late).sum()),
                'policy_caught': int(df.loc[monitor & late, 'failure'].sum()), 'capacity_caught': int(df.loc[ranked & late, 'failure'].sum())},
            'annual': annual}
        failures['p_' + name] = p.loc[failures.index]
        failures['monitor_' + name] = monitor.loc[failures.index]
        failures['top_1pct_' + name] = ranked[failures.index]
    return result, failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result, failures = audit()
    audit_path, case_path = REF / 'descriptive_audit.json', REF / 'failure_cases.csv'
    if args.verify:
        if result != json.loads(audit_path.read_text()):
            raise ValueError('Descriptive audit changed')
        saved = pd.read_csv(case_path, float_precision='round_trip')
        if not failures.reset_index(drop=True).equals(saved):
            raise ValueError('All-failure case audit changed')
        print('PASS: all failure cases, yearly capacity, frozen policy counts and post-hoc diagnostics.')
        return
    if audit_path.exists() or case_path.exists():
        raise ValueError('Descriptive evidence already exists; use --verify')
    audit_path.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    failures.to_csv(case_path, index=False, float_format='%.17g')
    print('Saved descriptive audit without fitting or changing the registered comparison.')


if __name__ == '__main__':
    main()
