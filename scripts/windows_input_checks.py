"""Independent current-input checks; reads no forward labels for held-out loans."""
from __future__ import annotations
from collections import Counter
from contextlib import closing
from decimal import Decimal, localcontext
from functools import lru_cache
import csv
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mortgage_risk.portable_log1p import positive_log1p
from mortgage_risk.schema import add_months

FEATURE_COLUMNS = ["loan_id", "fico", "dti", "ltv", "cltv", "mi_pct",
                   "original_term", "original_rate", "purpose", "occupancy",
                   "property_type", "relief_refinance", "current_rate", "current_dq",
                   "max_dq_6m", "dq_months_6m", "balance_ratio_6m",
                   "modified_by_snapshot", "calendar_age", "log_current_upb", "log_original_upb"]
LABEL_COLUMNS = ["as_of", "label_end", "label", "label_reason"]
CATEGORICAL = {"purpose", "occupancy", "property_type", "relief_refinance"}
ORIG_POSITIONS = {"fico": 0, "mi_pct": 5, "cltv": 8, "dti": 9,
                  "ltv": 11, "original_rate": 12, "original_term": 21,
                  "purpose": 20, "occupancy": 7, "property_type": 17,
                  "relief_refinance": 27}
SENTINELS = {"fico": "9999", "dti": "999", "ltv": "999", "cltv": "999", "mi_pct": "999"}


@lru_cache(maxsize=None)
def reference_log(x):
    # Actual mortgage inputs are >=9.72 and <=1.6e6; 80 decimal digits
    # leave a wide margin beyond the approximately 16 binary64 digits.
    with localcontext() as ctx:
        ctx.prec = 80
        return (Decimal(1) + Decimal.from_float(x)).ln()


def frames(root):
    output = []
    study = json.loads((root / "study.json").read_text())
    seen = set()
    for spec in study["cohorts"]:
        role, year = spec["role"], spec["year"]
        with (root / f"data/prepared/{role}_{year}.csv").open(newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            labels = role not in {"stress_test", "transport_test"}
            if reader.fieldnames != FEATURE_COLUMNS + (LABEL_COLUMNS if labels else []):
                raise ValueError("Unexpected feature schema/order or held-out labels.")
        ids = [row["loan_id"] for row in rows]
        if ids != sorted(ids) or len(set(ids)) != len(ids) or any(re.fullmatch(r"[FA]\d{2}Q[1-4]\d{7}", x) is None for x in ids):
            raise ValueError("Prepared key format/order/uniqueness failed.")
        if set(ids) & seen:
            raise ValueError("Duplicate supplied key across prepared cohorts.")
        seen.update(ids)
        historical = json.loads((root / "reports/portable/historical" /
                                 f"cohort_audit_{role}_{year}.json").read_text())
        missing = Counter(k for row in rows for k in FEATURE_COLUMNS[1:]
                          if row[k] in ("", "MISSING"))
        if dict(missing) != historical["feature_missing_counts"]:
            raise ValueError("Historical feature missingness counts differ.")
        expected = next(x for x in json.loads((root / "reports/portable/historical/preparation.json").read_text())["prepared"]
                        if x["year"] == year)
        if len(rows) != expected["rows"]:
            raise ValueError("Historical eligible count differs.")
        if labels:
            known = [int(row["label"]) for row in rows if row["label"] != ""]
            if any(y not in (0, 1) for y in known):
                raise ValueError("Invalid fitting label.")
            if (len(known), sum(known), len(rows)-len(known)) != (
                    historical["known_outcomes"], historical["positive_outcomes"], historical["unresolved_outcomes"]):
                raise ValueError("Historical fitting/validation label counts differ.")
        output.append((spec, rows, {"year": year, "rows": len(rows), "schema_key_order_passed": True,
                                    "historical_missingness_exact": True, "has_forward_labels": labels}))
    return output


def log_and_ratio_checks(root, checked):
    results = []
    maximum_error_ulps = Decimal(0)
    total_logs, total_ratios = 0, 0
    for spec, rows, info in checked:
        year, asof = spec["year"], spec["as_of"]
        start = add_months(asof, -5)
        with closing(sqlite3.connect((root / f"data/processed/sample_{year}.sqlite").resolve().as_uri()+"?mode=ro", uri=True)) as db:
            balances = {loan: (float(original), float(current), float(initial))
                        for loan, original, current, initial in db.execute(
                            "SELECT o.loan_id,o.original_upb,p.current_upb,h.current_upb "
                            "FROM origination o JOIN performance p ON o.loan_id=p.loan_id AND p.period=? "
                            "JOIN performance h ON o.loan_id=h.loan_id AND h.period=?", (asof, start))}
        minimum, maximum = math.inf, 0.0
        for row in rows:
            original, current, initial = balances[row["loan_id"]]
            for field, x in (("log_original_upb", original), ("log_current_upb", current)):
                minimum, maximum = min(minimum, x), max(maximum, x)
                value = float(row[field])
                if value != positive_log1p(x):
                    raise ValueError("Saved log feature does not equal declared adapter.")
                with localcontext() as ctx:
                    ctx.prec = 80
                    error_ulps = abs(Decimal.from_float(value)-reference_log(x))/Decimal.from_float(math.ulp(value))
                if error_ulps > 1:
                    raise ValueError("Log feature differs by more than one ulp from high-precision reference.")
                maximum_error_ulps = max(maximum_error_ulps, error_ulps)
                total_logs += 1
            ratio = float(row["balance_ratio_6m"])
            with localcontext() as ctx:
                ctx.prec = 80
                independent = float(Decimal.from_float(current)/Decimal.from_float(initial))
            if ratio != independent:
                raise ValueError("Balance ratio differs from high-precision division of source balances.")
            total_ratios += 1
        results.append({**info, "minimum_log_input": minimum, "maximum_log_input": maximum,
                        "logs_checked": 2*len(rows), "ratios_checked": len(rows)})
    return {"passed": True, "decimal_precision": 80, "log_accuracy_bound_ulps": 1,
            "maximum_observed_log_error_ulps": float(maximum_error_ulps),
            "log_cells_checked": total_logs, "balance_ratios_checked": total_ratios,
            "scope": "Accuracy and current source consistency, not unavailable historical cellwise equality.",
            "cohorts": results}


def raw_feature_check(root, spec, rows):
    """Reconstruct every feature from ZIP strings, independently of snapshot SQL."""
    year, asof = spec["year"], spec["as_of"]
    start = add_months(asof, -5)
    selected = {row["loan_id"] for row in rows}
    origins, histories = {}, {}
    with zipfile.ZipFile(root / f"data/raw/sample_{year}.zip") as archive:
        with archive.open(f"sample_orig_{year}.txt") as stream:
            for raw in stream:
                values = raw.decode("utf-8-sig").rstrip("\r\n").split("|")
                if len(values) != 31:
                    raise ValueError("Raw origination schema changed.")
                loan = values[19]
                if loan in selected:
                    if loan in origins:
                        raise ValueError("Duplicate raw origination key.")
                    origins[loan] = values
        with archive.open(f"sample_perf_{year}.txt") as stream:
            for raw in stream:
                prefix = raw.split(b"|", 2)
                if len(prefix) != 3:
                    raise ValueError("Invalid raw performance prefix.")
                # Only feature-window records are decoded beyond key/month.
                period = int(prefix[1])
                if not start <= period <= asof:
                    continue
                loan = prefix[0].decode("ascii")
                if loan not in selected:
                    continue
                values = raw.decode("utf-8").rstrip("\r\n").split("|")
                if len(values) != 35:
                    raise ValueError("Raw performance schema changed.")
                key = (loan, period)
                if key in histories:
                    raise ValueError("Duplicate raw feature-window key.")
                histories[key] = values
    expected_months = [add_months(asof, i) for i in range(-5, 1)]
    numeric_cells = categorical_cells = 0
    for row in rows:
        loan = row["loan_id"]
        orig = origins[loan]
        history = [histories[(loan, p)] for p in expected_months]
        last, first = history[-1], history[0]
        if (last[3] not in ("00", "01", "02") or float(last[2]) <= 0 or
                any(x[8] or x[3] in ("RA", "XX") for x in history) or
                float(first[2]) <= 0 or int(orig[1]) > asof):
            raise ValueError("Raw eligibility reconstruction failed.")
        expected = {}
        for field, position in ORIG_POSITIONS.items():
            text = orig[position]
            if field in CATEGORICAL:
                expected[field] = "MISSING" if text in ("", "9", "99") else text
            else:
                expected[field] = None if text == "" or text == SENTINELS.get(field) else float(text)
        y0, m0 = divmod(int(orig[1]), 100)
        y1, m1 = divmod(asof, 100)
        expected.update(current_rate=None if last[10] == "" else float(last[10]),
                        current_dq=float(int(last[3])),
                        max_dq_6m=float(max(int(x[3]) for x in history)),
                        dq_months_6m=float(sum(int(x[3]) >= 1 for x in history)),
                        balance_ratio_6m=float(last[2])/float(first[2]),
                        modified_by_snapshot=float(any(x[7] in ("Y", "P") for x in history)),
                        calendar_age=float((y1-y0)*12+m1-m0+1),
                        log_current_upb=positive_log1p(float(last[2])),
                        log_original_upb=positive_log1p(float(orig[10])))
        if set(expected) != set(FEATURE_COLUMNS[1:]):
            raise ValueError("Independent reconstruction omitted a feature.")
        for field, value in expected.items():
            if field in CATEGORICAL:
                categorical_cells += 1
                valid = row[field] == value
            else:
                numeric_cells += 1
                valid = row[field] == "" if value is None else float(row[field]) == value
            if not valid:
                raise ValueError(f"Independent raw feature mismatch: year={year}, field={field}")
    return {"passed": True, "year": year, "rows": len(rows), "features_per_row": 20,
            "numeric_cells_exact": numeric_cells, "categorical_cells_exact": categorical_cells,
            "raw_feature_window_records": len(histories),
            "forward_outcome_fields_used": False,
            "algorithm": "Independent Python reconstruction from pinned ZIP strings; no snapshot SQL.",
            "historical_array_comparison": "Unavailable; this establishes current raw-source consistency."}


def check(root=ROOT):
    checked = frames(root)
    numeric = log_and_ratio_checks(root, checked)
    raw = [raw_feature_check(root, spec, rows) for spec, rows, _ in checked if spec["year"] in (2016, 2018)]
    return {"passed": True, "all_six_schema_keys_order_missingness_counts_passed": True,
            "all_six_numeric_checks": numeric, "two_unmatched_tables_raw_reconstruction": raw,
            "historical_prepared_byte_gate": "FAILED for 2016 and 2018; preserved separately.",
            "no_historical_rowwise_equivalence_claim": True}


if __name__ == "__main__":
    import hashlib
    import time
    started = time.monotonic()
    spec = json.loads((ROOT / "compatibility/windows_verification_v1.json").read_text())
    before = {name: hashlib.sha256((ROOT / "data/prepared" / name).read_bytes()).hexdigest()
              for name in spec["current_prepared_sha256"]}
    if before != spec["current_prepared_sha256"]:
        raise ValueError("Current input hash differs from the explicit Windows protocol.")
    result = check()
    after = {name: hashlib.sha256((ROOT / "data/prepared" / name).read_bytes()).hexdigest() for name in before}
    if before != after:
        raise ValueError("Current inputs changed during independent verification.")
    result.update(current_prepared_sha256=after,
                  checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  elapsed_seconds=time.monotonic()-started)
    target = ROOT / "reports/portable/windows_input_checks.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
