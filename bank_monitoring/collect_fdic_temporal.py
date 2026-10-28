"""Capture a complete, attributable current FDIC snapshot; do not fit or score models."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
import time

from src.fdic_temporal import FINANCIAL_FIELDS, sha256

ROOT = Path(__file__).resolve().parent
PROTOCOL = ROOT/'reference/fdic_temporal/PROTOCOL.json'


def capture(endpoint, fields, directory, filters="", page_size=10000):
    directory.mkdir(parents=True, exist_ok=True)
    rows, receipts, index, total, offset = [], [], None, None, 0
    while total is None or offset < total:
        params = {"fields": ','.join(fields), "filters": filters, "limit": page_size, "offset": offset, "sort_by": "CERT", "sort_order": "ASC", "format": "json"}
        url = 'https://api.fdic.gov/banks/'+endpoint+'?'+urllib.parse.urlencode(params)
        dest = directory/f'{endpoint}_{offset:05d}.json'
        if not dest.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "Prasanna-K-FDIC-research/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as response:
                if response.status != 200:
                    raise ValueError("FDIC response was not successful")
                body = response.read()
            payload = json.loads(body)
            dest.write_bytes(body)
        else:
            payload = json.loads(dest.read_text())
        meta = payload['meta']
        if index is None:
            index = meta['index']
            total = int(meta['total'])
        if meta['index'] != index or int(meta['total']) != total:
            raise ValueError("Source changed during pagination; do not mix snapshots")
        page = [item['data'] for item in payload['data']]
        if not page and offset < total:
            raise ValueError("Premature empty API page")
        rows.extend(page)
        receipts.append({"path": str(dest.relative_to(ROOT)), "url": url, "bytes": dest.stat().st_size, "sha256": sha256(dest), "records": len(page)})
        offset += len(page)
        time.sleep(0.15)
    if len(rows) != total:
        raise ValueError("API total does not match captured row count")
    ids = [str(r['ID']) for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate API IDs across pagination")
    for field in fields:
        if not any(field in r for r in rows):
            raise ValueError(f"API silently omitted requested field {field}")
    return rows, {"endpoint": endpoint, "index": index, "records": total, "pages": receipts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'data/fdic_temporal')
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    years = sorted({y for v in protocol['report_years'].values() for y in v})
    folder = args.output.resolve()
    all_financials, financial_receipts = [], []
    for year in years:
        rows, receipt = capture('financials', FINANCIAL_FIELDS, folder/'raw'/str(year), f'REPDTE:{year}1231')
        all_financials.extend(rows)
        financial_receipts.append(receipt)
        print('Captured report-year', year, 'records', len(rows), flush=True)
    indexes = {json.dumps(r['index'], sort_keys=True) for r in financial_receipts}
    if len(indexes) != 1:
        raise ValueError("Annual financials do not share the same snapshot index")
    institutions, institution_receipt = capture('institutions', ('CERT','ACTIVE','ENDEFYMD','ESTYMD','INSDATE'), folder/'raw/institutions')
    failures, failure_receipt = capture('failures', ('CERT','FAILDATE','RESTYPE','FAILYR'), folder/'raw/failures')
    cutoff = datetime.fromisoformat(protocol['outcome_cutoff']+'T00:00:00+00:00')
    for receipt in financial_receipts+[institution_receipt,failure_receipt]:
        timestamp = datetime.fromisoformat(receipt['index']['createTimestamp'].replace('Z','+00:00'))
        if timestamp < cutoff:
            raise ValueError("Source snapshot predates the registered outcome cutoff")
    for name, records in [('financials',all_financials),('institutions',institutions),('failures',failures)]:
        p = folder/f'{name}.json'
        p.write_text(json.dumps(records, separators=(',',':'))+'\n')
    manifest = {"captured_utc": datetime.now(timezone.utc).isoformat(), "protocol_sha256": sha256(PROTOCOL), "financials": financial_receipts, "institutions": institution_receipt, "failures": failure_receipt,
                "combined": {name:{"path":str((folder/f'{name}.json').relative_to(ROOT)),"sha256":sha256(folder/f'{name}.json'),"bytes":(folder/f'{name}.json').stat().st_size} for name in ['financials','institutions','failures']},
                "scope": "Current historical-source snapshot, not an archive of values first released on each prediction date; raw bodies are not redistributed."}
    (folder/'collection_receipt.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Complete source capture; no models fitted or test scores calculated.',flush=True)


if __name__ == '__main__':
    main()

