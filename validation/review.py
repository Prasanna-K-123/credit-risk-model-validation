"""Independent review of frozen scores; never fits or selects a candidate model.

The original study implements its own tie-correct ROC/AP calculations. This
review uses scikit-learn metrics and pandas ranking/grouping as a separate
implementation, and checks every final annual cohort and every failed bank.
Governance thresholds are explicitly post-hoc review controls, not registration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


MODELS = (
    "constant", "capital_only", "logistic_raw", "logistic_calibrated",
    "hist_gradient_boosting_raw", "hist_gradient_boosting_calibrated",
)
PRIMARY = "hist_gradient_boosting_calibrated"
FEATURES = (
    "equity_to_assets", "loans_to_assets", "deposits_to_assets", "cash_to_assets",
    "securities_to_assets", "nonperforming_assets_fraction",
    "return_on_assets_fraction", "net_interest_margin_fraction", "log_assets",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integral_count(value, label: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)) or not np.isfinite(value) or value < 0 or value != np.floor(value):
        raise ValueError("Invalid integral count: " + label)
    return int(value)


def evidence_boolean(value, label: str) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError("Malformed boolean evidence: " + label)
    return bool(value)


def verify_reference(reference: Path) -> None:
    root = reference.parents[1].resolve()
    manifest = json.loads((reference / "artifact_manifest.json").read_text())
    for entry in manifest["artifacts"] + manifest["frozen_source"] + manifest["packaging_source"]:
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
            raise ValueError("Changed frozen input: " + entry["path"])


def check_predictions(frame: pd.DataFrame) -> None:
    required = {"CERT", "report_date", "prediction_date", "horizon_end", "failure",
                "failure_date", "nonfailure_exit", *("p_" + name for name in MODELS)}
    if set(frame.columns) != required or frame.empty:
        raise ValueError("Exact nonempty frozen prediction schema required")
    cert = frame.CERT.to_numpy()
    if not np.issubdtype(cert.dtype, np.number) or not np.isfinite(cert).all() or (cert <= 0).any() or not (cert == np.floor(cert)).all():
        raise ValueError("Certificate must be a positive integer")
    if frame.duplicated(["CERT", "report_date"]).any():
        raise ValueError("Duplicate certificate/report key")
    for column in ("failure", "nonfailure_exit"):
        if not frame[column].isin([0, 1]).all():
            raise ValueError("Binary outcome/exit indicators required")
    if ((frame.failure == 1) & (frame.nonfailure_exit == 1)).any():
        raise ValueError("Failure and competing nonfailure exit cannot coincide")
    for row in frame[["report_date", "prediction_date", "horizon_end", "failure_date", "failure"]].itertuples(index=False):
        report, prediction, horizon = [date.fromisoformat(str(v)) for v in row[:3]]
        if (report.month, report.day) != (12, 31) or prediction != date(report.year + 1, 4, 1) or horizon != date(report.year + 2, 4, 1):
            raise ValueError("Invalid annual report/prediction/horizon ordering")
        event = None if pd.isna(row.failure_date) or row.failure_date == "" else date.fromisoformat(str(row.failure_date))
        if bool(row.failure) != bool(event is not None and prediction < event <= horizon):
            raise ValueError("Failure label disagrees with event horizon")
    p = frame[["p_" + name for name in MODELS]].to_numpy(dtype=float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Finite probabilities in [0,1] required")


def metrics(y, p, threshold: float, false_negative_weight: float = 100.0) -> dict:
    y, p = np.asarray(y), np.asarray(p, dtype=float)
    if y.ndim != 1 or y.size == 0 or p.shape != y.shape or not np.isin(y, [0, 1]).all():
        raise ValueError("Aligned nonempty binary labels required")
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Invalid probability")
    if not np.isfinite(threshold) or not 0 <= threshold <= np.nextafter(1.0, np.inf):
        raise ValueError("Invalid policy threshold")
    if not np.isfinite(false_negative_weight) or false_negative_weight <= 0:
        raise ValueError("Invalid illustrative error weight")
    decision = p >= threshold
    caught = int(np.count_nonzero(decision & (y == 1)))
    missed = int(np.count_nonzero(~decision & (y == 1)))
    false_positives = int(np.count_nonzero(decision & (y == 0)))
    clipped = np.clip(p, 1e-8, 1 - 1e-8)  # Original registered log-loss convention.
    two_classes = len(np.unique(y)) == 2
    return {
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(np.mean(-np.where(y == 1, np.log(clipped), np.log1p(-clipped)))),
        "auc": float(roc_auc_score(y, p)) if two_classes else None,
        "average_precision": float(average_precision_score(y, p)) if two_classes else None,
        "weighted_cost_per_row": float((false_negative_weight * missed + false_positives) / len(y)),
        "test_monitor_count": int(decision.sum()),
        "test_caught_failures": caught,
        "test_missed_failures": missed,
        "false_positives": false_positives,
        "expected_failures": float(p.sum()),
        "observed_failures": int(y.sum()),
        "observed_expected_ratio": float(y.sum() / p.sum()) if p.sum() > 0 else None,
    }


def annual_review(frame: pd.DataFrame, name: str, threshold: float) -> list[dict]:
    rows = []
    for when, group in frame.groupby("prediction_date", sort=True):
        # Separate pandas stable multi-key ranking, rather than the frozen lexsort.
        top = group.sort_values(["p_" + name, "CERT"], ascending=[False, True], kind="mergesort")
        capacity = (len(group) + 99) // 100
        top = top.iloc[:capacity]
        scores = metrics(group.failure, group["p_" + name], threshold)
        caught = int(top.failure.sum())
        failures = int(group.failure.sum())
        rows.append({
            "prediction_date": when, "model": name, "rows": len(group),
            "failures": failures, "nonfailure_exits": int(group.nonfailure_exit.sum()),
            "review_capacity": capacity, "captured_failures_at_capacity": caught,
            "precision_at_capacity": caught / capacity,
            "recall_at_capacity": caught / failures if failures else None,
            **scores,
        })
    return rows


def assert_equal(actual, expected, label: str) -> None:
    if expected is None or (isinstance(expected, float) and np.isnan(expected)):
        if actual is not None:
            raise ValueError(f"Unexpected defined diagnostic: {label}")
    elif isinstance(expected, (int, np.integer)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, np.integer)) or actual != expected:
            raise ValueError(f"Count changed: {label}")
    elif isinstance(expected, (float, np.floating)):
        if actual is None or not np.isfinite(actual) or not np.isclose(actual, expected, rtol=1e-10, atol=1e-12):
            raise ValueError(f"Numeric disagreement: {label}")
    elif actual != expected:
        raise ValueError(f"Identity changed: {label}")


def feature_psi(training, later, bins: int = 10, pseudocount: float = 0.5) -> dict:
    """Training-defined quantiles; an explicit missing bucket; no test quantiles.

    Half-count smoothing avoids infinite diagnostics for finite empty buckets.
    PSI is descriptive distribution shift, not a calibrated hypothesis test.
    """
    a, b = np.asarray(training, dtype=float), np.asarray(later, dtype=float)
    if a.ndim != 1 or b.ndim != 1 or len(a) == 0 or len(b) == 0 or bins < 2 or not np.isfinite(pseudocount) or pseudocount <= 0:
        raise ValueError("Nonempty samples, bins >=2 and positive smoothing required")
    if np.isinf(a).any() or np.isinf(b).any() or not np.isfinite(a).any():
        raise ValueError("Finite training support required; infinity is not missing")
    edges = np.r_[-np.inf, np.unique(np.quantile(a[np.isfinite(a)], np.arange(1, bins) / bins)), np.inf]
    acount = np.r_[np.histogram(a[np.isfinite(a)], bins=edges)[0], np.isnan(a).sum()]
    bcount = np.r_[np.histogram(b[np.isfinite(b)], bins=edges)[0], np.isnan(b).sum()]
    afrac = (acount + pseudocount) / (len(a) + pseudocount * len(acount))
    bfrac = (bcount + pseudocount) / (len(b) + pseudocount * len(bcount))
    contributions = (bfrac - afrac) * np.log(bfrac / afrac)
    return {"psi": float(contributions.sum()), "training_rows": len(a), "later_rows": len(b),
            "finite_inner_edges": edges[1:-1].tolist(), "last_bucket": "missing",
            "training_counts": acount.tolist(), "later_counts": bcount.tolist(),
            "pseudocount": pseudocount, "contributions": contributions.tolist()}


@dataclass(frozen=True)
class ReviewPolicy:
    max_brier: float = 0.20
    max_feature_psi: float = 0.20
    minimum_late_recall: float = 0.50
    require_no_worse_than_constant: bool = True
    require_actual_vintages: bool = True

    def __post_init__(self):
        if not all(not isinstance(v, bool) and np.isfinite(v) for v in (self.max_brier, self.max_feature_psi, self.minimum_late_recall)):
            raise ValueError("Policy thresholds must be finite")
        if not 0 <= self.max_brier <= 1 or self.max_feature_psi < 0 or not 0 <= self.minimum_late_recall <= 1:
            raise ValueError("Invalid review policy threshold")
        if type(self.require_no_worse_than_constant) is not bool or type(self.require_actual_vintages) is not bool:
            raise ValueError("Policy requirements must be boolean")


def govern(diagnostics: dict, policy: ReviewPolicy = ReviewPolicy()) -> dict:
    required = {"brier", "constant_brier", "max_feature_psi", "late_recall", "actual_vintages"}
    missing = sorted(k for k in required if k not in diagnostics or diagnostics[k] is None)
    findings = [{"rule": key, "kind": "missing", "message": "Required diagnostic unavailable; never treated as passing."} for key in missing]
    for key in required - set(missing) - {"actual_vintages"}:
        value = diagnostics[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError("Nonfinite or invalid diagnostic: " + key)
        if value < 0 or (key != "max_feature_psi" and value > 1):
            raise ValueError("Out-of-domain diagnostic: " + key)
    if "actual_vintages" not in missing and type(diagnostics["actual_vintages"]) is not bool:
        raise ValueError("Vintage evidence must be boolean or missing")
    checks = [
        ("brier", lambda: diagnostics["brier"] > policy.max_brier, "Brier score exceeds the declared absolute ceiling."),
        ("max_feature_psi", lambda: diagnostics["max_feature_psi"] > policy.max_feature_psi, "Feature distribution shift exceeds the illustrative review trigger."),
        ("late_recall", lambda: diagnostics["late_recall"] < policy.minimum_late_recall, "Later-cohort monitoring recall is below the illustrative review floor."),
        ("actual_vintages", lambda: policy.require_actual_vintages and not diagnostics["actual_vintages"], "Original information vintages/publication times are not established."),
    ]
    for key, fails, message in checks:
        if key not in missing and fails():
            findings.append({"rule": key, "kind": "restriction", "message": message})
    if policy.require_no_worse_than_constant and not ({"brier", "constant_brier"} & set(missing)) and diagnostics["brier"] > diagnostics["constant_brier"]:
        findings.append({"rule": "brier_vs_constant", "kind": "restriction", "message": "Brier score is worse than the constant development-rate baseline."})
    return {"status": "INCOMPLETE_EVIDENCE" if missing else ("RESTRICTED_RESEARCH" if findings else "RESEARCH_REVIEW_NO_CONFIGURED_TRIGGER"),
            "policy": asdict(policy), "diagnostics": diagnostics, "findings": findings,
            "scope": "Post-hoc illustrative review controls added 2026-10-28; no regulatory approval, new holdout, model reselection or deployment authorization."}


def review(reference: Path, panel: pd.DataFrame) -> dict:
    verify_reference(reference)
    summary = json.loads((reference / "summary.json").read_text())
    expected_hash = summary["test_predictions_sha256"]
    import gzip
    prediction_bytes = gzip.decompress((reference / "test_predictions.csv.gz").read_bytes())
    if hashlib.sha256(prediction_bytes).hexdigest() != expected_hash:
        raise ValueError("Frozen prediction content hash mismatch")
    import io
    frame = pd.read_csv(io.BytesIO(prediction_bytes), float_precision="round_trip")
    check_predictions(frame)
    assert_equal(len(frame), summary["population"]["test"]["rows"], "test rows")
    assert_equal(int(frame.failure.sum()), summary["population"]["test"]["failure_events"], "test events")
    actual_test = panel.loc[panel.role.eq("test")].reset_index(drop=True)
    if not frame[["CERT", "report_date", "prediction_date", "horizon_end", "failure", "nonfailure_exit"]].equals(actual_test[["CERT", "report_date", "prediction_date", "horizon_end", "failure", "nonfailure_exit"]]):
        raise ValueError("Scores do not correspond to the rebuilt source panel")
    cohort = pd.read_csv(reference / "cohort_diagnostics.csv", float_precision="round_trip")
    if len(cohort) != len(MODELS) * frame.prediction_date.nunique() or cohort.duplicated(["prediction_date", "model"]).any():
        raise ValueError("Cohort evidence missing or duplicated")
    failures = pd.read_csv(reference / "failure_cases.csv", float_precision="round_trip")
    expected_failures = frame.loc[frame.failure.eq(1)].reset_index(drop=True)
    if not failures[["CERT", "prediction_date", "failure_date"]].equals(expected_failures[["CERT", "prediction_date", "failure_date"]]):
        raise ValueError("Failure-case evidence is incomplete or reordered")
    models, checks = {}, 0
    for name in MODELS:
        frozen = summary["test_metrics"][name]
        result = metrics(frame.failure, frame["p_" + name], frozen["threshold"])
        for key in ("brier", "log_loss", "auc", "average_precision", "weighted_cost_per_row", "test_monitor_count", "test_caught_failures", "test_missed_failures"):
            assert_equal(result[key], frozen[key], name + "/" + key); checks += 1
        annual = annual_review(frame, name, frozen["threshold"])
        for row in annual:
            saved = cohort.loc[cohort.model.eq(name) & cohort.prediction_date.eq(row["prediction_date"])].iloc[0]
            for key in ("rows", "failures", "nonfailure_exits", "review_capacity", "captured_failures_at_capacity", "precision_at_capacity", "recall_at_capacity", "brier", "log_loss", "weighted_cost_per_row", "auc", "average_precision"):
                expected = saved[key]
                if key in {"rows", "failures", "nonfailure_exits", "review_capacity", "captured_failures_at_capacity"}: expected = integral_count(expected, key)
                assert_equal(row[key], expected, name + "/" + row["prediction_date"] + "/" + key); checks += 1
        late = frame.loc[frame.prediction_date.ge("2022-04-01")]
        late_result = metrics(late.failure, late["p_" + name], frozen["threshold"])
        final_cases = []
        for when, group in frame.groupby("prediction_date", sort=True):
            top = group.sort_values(["p_" + name, "CERT"], ascending=[False, True], kind="mergesort").iloc[:(len(group) + 99) // 100]
            selected_ids = set(top.CERT)
            for case in group.loc[group.failure.eq(1)].to_dict("records"):
                saved = failures.loc[failures.CERT.eq(case["CERT"]) & failures.prediction_date.eq(when)].iloc[0]
                monitoring = bool(case["p_" + name] >= frozen["threshold"])
                at_capacity = case["CERT"] in selected_ids
                assert_equal(float(case["p_" + name]), float(saved["p_" + name]), "failure score"); checks += 1
                if monitoring != evidence_boolean(saved["monitor_" + name], "monitor flag") or at_capacity != evidence_boolean(saved["top_1pct_" + name], "capacity flag"):
                    raise ValueError("Failure-case monitoring/ranking disagreement")
                checks += 2
                final_cases.append({"certificate": int(case["CERT"]), "prediction_date": when, "failure_date": case["failure_date"],
                                    "probability": float(case["p_" + name]), "monitored": monitoring, "top_one_percent": at_capacity})
        models[name] = {"overall": result, "threshold": frozen["threshold"], "annual": annual, "failure_cases": final_cases,
                        "late_posthoc": {"rows": len(late), **late_result}}
    training = panel.loc[panel.role.eq("development")]
    drift = {name: feature_psi(training[name], actual_test[name]) for name in FEATURES}
    primary = models[PRIMARY]
    governance = govern({"brier": primary["overall"]["brier"], "constant_brier": models["constant"]["overall"]["brier"],
                         "max_feature_psi": max(v["psi"] for v in drift.values()),
                         "late_recall": primary["late_posthoc"]["test_caught_failures"] / primary["late_posthoc"]["observed_failures"],
                         "actual_vintages": False})
    return {"version": "bank-review-v1", "predictions_sha256": expected_hash,
            "population": summary["population"], "source_protocol_sha256": summary["protocol_sha256"],
            "independent_numeric_and_case_checks": checks, "models": models, "feature_drift": drift,
            "governance": governance, "paired_uncertainty": summary["paired_uncertainty"],
            "scope": {"independence": "Independent metric/ranking/review implementation within this portfolio, not independent institutional approval. Source panel uses the hash-checked frozen builder.",
                      "late_cohorts": "2022–2025 prediction cohorts are post hoc descriptive diagnostics, not a new untouched holdout.",
                      "drift": "Post-hoc training-defined decile PSI, half-count smoothing and missing bucket; descriptive, no calibrated significance test.",
                      "uncertainty": "Original paired bank and annual-cohort bootstrap intervals, separately replayed; neither jointly models all dependence or fitting uncertainty."}}
