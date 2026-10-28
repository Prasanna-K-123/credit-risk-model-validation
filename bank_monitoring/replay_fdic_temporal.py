"""Verify release bytes, restore the compressed CSV, and replay locked fits.

Packaging was added after the first evaluation solely to keep the original
10,432,670-byte prediction CSV compact in Git. The estimator and protocol
remain at the source freeze recorded in artifact_manifest.json.
"""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REF = ROOT / 'reference/fdic_temporal'


def validate_files(entries):
    for entry in entries:
        path = (ROOT / entry['path']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError('Missing or invalid release path')
        data = path.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Release hash/byte mismatch: ' + entry['path'])


def main():
    manifest = json.loads((REF / 'artifact_manifest.json').read_text())
    validate_files(manifest['frozen_source'])
    validate_files(manifest['packaging_source'])
    validate_files(manifest['artifacts'])
    item = manifest['prediction_csv']
    path = (ROOT / item['path']).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Invalid prediction path')
    if not path.exists():
        data = gzip.decompress((ROOT / item['compressed_path']).read_bytes())
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Compressed prediction content differs from first evaluation')
        with path.open('xb') as handle:
            handle.write(data)
    validate_files([item])
    subprocess.run([sys.executable, str(ROOT / 'benchmark_fdic_temporal.py'), '--verify'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / 'audit_fdic_results.py'), '--verify'], cwd=ROOT, check=True)
    validate_files([item])
    print('PASS: release hashes, original CSV bytes, frozen estimator replay and complete descriptive audit.')


if __name__ == '__main__':
    main()
