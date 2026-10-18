"""Stream user-supplied Release 47 ZIPs; retain aggregate integrity evidence only.

This supplements the preserved earlier P1 work. It neither recreates the missing
cohort-builder snapshot nor fits/selects models or reports held-out performance.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

YEARS = (2012, 2013, 2015, 2016, 2018, 2021)
OLD_2012 = {
    "zip": "57b6b0281ee956dd1b8b4a7a24e4d3469fcbc8292fd7df981aa2a494f6a50220",
    "orig": "a428c6af7b1d4408f16bacd89eef57dac4a0b0cbb3276314f044176920cc98b8",
    "perf": "5271ee93afc9f18ef99084037e0fe5880d1b1d7eaf6434e2204ddd0ebe784b04",
}


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while data := f.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()


def month_index(value):
    if not re.fullmatch(rb"\d{6}", value):
        raise ValueError("Monthly reporting period is not YYYYMM")
    year, month = int(value[:4]), int(value[4:])
    if not 1990 <= year <= 2100 or not 1 <= month <= 12:
        raise ValueError("Monthly reporting period outside supported calendar")
    return (year - 1990) * 12 + month - 1


def calendar_label(index):
    return (1990 + index // 12) * 100 + index % 12 + 1


def audit_archive(path, year):
    out = {"year": year, "uploaded_name": path.name, "zip_bytes": path.stat().st_size,
           "zip_sha256": sha_file(path), "audited_utc": datetime.now(timezone.utc).isoformat(),
           "audit_script_sha256": sha_file(Path(__file__)), "members": {}}
    names = {"orig": f"sample_orig_{year}.txt", "perf": f"sample_perf_{year}.txt"}
    with zipfile.ZipFile(path) as z:
        if sorted(z.namelist()) != sorted(names.values()):
            raise ValueError("Unexpected archive members")
        # The performance identifier is located by exact agreement with a source
        # origination field, then checked against the documented 20th position.
        with z.open(names["perf"]) as f:
            first = f.readline().rstrip(b"\r\n").split(b"|")
        if len(first) != 35:
            raise ValueError("Unexpected monthly field count")
        month_index(first[1])
        orig_key_index = None
        with z.open(names["orig"]) as f:
            for raw in f:
                fields = raw.rstrip(b"\r\n").split(b"|")
                found = [i for i, v in enumerate(fields) if v == first[0]]
                if found:
                    if len(found) != 1:
                        raise ValueError("Ambiguous origination loan key")
                    orig_key_index = found[0]
                    break
        if orig_key_index != 19:
            raise ValueError("Loan-key position does not match Release 47")
        ids = set()
        quarters = Counter()
        field_counts = Counter()
        h = hashlib.sha256()
        rows = duplicates = bad_ids = 0
        with z.open(names["orig"]) as f:
            for raw in f:
                h.update(raw)
                fields = raw.rstrip(b"\r\n").split(b"|")
                field_counts[len(fields)] += 1
                if len(fields) != 31:
                    raise ValueError("Unexpected origination field count")
                loan = fields[orig_key_index]
                rows += 1
                duplicates += loan in ids
                ids.add(loan)
                match = re.fullmatch(rb"[FA](\d{2})Q([1-4])\d{7}", loan)
                if match is None or int(match[1]) != year % 100:
                    bad_ids += 1
                else:
                    quarters[match[2].decode()] += 1
        info = z.getinfo(names["orig"])
        out["members"]["orig"] = {"name": info.filename, "bytes": info.file_size,
            "sha256": h.hexdigest(), "crc_verified_by_complete_read": True,
            "rows": rows, "field_count_rows": dict(field_counts), "unique_loans": len(ids),
            "duplicate_loan_keys": duplicates, "invalid_year_or_identifier": bad_ids,
            "origination_quarter_counts_from_loan_identifier": dict(quarters)}
        h = hashlib.sha256()
        field_counts = Counter()
        bits = {}
        rows = duplicates = unknown = non_chronological = 0
        previous = {}
        with z.open(names["perf"]) as f:
            for raw in f:
                h.update(raw)
                fields = raw.rstrip(b"\r\n").split(b"|")
                field_counts[len(fields)] += 1
                if len(fields) != 35:
                    raise ValueError("Unexpected monthly field count")
                loan, month = fields[0], month_index(fields[1])
                rows += 1
                unknown += loan not in ids
                mask = 1 << month
                old = bits.get(loan, 0)
                duplicates += bool(old & mask)
                bits[loan] = old | mask
                if loan in previous and month <= previous[loan]:
                    non_chronological += 1
                previous[loan] = month
        gap_months = gap_loans = 0
        lengths = []
        starts, ends = [], []
        for bitmap in bits.values():
            first_month = (bitmap & -bitmap).bit_length() - 1
            last_month = bitmap.bit_length() - 1
            n = bitmap.bit_count()
            gap = last_month - first_month + 1 - n
            gap_months += gap
            gap_loans += gap > 0
            lengths.append(n)
            starts.append(first_month)
            ends.append(last_month)
        info = z.getinfo(names["perf"])
        out["members"]["perf"] = {"name": info.filename, "bytes": info.file_size,
            "sha256": h.hexdigest(), "crc_verified_by_complete_read": True,
            "rows": rows, "field_count_rows": dict(field_counts), "unique_loans": len(bits),
            "unique_loan_months": sum(lengths), "duplicate_loan_months": duplicates,
            "rows_without_origination_key": unknown, "origination_loans_without_performance": len(ids - bits.keys()),
            "non_increasing_source_order_rows_within_loan": non_chronological,
            "loans_with_internal_calendar_gaps": gap_loans, "missing_internal_calendar_months": gap_months,
            "reporting_month_min": calendar_label(min(starts)), "reporting_month_max": calendar_label(max(ends)),
            "observations_per_loan_min": min(lengths), "observations_per_loan_max": max(lengths)}
    o, p = out["members"]["orig"], out["members"]["perf"]
    out["structural_checks_pass"] = all([
        o["rows"] == 50000, o["unique_loans"] == 50000, o["duplicate_loan_keys"] == 0,
        o["invalid_year_or_identifier"] == 0, p["duplicate_loan_months"] == 0,
        p["rows_without_origination_key"] == 0, p["origination_loans_without_performance"] == 0,
        p["missing_internal_calendar_months"] == 0, p["non_increasing_source_order_rows_within_loan"] == 0,
    ])
    if year == 2012:
        out["matches_prior_2012_snapshot"] = (out["zip_sha256"] == OLD_2012["zip"]
            and o["sha256"] == OLD_2012["orig"] and p["sha256"] == OLD_2012["perf"])
        if not out["matches_prior_2012_snapshot"]:
            raise ValueError("2012 source differs from preserved source checkpoint")
    out["scope_limit"] = "Source integrity only: no cohort labels, model fitting, linked-loan exclusions or held-out model evaluation."
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "reports")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_results = []
    for year in YEARS:
        paths = sorted(args.input_dir.glob(f"sample_{year}*.zip"))
        if len(paths) != 1:
            raise ValueError(f"Expected exactly one uploaded ZIP for {year}")
        result = audit_archive(paths[0], year)
        target = args.output_dir / f"source_{year}.json"
        staged = target.with_suffix(".json.tmp")
        staged.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        staged.replace(target)
        all_results.append(result)
        print(json.dumps({"year": year, "loans": result["members"]["orig"]["unique_loans"],
            "monthly_rows": result["members"]["perf"]["rows"],
            "pass": result["structural_checks_pass"]}), flush=True)
    summary = {"archives": len(all_results), "loans": sum(x["members"]["orig"]["unique_loans"] for x in all_results),
        "loan_months": sum(x["members"]["perf"]["rows"] for x in all_results),
        "all_structural_checks_pass": all(x["structural_checks_pass"] for x in all_results),
        "input_zip_bytes": sum(x["zip_bytes"] for x in all_results),
        "uncompressed_member_bytes": sum(v["bytes"] for x in all_results for v in x["members"].values()),
        "sources": [{"year": x["year"], "zip_sha256": x["zip_sha256"]} for x in all_results],
        "scope_limit": "Audited source intake; no model result or full P1 completion is claimed."}
    (args.output_dir / "intake_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
