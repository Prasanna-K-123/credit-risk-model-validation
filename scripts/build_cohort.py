"""Build a private feature/label table; publish aggregate audit evidence only."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mortgage_risk.cohorts import snapshot_rows, outcome_12m
from mortgage_risk.schema import add_months


def build(year: int, as_of: int, role: str) -> dict:
    db = ROOT / "data" / "processed" / f"sample_{year}.sqlite"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    features = snapshot_rows(conn, as_of)
    if not features:
        raise ValueError("No eligible observations")
    outcomes, missing = Counter(), Counter()
    positives = 0
    known = 0
    horizon = add_months(as_of, 12)
    out = ROOT / "data" / "cohorts" / f"{role}_{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(".csv.partial")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(features[0]) + ["as_of", "label_end", "label", "label_reason"])
        writer.writeheader()
        for row in features:
            future = conn.execute(
                "SELECT period, delinquency, zero_balance_code FROM performance "
                "WHERE loan_id=? AND period>? AND period<=? ORDER BY period",
                (row["loan_id"], as_of, horizon)).fetchall()
            y = outcome_12m(future, as_of)
            outcomes[y.reason] += 1
            positives += y.value == 1
            known += y.value is not None
            missing.update(k for k, v in row.items() if v is None or v == "MISSING")
            writer.writerow(dict(row, as_of=as_of, label_end=horizon, label=y.value, label_reason=y.reason))
    temporary.replace(out)
    total = conn.execute("SELECT COUNT(*) FROM origination").fetchone()[0]
    at_landmark = conn.execute("SELECT COUNT(*) FROM performance WHERE period=?", (as_of,)).fetchone()[0]
    conn.close()
    report = {
        "year": year, "role": role, "as_of": as_of, "history_start": add_months(as_of, -5),
        "label_start": add_months(as_of, 1), "label_end": horizon,
        "origination_loans": total, "loans_observed_at_landmark": at_landmark,
        "eligible_loans": len(features), "excluded_from_origination_count": total-len(features),
        "known_outcomes": known, "positive_outcomes": positives, "unresolved_outcomes": len(features)-known,
        "outcome_counts": dict(outcomes), "feature_missing_counts": dict(missing),
        "event_rate_among_known": positives / known if known else None,
        "all_eligible_event_rate_bounds": [positives / len(features), (positives + len(features)-known) / len(features)],
        "private_table_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "interpretation": "Latest-release retrospective snapshot; no historical-release availability claim. Censoring bounds are identification bounds, not confidence intervals.",
    }
    (ROOT / "reports" / f"cohort_audit_{role}_{year}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--as-of", type=int, required=True)
    parser.add_argument("--role", choices=["train", "adaptation", "validation", "stress_test", "transport_test"], required=True)
    a = parser.parse_args()
    print(json.dumps(build(a.year, a.as_of, a.role), indent=2))
