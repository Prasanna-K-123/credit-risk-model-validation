"""Ingest the six already-audited uploads with two independent SQL workers."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def one(year):
    raw = ROOT / 'data/raw' / f'sample_{year}.zip'
    intake = json.loads((ROOT / f'source_intake/reports/source_{year}.json').read_text())
    with raw.open('rb') as f:
        if hashlib.file_digest(f, 'sha256').hexdigest() != intake['zip_sha256']:
            raise ValueError('Supplied source changed')
    report = ROOT / f'reports/data_audit_{year}.json'
    database = ROOT / f'data/processed/sample_{year}.sqlite'
    if report.exists() and database.exists():
        d = json.loads(report.read_text())
        if d['source']['sha256'] == intake['zip_sha256'] and d['validation']['sqlite_integrity'] == 'ok':
            return {'year': year, 'status': 'existing audited SQL store'}
    logs = ROOT / 'private_logs'
    logs.mkdir(exist_ok=True)
    with (logs / f'ingest_{year}.log').open('w') as log:
        subprocess.run([sys.executable, str(ROOT / 'scripts/ingest_audit.py'),
                        '--zip', str(raw), '--year', str(year)], stdout=log, stderr=subprocess.STDOUT, check=True)
    d = json.loads(report.read_text())
    if (d['origination']['sha256'] != intake['members']['orig']['sha256']
            or d['performance']['sha256'] != intake['members']['perf']['sha256']):
        raise ValueError('SQL ingestion and independent ZIP intake disagree')
    return {'year': year, 'status': 'SQL store built; member hashes agree',
            'monthly_rows': d['performance']['rows']}


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, y) for y in (2012, 2013, 2015, 2016, 2018, 2021)]
        for f in concurrent.futures.as_completed(futures):
            print(json.dumps(f.result()), flush=True)
