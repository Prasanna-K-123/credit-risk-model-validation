"""Bounded parallel source caching; uses the locked collector without changing its contracts."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path

from collect_fdic_temporal import ROOT, PROTOCOL, capture
from src.fdic_temporal import FINANCIAL_FIELDS


def one(year):
    target=ROOT/'data/fdic_temporal/raw'/str(year)
    if target.exists():return year,'already owned by collector'
    staging=ROOT/'data/fdic_preload_staging'/str(year)
    rows,receipt=capture('financials',FINANCIAL_FIELDS,staging,f'REPDTE:{year}1231')
    target.parent.mkdir(parents=True,exist_ok=True)
    try:
        os.rename(staging,target)
        return year,f'atomically cached {len(rows)} rows'
    except OSError:
        if not target.exists():raise
        return year,'collector reached this year; its files preserved'


def main():
    p=json.loads(PROTOCOL.read_text())
    years=sorted({y for v in p['report_years'].values() for y in v})
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs=[pool.submit(one,y) for y in years if not (ROOT/'data/fdic_temporal/raw'/str(y)).exists()]
        for job in as_completed(jobs):
            year,status=job.result();print(year,status,flush=True)


if __name__=='__main__':main()
