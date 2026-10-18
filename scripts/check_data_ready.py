"""Fail closed unless every planned source is present and matches a passed audit.

This is a necessary input gate, not a substitute for cross-cohort validation.
Exit 0 means the source gate passed; exit 2 means work must not proceed to fitting.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ("zip_crc_passed", "origination_unique", "performance_key_unique",
          "performance_loan_ids_matched", "schema_field_counts_passed")


def check_sources(root: Path, source_dirs: list[Path]) -> dict:
    study = json.loads((root / "study.json").read_text())
    results = []
    for year in sorted({c["year"] for c in study["cohorts"]}):
        filename = f"sample_{year}.zip"
        sources = [d / filename for d in source_dirs if (d / filename).is_file()]
        entry = {"year": year, "filename": filename, "status": "missing_source"}
        if sources:
            audit_path = root / "reports" / f"data_audit_{year}.json"
            entry["status"] = "missing_audit"
            if audit_path.is_file():
                try:
                    audit = json.loads(audit_path.read_text())
                    valid = (audit["source"]["year"] == year
                             and all(audit["validation"].get(k) is True for k in CHECKS)
                             and audit["validation"].get("sqlite_integrity") == "ok"
                             and audit["validation"].get("origination_without_performance") == 0)
                    entry["status"] = "audit_failed"
                    if valid:
                        hashes = []
                        for source in sources:
                            with source.open("rb") as stream:
                                hashes.append(hashlib.file_digest(stream, "sha256").hexdigest())
                        entry["status"] = "verified" if all(h == audit["source"]["sha256"] for h in hashes) else "checksum_mismatch"
                except (OSError, ValueError, KeyError, TypeError):
                    entry["status"] = "invalid_audit"
        results.append(entry)
    return {"source_gate_passed": bool(results) and all(r["status"] == "verified" for r in results),
            "required": len(results), "verified": sum(r["status"] == "verified" for r in results),
            "files": results,
            "scope": "Source availability and audit/hash agreement only; cross-cohort validation remains required."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, action="append", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = check_sources(ROOT, args.source_dir)
    text = json.dumps(result, indent=2) + "\n"
    if args.report:
        args.report.write_text(text)
    print(text, end="")
    raise SystemExit(0 if result["source_gate_passed"] else 2)
