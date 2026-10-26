"""Audited runtime wrapper around the unchanged frozen study scripts.

Run prepare, fit, evaluate, compare in a fresh private reproduction checkout.
Raw data and artifacts remain ignored. Each stage runs in a separate process.
"""
from __future__ import annotations
import argparse
from contextlib import redirect_stderr
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import sqlite3
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from mortgage_risk.portable_log1p import VERSION, UPSTREAM_COMMIT, UPSTREAM_BLOB, cohort_math
from prepare_verified_stores import prepare as verify_caches
from portable_compare import compare, report_precision

PORTABLE = ROOT / "reports/portable"
CONTRACT = ROOT / "compatibility/reproduction_contract_v1.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                          encoding="utf-8", newline="\n")


def contract():
    return read(CONTRACT)


def check_methods():
    expected = read(ROOT / "reports/prefit_manifest.json")["method_files"]
    for name, digest in expected.items():
        if sha(ROOT / name) != digest:
            raise ValueError("Original method changed: " + name)
    return expected


def execution_files():
    paths = set(check_methods())
    for pattern in ("scripts/*.py", "src/mortgage_risk/*.py", "tests/*.py",
                    "source_intake/*.py", "tools/*.py", "third_party/glibc/*",
                    "compatibility/*.json"):
        paths.update(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern) if p.is_file())
    paths.update(("reports/evaluation_repair.json", "reports/prefit_manifest.json",
                  "docs/demo.template.html"))
    return {name: sha(ROOT / name) for name in sorted(paths)}


def runtime():
    from threadpoolctl import threadpool_info
    import numpy
    import scipy.linalg
    import sklearn
    pools = threadpool_info()
    for pool in pools:
        if "filepath" in pool:
            pool["filepath"] = Path(pool["filepath"]).name
    return {"python": sys.version, "platform": platform.platform(),
            "machine": platform.machine(), "sqlite": sqlite3.sqlite_version,
            "packages": {name: importlib.metadata.version(name) for name in
                         ("numpy", "scipy", "pandas", "scikit-learn", "joblib", "threadpoolctl")},
            "thread_environment": {key: os.environ.get(key) for key in contract()["threads"]},
            "python_utf8": os.environ.get("PYTHONUTF8"), "utf8_mode": sys.flags.utf8_mode,
            "threadpools": pools}


def check_environment():
    spec = contract()
    if any(os.environ.get(k) != v for k, v in spec["threads"].items()):
        raise ValueError("Set every thread variable to the prespecified value 2.")
    if os.environ.get("PYTHONUTF8") != "1" or not sys.flags.utf8_mode:
        raise ValueError("Start Python with PYTHONUTF8=1.")
    if sys.version_info[:2] != (3, 12):
        raise ValueError("This compatibility run specifies Python 3.12.")
    expected = read(ROOT / "reports/prefit_manifest.json")["runtime_versions"]
    for name, version in expected.items():
        if importlib.metadata.version(name) != version:
            raise ValueError("Pinned package version mismatch: " + name)
    return runtime()


def invoke(relative, args=()):
    previous = sys.argv
    sys.argv = [str(ROOT / relative), *map(str, args)]
    try:
        try:
            runpy.run_path(str(ROOT / relative), run_name="__main__")
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
    finally:
        sys.argv = previous


def run_tests():
    records = []
    for args in (["-m", "unittest", "discover", "-s", "tests", "-v"],
                 ["-m", "unittest", "discover", "-s", "source_intake", "-p", "test_*.py", "-v"]):
        result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True,
                                capture_output=True, encoding="utf-8")
        records.append({"arguments": args, "returncode": result.returncode,
                        "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode:
            write(PORTABLE / "test_results.json", {"passed": False, "runs": records})
            raise RuntimeError("Tests failed before preparing or fitting.")
    # Original synthetic lookback/leakage tests also run with the actual proxy.
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_cohorts.py")
    with cohort_math() as proxy:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        proxy_receipt = proxy.receipt()
    records.append({"arguments": ["original test_cohorts.py under cohort_math"],
                    "returncode": 0 if result.wasSuccessful() else 1,
                    "stdout": "", "stderr": stream.getvalue(), "adapter": proxy_receipt})
    output = {"passed": result.wasSuccessful(), "runs": records}
    write(PORTABLE / "test_results.json", output)
    if not output["passed"]:
        raise RuntimeError("Original cohort tests failed under the adapter.")
    return {"passed": True, "receipt_sha256": sha(PORTABLE / "test_results.json")}


def assert_prepared():
    hashes = {name: sha(ROOT / "data/prepared" / name)
              for name in contract()["historical_prepared_sha256"]}
    if hashes != contract()["historical_prepared_sha256"]:
        raise ValueError("At least one of the six historical prepared-table hashes differs.")
    report = compare(read(PORTABLE / "historical/preparation.json"), read(ROOT / "reports/preparation.json"),
                     atol=0.0, rtol=0.0)
    if not report["passed"]:
        raise ValueError("Preparation counts or label-access status changed.")
    return hashes


def check_manifest():
    path = PORTABLE / "runtime_manifest.json"
    if sha(path) != (PORTABLE / "runtime_manifest.sha256").read_text().strip():
        raise ValueError("Runtime manifest changed.")
    manifest = read(path)
    if sha(CONTRACT) != manifest["comparison_contract_sha256"]:
        raise ValueError("Comparison contract changed after preparation.")
    for name, digest in manifest["execution_file_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("Execution source changed after preparation: " + name)
    for name, digest in contract()["historical_file_sha256"].items():
        if sha(PORTABLE / "historical" / name) != digest:
            raise ValueError("Historical aggregate baseline changed: " + name)
    if check_environment() != manifest["runtime"]:
        raise ValueError("Runtime differs from the pre-fit manifest.")
    return manifest


def prepare_stage():
    if (ROOT / "artifacts/training_started.json").exists() or (PORTABLE / "runtime_manifest.json").exists():
        raise RuntimeError("Use a fresh reproduction copy; do not remove or replace an existing run's seals.")
    spec = contract()
    for name, digest in spec["historical_file_sha256"].items():
        if sha(ROOT / "reports" / name) != digest:
            raise ValueError("Historical baseline differs before execution: " + name)
    env = check_environment()
    methods = check_methods()
    (PORTABLE / "historical").mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "reports").iterdir():
        if path.is_file():
            shutil.copyfile(path, PORTABLE / "historical" / path.name)
    tests = run_tests()
    caches = verify_caches(ROOT, verify_only=True)
    invoke("scripts/check_data_ready.py", ["--source-dir", ROOT / "data/raw",
                                          "--report", ROOT / "reports/source_readiness.json"])
    manifest = {"created_utc": now(), "adapter_version": VERSION,
                "upstream_commit": UPSTREAM_COMMIT, "upstream_blob": UPSTREAM_BLOB,
                "runtime": env, "tests": tests, "cache_verification": caches,
                "cache_attestation_sha256": sha(ROOT / "data/processed/cache_attestation.json"),
                "original_method_count": len(methods),
                "execution_file_sha256": execution_files(),
                "comparison_contract_sha256": sha(CONTRACT),
                "fit_budget": spec["fit_budget"],
                "scope": "Compatibility-assisted local rerun; no native environment identity claim."}
    write(PORTABLE / "runtime_manifest.json", manifest)
    (PORTABLE / "runtime_manifest.sha256").write_text(sha(PORTABLE / "runtime_manifest.json") + "\n", encoding="ascii")
    with cohort_math() as proxy:
        invoke("scripts/prepare_study.py")
        usage = proxy.receipt()
    hashes = assert_prepared()
    output = {"passed": True, "completed_utc": now(), "historical_prepared_tables_exact": hashes,
              "all_original_methods_unchanged": True, "adapter": usage,
              "full_fits_started": 0, "test_outcomes_accessed_for_selection": False}
    write(PORTABLE / "prefit_gate.json", output)
    print(json.dumps(output, indent=2))


def fit_stage():
    check_manifest()
    if not read(PORTABLE / "prefit_gate.json")["passed"]:
        raise ValueError("Pre-fit gate failed.")
    assert_prepared()
    started = now()
    invoke("scripts/fit_and_seal.py")
    selection = read(ROOT / "reports/selection.json")
    if (selection["full_fits"], selection["intercept_fits"]) != (4, 2):
        raise ValueError("Original fixed fit budget mismatch.")
    sealed = {"reports/selection.json": sha(ROOT / "reports/selection.json")}
    sealed.update({"artifacts/" + name: digest for name, digest in selection["models"].items()})
    sealed.update({f"artifacts/predictions_{year}.csv": item["sha256"]
                   for year, item in selection["test_prediction_files"].items()})
    output = {"fit_started_utc": started, "fit_completed_utc": now(), "sealed_before_evaluation": True,
              "selection_test_outcomes_accessed": selection["test_outcomes_accessed"],
              "file_sha256": sealed, "runtime_manifest_sha256": sha(PORTABLE / "runtime_manifest.json"),
              "comparison_contract_sha256": sha(CONTRACT)}
    write(PORTABLE / "fit_seal.json", output)
    print(json.dumps(output, indent=2))


def check_fit_seal():
    seal = read(PORTABLE / "fit_seal.json")
    if seal["selection_test_outcomes_accessed"] or not seal["sealed_before_evaluation"]:
        raise ValueError("Fit/evaluation separation failed.")
    for name, digest in seal["file_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("Current fitted artifact changed: " + name)
    return seal


def evaluate_stage():
    check_manifest()
    assert_prepared()
    seal = check_fit_seal()
    if (PORTABLE / "evaluation_started.json").exists():
        raise RuntimeError("Evaluation already started; preserve this run and investigate its existing receipt.")
    write(PORTABLE / "evaluation_started.json", {"started_utc": now(),
          "fit_seal_sha256": sha(PORTABLE / "fit_seal.json"), "model_refits_authorized": 0})
    with cohort_math() as proxy:
        invoke("scripts/evaluate_release.py")
        usage = proxy.receipt()
    invoke("scripts/build_reports.py")
    invoke("scripts/build_demo.py")
    invoke("tools/polish_demo_layout.py")
    invoke("scripts/verify_results.py")
    check_fit_seal()
    output = {"passed": True, "completed_utc": now(), "adapter": usage,
              "model_refits_during_evaluation": 0,
              "original_verification": read(ROOT / "reports/final_verification.json")}
    write(PORTABLE / "evaluation_receipt.json", output)
    print(json.dumps(output, indent=2))


def compare_stage():
    check_manifest()
    assert_prepared()
    check_fit_seal()
    if not read(PORTABLE / "evaluation_receipt.json")["passed"]:
        raise ValueError("Original verification did not pass.")
    spec = contract()
    old = {name: read(PORTABLE / "historical" / name) for name in spec["historical_file_sha256"]}
    new = {name: read(ROOT / "reports" / name) for name in spec["historical_file_sha256"]}
    comparisons = {name: compare(old[name], new[name], excluded=spec["metadata_exclusions"].get(name, ()),
                       atol=spec["numeric_rule"]["absolute_tolerance"], rtol=spec["numeric_rule"]["relative_tolerance"])
                   for name in old}
    strict = all(x["passed"] for x in comparisons.values())
    prediction_identity = {}
    for year, item in old["selection.json"]["test_prediction_files"].items():
        data = (ROOT / f"artifacts/predictions_{year}.csv").read_bytes()
        normalized = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        prediction_identity[year] = {"historical_sha256": item["sha256"],
                                    "current_sha256": hashlib.sha256(data).hexdigest(),
                                    "current_lf_normalized_sha256": normalized,
                                    "raw_bytes_match": hashlib.sha256(data).hexdigest() == item["sha256"],
                                    "lf_normalized_bytes_match": normalized == item["sha256"],
                                    "rowwise_difference_estimation": "Unavailable without historical private predictions when hashes differ."}
    model_identity = {name: sha(ROOT / "artifacts" / name) == digest
                      for name, digest in old["selection.json"]["models"].items()}
    selected_same = (old["selection.json"]["selected_variants"] == new["selection.json"]["selected_variants"]
                     and old["selection.json"]["recommended_family_from_validation"] ==
                         new["selection.json"]["recommended_family_from_validation"])
    decision = {"selection_identical": selected_same, "cohorts": {}}
    for year in ("2020", "2023"):
        prior = old["final_evaluation.json"]["cohorts"][year]
        current = new["final_evaluation.json"]["cohorts"][year]
        decision["cohorts"][year] = {
            "hgb_brier_advantage_remains": current["paired_brier"]["hgb_minus_logit"] < 0,
            "paired_interval_below_zero_remains": current["paired_brier"]["paired_percentile_95_interval"][1] < 0,
            "both_models_underpredict_remain": all(current["models"][f]["observed_expected_ratio"] > 1 for f in ("logit", "hgb")),
            "historical_decision_checks": {
                "hgb_brier_advantage": prior["paired_brier"]["hgb_minus_logit"] < 0,
                "paired_interval_below_zero": prior["paired_brier"]["paired_percentile_95_interval"][1] < 0,
                "both_models_underpredict": all(prior["models"][f]["observed_expected_ratio"] > 1 for f in ("logit", "hgb"))}}
    decision["restriction"] = "Historical research/ranking only; unchanged probabilities remain unsuitable for operational loss/capital use."
    output = {"completed_utc": now(), "comparison_contract_sha256": sha(CONTRACT),
              "strict_numerical_reproduction_passed": strict,
              "classification": "compatibility-assisted aggregate numerical reproduction" if strict else "completed cross-platform refit; strict numerical reproduction failed",
              "all_six_historical_prepared_tables_exact": True,
              "original_current_run_verification_passed": True,
              "scientific_file_comparisons": comparisons,
              "secondary_report_precision": report_precision(old, new, spec["secondary_report_precision_fields"]),
              "secondary_decision_assessment": decision,
              "prediction_serialization_identity": prediction_identity, "model_byte_identity": model_identity,
              "no_tolerance_widening_or_refitting": True}
    write(PORTABLE / "comparison.json", output)
    current_dir = PORTABLE / "current"
    current_dir.mkdir(exist_ok=True)
    for name in (*spec["historical_file_sha256"], "final_verification.json"):
        shutil.copyfile(ROOT / "reports" / name, current_dir / name)
    print(json.dumps({"classification": output["classification"], "strict_numerical_reproduction_passed": strict,
                      "differences": {name: len(item["differences"]) for name, item in comparisons.items()},
                      "report_precision_passed": output["secondary_report_precision"]["passed"],
                      "decision": decision}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "fit", "evaluate", "compare"))
    args = parser.parse_args()
    os.chdir(ROOT)
    started = time.monotonic()
    globals()[args.stage + "_stage"]()
    print(json.dumps({"stage": args.stage, "elapsed_seconds": time.monotonic()-started}))
