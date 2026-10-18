"""Prepare fitting labels and label-free tests after supplied-linkage exclusion."""
from __future__ import annotations
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mortgage_risk.cohorts import snapshot_rows
from build_cohort import build


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def linked_later(records):
    parent, seen = {}, {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for year, identifier, previous in records:
        if identifier in seen:
            raise ValueError("Duplicate supplied loan identifier across cohorts")
        seen[identifier] = year
        find(identifier)
        if previous:
            a, b = find(identifier), find(previous)
            if a != b:
                parent[b] = a
    earliest = {}
    for identifier, year in seen.items():
        group = find(identifier)
        earliest[group] = min(year, earliest.get(group, year))
    excluded = {identifier for identifier, year in seen.items()
                if year > earliest[find(identifier)]}
    groups = Counter(find(identifier) for identifier in seen)
    return excluded, {"origination_records": len(seen),
                      "duplicate_ids": 0,
                      "components_with_multiple_supplied_loans": sum(n>1 for n in groups.values()),
                      "excluded_later_records": len(excluded),
                      "excluded_by_year": dict(Counter(seen[x] for x in excluded)),
                      "linkage_scope": "Supplied pre-HARP links, including parents outside the sample; no external linkage."}


def main():
    if (ROOT/"artifacts/training_started.json").exists():
        raise RuntimeError("Do not rewrite prepared data after fitting starts")
    readiness = json.loads((ROOT/"reports/source_readiness.json").read_text())
    if not readiness["source_gate_passed"]:
        raise RuntimeError("Source readiness failed")
    study = json.loads((ROOT/"study.json").read_text())
    records = []
    for c in study["cohorts"]:
        with sqlite3.connect(f'file:{ROOT}/data/processed/sample_{c["year"]}.sqlite?mode=ro', uri=True) as conn:
            records.extend((c["year"], a, b) for a, b in conn.execute(
                "SELECT loan_id,pre_harp_loan_id FROM origination ORDER BY loan_id"))
    excluded, overlap = linked_later(records)
    (ROOT/"data/prepared").mkdir(exist_ok=True)
    (ROOT/"data/prepared/excluded_ids.json").write_text(json.dumps(sorted(excluded))+"\n")
    (ROOT/"reports/cross_cohort_audit.json").write_text(json.dumps(overlap, indent=2, sort_keys=True)+"\n")
    outputs = []
    for c in study["cohorts"]:
        year, role = c["year"], c["role"]
        if role in {"stress_test", "transport_test"}:
            with sqlite3.connect(f'file:{ROOT}/data/processed/sample_{year}.sqlite?mode=ro', uri=True) as conn:
                rows = snapshot_rows(conn, c["as_of"])
            # No forward-outcome query occurs for either held-out cohort here.
            labelled = False
        else:
            result = build(year, c["as_of"], role)
            if year == 2012 and result["private_table_sha256"] != "bdeaa4220b0ba26da732ccbcfe710ddbafce803359eb34a3035158a3d1433d7a":
                raise ValueError("Original 2012 cohort byte regression failed")
            with (ROOT/f"data/cohorts/{role}_{year}.csv").open() as f:
                rows = list(csv.DictReader(f))
            labelled = True
        before = len(rows)
        rows = [row for row in rows if row["loan_id"] not in excluded]
        out = ROOT/f"data/prepared/{role}_{year}.csv"
        with out.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        outputs.append({"year": year, "role": role, "eligible_before_link_exclusion": before,
                        "link_excluded_eligible": before-len(rows), "rows": len(rows),
                        "has_forward_labels": labelled, "private_table_sha256": sha(out)})
        print(json.dumps(outputs[-1]), flush=True)
    report = {"source_gate_passed": True, "original_2012_byte_regression": True,
              "cross_cohort": overlap, "prepared": outputs,
              "test_outcomes_accessed": False}
    (ROOT/"reports/preparation.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")


if __name__ == "__main__":
    main()
