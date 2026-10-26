"""Windows verification v1: a current refit, distinct from historical reproduction.

The strict portable workflow and its failed historical gate remain unchanged.
This entrypoint adds an explicit prospective protocol and current-input seal.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

import portable_reproduction as p
from portable_compare import compare, report_precision
from mortgage_risk.portable_log1p import cohort_math

ROOT = p.ROOT
OUT = ROOT / "reports/windows_verification_v1"
PROTOCOL = ROOT / "compatibility/windows_verification_v1.json"


def protocol():
    return p.read(PROTOCOL)


def current_inputs():
    spec = protocol()
    actual = {name: p.sha(ROOT / "data/prepared" / name) for name in spec["current_prepared_sha256"]}
    if actual != spec["current_prepared_sha256"]:
        raise ValueError("Current Windows input bytes differ from the new protocol.")
    historic = p.contract()["historical_prepared_sha256"]
    unmatched = sorted(name for name in actual if actual[name] != historic[name])
    if unmatched != sorted(spec["historical_gate"]["unmatched_tables"]):
        raise ValueError("Historical byte-gate status changed unexpectedly.")
    prepared = p.read(ROOT / "reports/preparation.json")
    baseline = p.read(p.PORTABLE / "historical/preparation.json")
    for old, new in zip(baseline["prepared"], prepared["prepared"]):
        if {k:v for k,v in old.items() if k != "private_table_sha256"} != {k:v for k,v in new.items() if k != "private_table_sha256"}:
            raise ValueError("Preparation count/role/label access metadata changed.")
    if len(prepared["prepared"]) != 6 or prepared["test_outcomes_accessed"]:
        raise ValueError("Prepared test separation failed.")
    if not prepared["original_2012_byte_regression"]:
        raise ValueError("Original 2012 regression gate did not pass.")
    for item in prepared["prepared"]:
        name = f'{item["role"]}_{item["year"]}.csv'
        if item["private_table_sha256"] != actual[name]:
            raise ValueError("Original preparation receipt differs from current tables.")
    return actual, unmatched


def prepare_new():
    """Fresh-checkout route; preserve the failed strict gate, then verify new inputs."""
    if (p.PORTABLE / "runtime_manifest.json").exists():
        raise RuntimeError("Preparation already exists; preserve it and use authorize only after completed independent checks.")
    try:
        p.prepare_stage()
    except ValueError as exc:
        if str(exc) != "At least one of the six historical prepared-table hashes differs.":
            raise
        # This is an explicit alternative protocol, not a changed historical gate.
        current_inputs()
        p.write(OUT / "historical_exact_gate.json", {"passed": False,
                "original_error": str(exc), "matched": 4, "required": 6,
                "unmatched": protocol()["historical_gate"]["unmatched_tables"],
                "full_fits_started": 0})
    else:
        raise RuntimeError("Historical inputs matched; use the strict portable workflow instead of this Windows-specific protocol.")
    p.invoke("scripts/windows_input_checks.py")
    shutil.copyfile(p.PORTABLE / "test_results.json", p.PORTABLE / "windows_tests.json")
    authorize()


def authorize():
    if (ROOT / "artifacts/training_started.json").exists() or (OUT / "prefit_manifest.json").exists():
        raise RuntimeError("Current inputs must be sealed before fitting; do not replace an existing seal.")
    p.check_manifest()
    spec = protocol()
    if p.sha(p.CONTRACT) != spec["historical_comparison_contract_sha256"]:
        raise ValueError("Historical comparison contract was changed.")
    hashes, unmatched = current_inputs()
    checks = p.read(p.PORTABLE / "windows_input_checks.json")
    if not checks["passed"] or not checks["all_six_numeric_checks"]["passed"] or not all(
            x["passed"] for x in checks["two_unmatched_tables_raw_reconstruction"]):
        raise ValueError("Independent current-input checks failed.")
    if checks["all_six_numeric_checks"]["log_cells_checked"] != 530890 or checks["all_six_numeric_checks"]["balance_ratios_checked"] != 265445:
        raise ValueError("Independent checks did not cover all current rows.")
    if checks["checker_sha256"] != p.sha(ROOT / "scripts/windows_input_checks.py") or checks["current_prepared_sha256"] != hashes:
        raise ValueError("Independent check source/input identity differs.")
    tests = p.read(p.PORTABLE / "windows_tests.json")
    if not tests["passed"]:
        raise ValueError("Windows input-check regression tests failed.")
    caches = p.verify_caches(ROOT, verify_only=True)
    p.invoke("scripts/check_data_ready.py", ["--source-dir", ROOT / "data/raw",
                                           "--report", ROOT / "reports/source_readiness.json"])
    receipt = {"sealed_utc": p.now(), "protocol_version": spec["protocol_version"],
               "classification": spec["classification"], "protocol_sha256": p.sha(PROTOCOL),
               "comparison_contract_sha256": p.sha(p.CONTRACT),
               "current_prepared_sha256": hashes,
               "historical_exact_gate": {"passed": False, "matched": 4, "required": 6, "unmatched": unmatched,
                                         "fits_started_before_new_protocol": 0},
               "original_2012_gate_unchanged_and_passed": True,
               "original_method_files": p.check_methods(),
               "execution_file_sha256": p.execution_files(),
               "runtime": p.check_environment(), "cache_verification": caches,
               "preparation_sha256": p.sha(ROOT / "reports/preparation.json"),
               "independent_input_checks_sha256": p.sha(p.PORTABLE / "windows_input_checks.json"),
               "windows_test_receipt_sha256": p.sha(p.PORTABLE / "windows_tests.json"),
               "original_test_receipt_sha256": p.sha(p.PORTABLE / "test_results.json"),
               "prior_exact_attempt_manifest_sha256": p.sha(p.PORTABLE / "runtime_manifest.json"),
               "full_fit_budget": 4, "intercept_fit_budget": 2}
    p.write(OUT / "prefit_manifest.json", receipt)
    (OUT / "prefit_manifest.sha256").write_text(p.sha(OUT / "prefit_manifest.json")+"\n", encoding="ascii")
    shutil.copyfile(p.PORTABLE / "windows_input_checks.json", OUT / "input_checks.json")
    print(json.dumps({"passed": True, "new_current_input_seal_sha256": p.sha(OUT / "prefit_manifest.json"),
                      "historical_gate": receipt["historical_exact_gate"], "full_fits_started": 0}, indent=2))


def check_current():
    path = OUT / "prefit_manifest.json"
    if p.sha(path) != (OUT / "prefit_manifest.sha256").read_text().strip():
        raise ValueError("Windows pre-fit manifest changed.")
    manifest = p.read(path)
    p.check_manifest()
    current_inputs()
    if p.sha(PROTOCOL) != manifest["protocol_sha256"] or p.sha(p.CONTRACT) != manifest["comparison_contract_sha256"]:
        raise ValueError("A prospective protocol or comparison rule changed.")
    if p.sha(ROOT / "reports/preparation.json") != manifest["preparation_sha256"]:
        raise ValueError("Prepared input receipt changed.")
    for name, digest in manifest["execution_file_sha256"].items():
        if p.sha(ROOT / name) != digest:
            raise ValueError("Windows execution source changed: " + name)
    if p.check_environment() != manifest["runtime"]:
        raise ValueError("Windows execution environment differs from its pre-fit seal.")
    if p.sha(p.PORTABLE / "windows_input_checks.json") != manifest["independent_input_checks_sha256"]:
        raise ValueError("Independent input receipt changed.")
    return manifest


def fit():
    check_current()
    started = p.now()
    p.invoke("scripts/fit_and_seal.py")
    selection = p.read(ROOT / "reports/selection.json")
    if (selection["full_fits"], selection["intercept_fits"]) != (4, 2) or selection["test_outcomes_accessed"]:
        raise ValueError("Fixed fit budget or test separation failed.")
    files = {"reports/selection.json": p.sha(ROOT / "reports/selection.json")}
    files.update({"artifacts/"+name: digest for name,digest in selection["models"].items()})
    files.update({f"artifacts/predictions_{year}.csv": item["sha256"]
                  for year,item in selection["test_prediction_files"].items()})
    receipt = {"fit_started_utc": started, "sealed_utc": p.now(), "file_sha256": files,
               "test_outcomes_accessed": False, "full_fits": 4, "intercept_fits": 2,
               "prefit_manifest_sha256": p.sha(OUT / "prefit_manifest.json"),
               "comparison_contract_sha256": p.sha(p.CONTRACT)}
    p.write(OUT / "fit_seal.json", receipt)
    print(json.dumps(receipt, indent=2))


def check_fit():
    receipt = p.read(OUT / "fit_seal.json")
    if receipt["test_outcomes_accessed"] or receipt["prefit_manifest_sha256"] != p.sha(OUT / "prefit_manifest.json"):
        raise ValueError("Current fit/evaluation separation failed.")
    for name,digest in receipt["file_sha256"].items():
        if p.sha(ROOT / name) != digest:
            raise ValueError("New fitted artifact changed: " + name)
    return receipt


def evaluate():
    check_current()
    check_fit()
    if (OUT / "evaluation_started.json").exists():
        raise RuntimeError("Evaluation already started. Preserve its evidence and diagnose instead of repeating.")
    p.write(OUT / "evaluation_started.json", {"started_utc": p.now(),
            "fit_seal_sha256": p.sha(OUT / "fit_seal.json"), "refits_authorized": 0})
    with cohort_math() as proxy:
        p.invoke("scripts/evaluate_release.py")
        usage = proxy.receipt()
    for name in ("scripts/build_reports.py", "scripts/build_demo.py",
                 "tools/polish_demo_layout.py", "scripts/verify_results.py"):
        p.invoke(name)
    check_fit()
    p.write(OUT / "evaluation_receipt.json", {"passed": True, "completed_utc": p.now(),
            "adapter": usage, "model_refits": 0,
            "original_internal_verification": p.read(ROOT / "reports/final_verification.json")})
    print(json.dumps({"passed": True, "model_refits": 0, "original_verification_passed": True}))


def compare_outputs():
    check_current()
    check_fit()
    if not p.read(OUT / "evaluation_receipt.json")["passed"]:
        raise ValueError("Original evaluation/verification did not pass.")
    spec = p.contract()
    old = {name:p.read(p.PORTABLE / "historical" / name) for name in spec["historical_file_sha256"]}
    new = {name:p.read(ROOT / "reports" / name) for name in spec["historical_file_sha256"]}
    results = {name:compare(old[name],new[name],excluded=spec["metadata_exclusions"].get(name,()),
               atol=spec["numeric_rule"]["absolute_tolerance"],rtol=spec["numeric_rule"]["relative_tolerance"])
               for name in old}
    numeric_differences = []
    discrete_differences = []
    for name, result in results.items():
        for diff in result["differences"]:
            item = {"file":name, **diff}
            if diff["kind"] == "float":
                numeric_differences.append(item)
            if isinstance(diff.get("historical"), (int,bool)) and diff["kind"] in ("exact","type"):
                discrete_differences.append(item)
    predictions = {}
    for year,item in old["selection.json"]["test_prediction_files"].items():
        data = (ROOT/f"artifacts/predictions_{year}.csv").read_bytes()
        raw = hashlib.sha256(data).hexdigest()
        lf = hashlib.sha256(data.replace(b"\r\n",b"\n")).hexdigest()
        predictions[year] = {"historical_sha256":item["sha256"],"current_sha256":raw,
                             "current_lf_normalized_sha256":lf,"raw_bytes_match":raw==item["sha256"],
                             "lf_normalized_bytes_match":lf==item["sha256"],
                             "rowwise_difference_estimation":"Unavailable without historical private predictions when hashes differ."}
    selection_same = (old["selection.json"]["selected_variants"] == new["selection.json"]["selected_variants"]
                       and old["selection.json"]["recommended_family_from_validation"] == new["selection.json"]["recommended_family_from_validation"])
    decisions = {"selection_identical":selection_same,"cohorts":{}}
    for year in ("2020","2023"):
        current = new["final_evaluation.json"]["cohorts"][year]
        decisions["cohorts"][year] = {
            "hgb_brier_advantage_remains":current["paired_brier"]["hgb_minus_logit"]<0,
            "paired_interval_below_zero_remains":current["paired_brier"]["paired_percentile_95_interval"][1]<0,
            "both_models_underpredict_remain":all(current["models"][f]["observed_expected_ratio"]>1 for f in ("logit","hgb"))}
    decisions["restriction"] = "Historical research/ranking only; unchanged probabilities are unsuitable for operational loss/capital use."
    result = {"completed_utc":p.now(),"classification":protocol()["classification"],
              "historical_exact_input_gate_passed":False,
              "original_current_run_internal_verification_passed":True,
              "full_historical_11_json_comparison_passed":all(x["passed"] for x in results.values()),
              "comparison_contract_sha256":p.sha(p.CONTRACT),
              "scientific_file_comparisons":results,
              "numeric_only_assessment":{"passed":not numeric_differences,
                  "scope":"All floating scientific leaves of the same 11 JSON files, unchanged abs+rel 1e-10 rule; does not establish historical input or rowwise equivalence.",
                  "floating_leaves_compared":sum(x["counts"]["scientific_numbers"] for x in results.values()),
                  "differences":numeric_differences},
              "exact_discrete_numeric_assessment":{"passed":not discrete_differences,
                  "integer_boolean_leaves_compared":sum(x["counts"]["integer_or_boolean_leaves"] for x in results.values()),
                  "differences":discrete_differences},
              "secondary_report_precision":report_precision(old,new,spec["secondary_report_precision_fields"]),
              "secondary_decision_assessment":decisions,
              "prediction_serialization_identity":predictions,
              "model_byte_identity":{name:p.sha(ROOT/"artifacts"/name)==digest for name,digest in old["selection.json"]["models"].items()},
              "no_tolerance_widening_or_refitting":True}
    p.write(OUT/"comparison.json",result)
    current = OUT/"current";current.mkdir(exist_ok=True)
    for name in (*spec["historical_file_sha256"],"final_verification.json"):
        shutil.copyfile(ROOT/"reports"/name,current/name)
    print(json.dumps({"historical_exact_gate_passed":False,
                      "current_internal_verification_passed":True,
                      "numeric_only_passed":result["numeric_only_assessment"]["passed"],
                      "numeric_differences":len(numeric_differences),
                      "discrete_numeric_passed":not discrete_differences,
                      "report_precision_passed":result["secondary_report_precision"]["passed"],
                      "decision":decisions},indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("prepare","authorize","fit","evaluate","compare"))
    args=parser.parse_args()
    os.chdir(ROOT)
    started=time.monotonic()
    {"prepare":prepare_new,"authorize":authorize,"fit":fit,"evaluate":evaluate,"compare":compare_outputs}[args.stage]()
    print(json.dumps({"stage":args.stage,"elapsed_seconds":time.monotonic()-started}))
