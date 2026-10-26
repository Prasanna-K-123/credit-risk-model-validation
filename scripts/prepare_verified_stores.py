"""Rebuild or verify private SQL caches against pinned input bytes.

This additive entrypoint leaves the original frozen scientific methods unchanged.
A cache is reusable only when this entrypoint recorded its digest immediately
following fresh ingestion. A manifest is an integrity receipt, not authentication
against a malicious party who can edit both the cache and its receipt.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
YEARS = (2012, 2013, 2015, 2016, 2018, 2021)
METHODS = ("scripts/ingest_audit.py", "src/mortgage_risk/schema.py")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def method_hashes(root: Path) -> dict:
    frozen = json.loads((root / "reports/prefit_manifest.json").read_text(encoding="utf-8"))
    current = {name: sha256(root / name) for name in METHODS}
    if any(current[name] != frozen["method_files"][name] for name in METHODS):
        raise ValueError("Frozen ingestion method changed; use a separately reviewed release.")
    return current


def attest(database: Path, source_sha256: str, methods: dict, audit: dict) -> dict:
    """Called only after this process launches successful fresh ingestion."""
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Fresh SQLite integrity check failed.")
        counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("origination", "performance")}
    if any(counts[table] != audit[table]["rows"] for table in counts):
        raise ValueError("Fresh database row counts disagree with the ingestion audit.")
    return {"source_sha256": source_sha256, "method_sha256": methods,
            "database_sha256": sha256(database), "database_bytes": database.stat().st_size,
            "row_counts": counts, "fresh_ingestion_then_sqlite_check": True}


def verify_attestation(database: Path, record: dict, source_sha256: str, methods: dict) -> None:
    if (record.get("source_sha256") != source_sha256
            or record.get("method_sha256") != methods
            or record.get("fresh_ingestion_then_sqlite_check") is not True):
        raise ValueError("Cache provenance does not match the pinned input and ingestion method.")
    if (not database.is_file() or database.stat().st_size != record.get("database_bytes")
            or sha256(database) != record.get("database_sha256")):
        raise ValueError("SQL cache bytes changed or are missing; use --rebuild in a clean working copy.")


def prepare(root: Path, rebuild: bool = False, verify_only: bool = False) -> dict:
    if rebuild and verify_only:
        raise ValueError("Choose rebuilding or verification, not both.")
    if not verify_only and (root / "artifacts/training_started.json").exists():
        raise RuntimeError("Fitting has started here; rebuild only in a clean working copy.")
    methods = method_hashes(root)
    receipt_path = root / "data/processed/cache_attestation.json"
    prior = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {"caches": {}}
    records, statuses = {}, []
    for year in YEARS:
        intake = json.loads((root / f"source_intake/reports/source_{year}.json").read_text(encoding="utf-8"))
        raw = root / f"data/raw/sample_{year}.zip"
        source_sha = sha256(raw)
        if source_sha != intake["zip_sha256"]:
            raise ValueError(f"Pinned source bytes changed: {raw.name}")
        database = root / f"data/processed/sample_{year}.sqlite"
        record = prior["caches"].get(str(year))
        if not rebuild and record is not None:
            verify_attestation(database, record, source_sha, methods)
            records[str(year)] = record
            statuses.append({"year": year, "status": "cache_digest_verified"})
            continue
        if verify_only or (database.exists() and not rebuild):
            raise ValueError(f"No trusted cache receipt for {year}; run --rebuild before fitting.")
        subprocess.run([sys.executable, str(root / "scripts/ingest_audit.py"),
                        "--zip", str(raw), "--year", str(year)],
                       cwd=root, check=True)
        audit = json.loads((root / f"reports/data_audit_{year}.json").read_text(encoding="utf-8"))
        if (audit["source"]["sha256"] != source_sha
                or audit["origination"]["sha256"] != intake["members"]["orig"]["sha256"]
                or audit["performance"]["sha256"] != intake["members"]["perf"]["sha256"]):
            raise ValueError("Fresh ingestion disagrees with the pinned ZIP/member bytes.")
        records[str(year)] = attest(database, source_sha, methods, audit)
        statuses.append({"year": year, "status": "fresh_ingestion_and_cache_digest_recorded"})
    output = {"format_version": 1, "caches": records,
              "scope": "Private generated-cache integrity; no change to scientific models or labels."}
    if not verify_only:
        receipt_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"passed": True, "verify_only": verify_only, "stores": statuses}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true", help="Regenerate all six private caches from the pinned ZIPs.")
    parser.add_argument("--verify-only", action="store_true", help="Read-only verification of existing cache receipts and raw inputs.")
    args = parser.parse_args()
    print(json.dumps(prepare(ROOT, args.rebuild, args.verify_only), indent=2))
