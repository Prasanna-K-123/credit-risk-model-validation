"""Stream one official annual ZIP; audit every row and build a local SQL store.

Usage: python scripts/ingest_audit.py --zip /path/sample_2012.zip --year 2012
Raw records, identifiers and the SQLite database must never be committed.
The original ZIP is read without extraction or modification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mortgage_risk.schema import (ORIGINATION, PERFORMANCE, PERFORMANCE_STORED,
                                  PERFORMANCE_POSITIONS, month_index)

PINNED = {2012: "57b6b0281ee956dd1b8b4a7a24e4d3469fcbc8292fd7df981aa2a494f6a50220"}
ALLOWED_ZERO_CODES = {"", "01", "02", "03", "09", "15", "16", "96"}
ALLOWED_DELINQUENCY = {"RA", "XX"} | {f"{n:02d}" for n in range(100)}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rows(archive: zipfile.ZipFile, name: str, columns: list[str], result: dict):
    h = hashlib.sha256()
    missing = [0] * len(columns)
    count = 0
    with archive.open(name) as stream:
        for raw in stream:
            h.update(raw)
            values = raw.decode("utf-8-sig" if count == 0 else "utf-8").rstrip("\r\n").split("|")
            if len(values) != len(columns):
                raise ValueError(f"{name}: row {count + 1} has {len(values)} fields; expected {len(columns)}")
            count += 1
            for i, value in enumerate(values):
                missing[i] += value == ""
            yield values
    # Reaching EOF also invokes zipfile's CRC validation.
    result.update(rows=count, fields=len(columns), sha256=h.hexdigest(),
                  blank_counts=dict(zip(columns, missing)), crc_verified=True)


def finite_number(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite numeric value")
    return result


def audit(path: Path, year: int, output: Path) -> dict:
    source_hash = sha256(path)
    if year in PINNED and source_hash != PINNED[year]:
        raise ValueError("ZIP checksum differs from the audited source release; review before use")
    names = {"origination": f"sample_orig_{year}.txt", "performance": f"sample_perf_{year}.txt"}
    output.mkdir(parents=True, exist_ok=True)
    db_path = output / f"sample_{year}.sqlite"
    stage = output / f"sample_{year}.sqlite.partial"
    stage.unlink(missing_ok=True)
    conn = sqlite3.connect(stage)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-65536")
    orig_defs = [f'"{c}" TEXT NOT NULL' + (" PRIMARY KEY" if c == "loan_id" else "") for c in ORIGINATION]
    conn.execute("CREATE TABLE origination (" + ",".join(orig_defs) + ") WITHOUT ROWID")
    perf_defs = [f'"{c}" ' + ("INTEGER" if c in {"period", "loan_age", "remaining_term"} else "REAL" if c in {"current_upb", "current_rate", "non_interest_upb"} else "TEXT") for c in PERFORMANCE_STORED]
    conn.execute("CREATE TABLE performance (" + ",".join(perf_defs) + ", PRIMARY KEY (loan_id,period)) WITHOUT ROWID")
    report = {
        "source": {"filename": path.name, "year": year, "bytes": path.stat().st_size,
                   "sha256": source_hash, "received_date": datetime.now(timezone.utc).date().isoformat(),
                   "acquisition": "User-supplied official Clarity annual sample",
                   "provider_checksum_available": False,
                   "independent_provider_byte_match": False,
                   "resource_url": "https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset",
                   "layout": "July 2026 / Release 47; 31 origination and 35 performance fields"},
        "origination": {}, "performance": {}, "validation": {},
        "scope": "Source integrity and schema audit; no fitted model or held-out model evaluation",
    }
    ids = set()
    original_dates = Counter()
    missing_sentinels = Counter()
    sentinel_positions = {0: "9999", 5: "999", 6: "99", 8: "999", 9: "999", 11: "999", 22: "99", 30: "9999"}
    first_dates = []
    orig_insert = "INSERT INTO origination VALUES (" + ",".join("?" for _ in ORIGINATION) + ")"
    perf_insert = "INSERT INTO performance VALUES (" + ",".join("?" for _ in PERFORMANCE_STORED) + ")"
    anomalies = Counter()
    period_counts, delinquency_counts, zero_counts = Counter(), Counter(), Counter()
    terminal_loans = set()
    age_resets = 0
    previous_age = {}
    intervals = {}
    nonnegative_failures = Counter()
    numeric_failures = Counter()
    with zipfile.ZipFile(path) as archive:
        if set(archive.namelist()) != set(names.values()):
            raise ValueError("Unexpected ZIP members; review archive before ingestion")
        report["source"]["members"] = [{"name": i.filename, "bytes": i.file_size,
                "compressed_bytes": i.compress_size, "crc32": f"{i.CRC:08x}"} for i in archive.infolist()]
        batch = []
        for values in rows(archive, names["origination"], ORIGINATION, report["origination"]):
            loan_id = values[19]
            if not re.fullmatch(r"[FA]\d{2}Q[1-4]\d{7}", loan_id):
                raise ValueError("Unexpected loan identifier format")
            if loan_id in ids:
                raise ValueError("Duplicate origination loan identifier")
            if int(loan_id[1:3]) != year % 100:
                raise ValueError("Origination identifier year disagrees with archive year")
            ids.add(loan_id)
            month_index(values[1]); month_index(values[3])
            first_dates.append(int(values[1]))
            original_dates[loan_id[3:5]] += 1
            for i, sentinel in sentinel_positions.items():
                missing_sentinels[ORIGINATION[i]] += values[i] == sentinel
            for i in [0, 5, 6, 8, 9, 10, 11, 12, 21, 22, 30]:
                try:
                    finite_number(values[i])
                except ValueError:
                    numeric_failures[ORIGINATION[i]] += 1
            batch.append(values)
        conn.executemany(orig_insert, batch)
        report["origination"].update(unique_loans=len(ids), quarter_counts=dict(sorted(original_dates.items())),
             first_payment_min=min(first_dates), first_payment_max=max(first_dates),
             sentinel_missing_counts=dict(missing_sentinels), numeric_parse_failures=dict(numeric_failures))
        batch = []
        for values in rows(archive, names["performance"], PERFORMANCE, report["performance"]):
            loan_id, period = values[0], int(values[1])
            if loan_id not in ids:
                raise ValueError("Performance loan absent from origination file")
            month = month_index(period)
            if period > 202603:
                raise ValueError("Performance exceeds declared Release 47 cutoff")
            if values[3] not in ALLOWED_DELINQUENCY:
                raise ValueError("Unrecognized delinquency code")
            if values[8] not in ALLOWED_ZERO_CODES:
                raise ValueError("Unrecognized exit code")
            period_counts[period] += 1
            delinquency_counts[values[3]] += 1
            zero_counts[values[8] or "blank"] += 1
            if loan_id in terminal_loans:
                anomalies["records_after_first_exit"] += 1
            if values[8]:
                terminal_loans.add(loan_id)
                if not values[9]:
                    anomalies["exit_without_effective_month"] += 1
                elif month_index(values[9]) != month:
                    anomalies["exit_effective_month_differs_from_reporting_month"] += 1
            if loan_id in intervals:
                lo, hi, count, mask = intervals[loan_id]
                # All records are independently checked; database primary key also
                # rejects a duplicate even if the input is out of order.
                if month < hi:
                    anomalies["records_out_of_order_within_loan"] += 1
                if mask & (1 << (month - 1900 * 12)):
                    raise ValueError("Duplicate loan/month record")
                intervals[loan_id] = (min(lo, month), max(hi, month), count + 1, mask | (1 << (month - 1900 * 12)))
            else:
                intervals[loan_id] = (month, month, 1, 1 << (month - 1900 * 12))
            parsed = [values[i] for i in PERFORMANCE_POSITIONS]
            for i, name in enumerate(PERFORMANCE_STORED):
                if name in {"period", "loan_age", "remaining_term"}:
                    parsed[i] = int(parsed[i]) if parsed[i] else None
                elif name in {"current_upb", "current_rate", "non_interest_upb"}:
                    parsed[i] = finite_number(parsed[i]) if parsed[i] else None
                    if parsed[i] is not None and parsed[i] < 0:
                        nonnegative_failures[name] += 1
            age = parsed[4]
            if loan_id in previous_age and age is not None and previous_age[loan_id] is not None and age < previous_age[loan_id]:
                age_resets += 1
            previous_age[loan_id] = age
            batch.append(parsed)
            if len(batch) >= 10000:
                conn.executemany(perf_insert, batch); batch.clear()
        if batch:
            conn.executemany(perf_insert, batch)
    conn.commit()
    gap_loans = sum(hi - lo + 1 != count for lo, hi, count, _ in intervals.values())
    gaps = sum(hi - lo + 1 - count for lo, hi, count, _ in intervals.values())
    report["performance"].update(unique_loans=len(intervals), period_min=min(period_counts), period_max=max(period_counts),
        period_counts={str(k): v for k, v in sorted(period_counts.items())},
        delinquency_counts=dict(sorted(delinquency_counts.items())), zero_balance_counts=dict(sorted(zero_counts.items())),
        loans_with_exit=len(terminal_loans), loan_age_decreases=age_resets,
        loans_with_internal_calendar_gaps=gap_loans, internal_missing_months=gaps,
        observed_months_min=min(x[2] for x in intervals.values()), observed_months_max=max(x[2] for x in intervals.values()),
        negative_values=dict(nonnegative_failures), anomalies=dict(anomalies))
    report["validation"].update(zip_crc_passed=True, origination_unique=True,
        performance_key_unique=True, performance_loan_ids_matched=True,
        origination_without_performance=len(ids - intervals.keys()),
        schema_field_counts_passed=True, sqlite_integrity=conn.execute("PRAGMA integrity_check").fetchone()[0])
    conn.close()
    stage.replace(db_path)
    target = ROOT / "reports" / f"data_audit_{year}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "processed")
    args = parser.parse_args()
    r = audit(args.zip, args.year, args.output)
    print(json.dumps({"origination_rows": r["origination"]["rows"],
        "performance_rows": r["performance"]["rows"], "validation": r["validation"],
        "anomalies": r["performance"]["anomalies"],
        "report": str(ROOT / "reports" / f"data_audit_{args.year}.json")}, indent=2))
