"""Build the public narrative and self-contained explorer from verified evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"constant": "Development-rate baseline", "capital_only": "Capital-only logistic",
          "logistic_raw": "Full logistic, raw", "logistic_calibrated": "Full logistic, calibrated",
          "hist_gradient_boosting_raw": "Boosting, raw", "hist_gradient_boosting_calibrated": "Boosting, calibrated"}


def render() -> dict[str, str]:
    raw = (ROOT / "reports/independent_review.json").read_bytes()
    evidence = json.loads(raw)
    receipt = json.loads((ROOT / "reports/execution_receipt.json").read_text())
    if receipt["status"] != "passed" or hashlib.sha256(raw).hexdigest() != receipt["review_sha256"]:
        raise ValueError("Presentation requires a passed execution receipt bound to these review bytes")
    primary = evidence["models"]["hist_gradient_boosting_calibrated"]
    overall, late = primary["overall"], primary["late_posthoc"]
    stamp = receipt["completed_at_utc"][:10]
    table = "| Model | ROC AUC | Average precision | Brier | Fixed-rule caught / 35 | Monitored |\n|---|---:|---:|---:|---:|---:|\n"
    for name, model in evidence["models"].items():
        m = model["overall"]
        table += f"| {LABELS[name]} | {m['auc']:.6f} | {m['average_precision']:.6f} | {m['brier']:.9f} | {m['test_caught_failures']} | {m['test_monitor_count']} |\n"
    phases = "| Role | Report years | Bank-year rows | Failure events | Last outcome horizon |\n|---|---|---:|---:|---|\n"
    years = {"development": "1992–2005", "selection": "2007–2008", "calibration": "2010", "policy": "2012", "test": "2014–2024"}
    for role, row in evidence["population"].items():
        phases += f"| {role} | {years[role]} | {row['rows']:,} | {row['failure_events']} | {row['latest_horizon']} |\n"
    drift = "| Predictor | Training-to-final PSI |\n|---|---:|\n"
    for name, item in sorted(evidence["feature_drift"].items(), key=lambda p: -p[1]["psi"]):
        drift += f"| {name} | {item['psi']:.6f} |\n"
    uncertainty = "| Resampling unit | Difference in Brier, 95% interval | Difference in illustrative cost, 95% interval |\n|---|---|---|\n"
    for unit, u in evidence["paired_uncertainty"].items():
        b = u["metrics"]["brier"]["percentile_95"]
        c = u["metrics"]["weighted_cost_per_row"]["percentile_95"]
        uncertainty += f"| {unit} | [{b[0]:.9f}, {b[1]:.9f}] | [{c[0]:.6f}, {c[1]:.6f}] |\n"
    report = f"""# Bank-risk validation: pooled performance and later monitoring failure

Current execution: {stamp}. This is a second implementation of metric and decision checks within one research portfolio, not an independent institutional opinion or regulatory approval.

## Decision and intended user

A model reviewer asks whether a historical bank-failure model supports its intended monitoring rule. **Restrict the fixed model to retrospective research and challenge analysis.** Its calibrated booster has pooled AUC {overall['auc']:.6f}, but missed {late['test_missed_failures']} of {late['observed_failures']} failures in the later 2022–2025 prediction cohorts. A better pooled score does not establish a reliable operating policy.

The later slice was selected for descriptive investigation after seeing annual results. It is **post hoc**, not a new untouched test. It is retained to expose a failure mode, not to tune a replacement model.

## Data lineage and target

The frozen snapshot contains 29 December financial extracts, the FDIC institution registry and failure/assistance records. From these, the actual source builder reconstructs {receipt['eligible_rows']:,} eligible bank-year observations. Its exclusions and event coverage are recorded in [eligibility_audit.json](../bank_monitoring/reference/fdic_temporal/eligibility_audit.json). Integrity checks bind source bytes, schema, predictor whitelist, protocol, roles and final row identities.

The target is certificate failure during (April 1, next April 1], with nonfailure closure/insurance exit as a competing outcome. It is not borrower default, borrower PD/LGD, loss severity, IFRS 9 adequacy or a current bank rating. Reports are assumed available three months after December 31; original publication timestamps and contemporary revisions are not reconstructed. The pinned objects are later-revised historical values. These limitations prevent a point-in-time prospective-performance claim.

{phases}

Role boundaries include purged years so earlier outcome horizons precede later role prediction dates. Repeated certificates across time are intentional. This measures temporal transport among the eligible historical institutions, not generalization to unseen banks. Registry matching, known origin/insurance dates, inactive dates and positive assets determine eligibility; the exclusions remain part of the population definition.

## Models and choices made before final scoring

The constant development-event-rate and capital-only logistic models are baselines. Full logistic uses training-only median imputation/robust scaling and C candidates 0.01, 0.1 and 1.0. Histogram boosting uses native missing routing and 7, 15 or 31 leaves, with fixed iteration, learning-rate and regularization settings. Both families use the same development rows; selection minimizes separate-year log loss. The selected values are C=0.1 and 7 leaves. No final-score model reselection occurs.

Two monotone logistic calibrators are fit only on the calibration year. The policy year chooses an illustrative cost-minimizing threshold with a false-negative weight of 100 and false-positive weight of 1; exact ties prefer less monitoring. These weights are scenarios, not measured bank financial losses or estimated intervention benefits. Annual top-1% review is a separate descriptive capacity diagnostic with public certificate ID tie-breaking.

## Results: keep ranking, calibration and decisions separate

{table}

The calibrated booster predicts {overall['expected_failures']:.4f} failures versus {overall['observed_failures']} observed over all final rows. Its fixed rule monitors {overall['test_monitor_count']} observations, catches {overall['test_caught_failures']} failures and generates {overall['false_positives']} false positives. In the later post-hoc slice it predicts {late['expected_failures']:.4f} failures versus {late['observed_failures']} observed and catches only {late['test_caught_failures']}. Overall calibration can conceal severe cohort-specific problems.

The constant baseline has average precision equal to the final prevalence (approximately 0.000605). Average precision is therefore reported alongside ROC AUC, avoiding a ranking-only story in a very rare-event population. Zero-failure annual cohorts retain undefined ROC/AP rather than receiving invented perfect scores.

## Uncertainty

The original registered comparison is calibrated boosting minus calibrated full logistic. Its paired 500-replicate bank-cluster and annual-cohort percentile calculations were actually replayed.

{uncertainty}

The bank-cluster cost interval crosses zero while the annual-cohort interval does not. Neither bootstrap jointly represents all bank and common-year dependence, all fitting/selection uncertainty or future regime changes. There are only 11 final annual cohorts and 35 failure events. The intervals are sensitivity evidence, not a guarantee of nominal prospective coverage.

## Independent challenge and added diagnostics

The frozen study implements its own weighted ROC/AP logic; [validation/review.py](../validation/review.py) instead uses scikit-learn metrics and separate pandas ranking/grouping. It checks all six model outputs, 66 annual model/cohort rows, and all 35 failed-bank cases for each model: {evidence['independent_numeric_and_case_checks']} numeric/count/flag comparisons. Counts and identities must be exact; finite floating comparisons use rtol 1e-10 and atol 1e-12. Fractional counts, invalid boolean flags, missing/duplicate rows, inconsistent horizons and nonfinite probabilities fail.

The source panel is still constructed by the hash-checked frozen builder; this is not a claim that a second implementation independently re-extracted every original API response. Pinned sources and the full fitted-probability replay provide the separate source-to-score route.

Added on 28 October 2026: feature PSI uses **development-only decile edges**, a separate missing bucket and 0.5 pseudocount smoothing. It is descriptive distribution shift, not a significance test. Nominal bank assets and changing balance-sheet composition affect interpretation.

{drift}

The post-hoc example governance policy enforces every declared rule: absolute Brier ceiling 0.20, no worse Brier than the constant baseline, maximum feature PSI 0.20, later recall floor 0.50 and evidence of actual information vintages. The absolute Brier ceiling alone is deliberately weak for rare events; the baseline comparison and other checks prevent treating it as sufficient. The PSI/recall values are illustrative review triggers, not regulatory standards, newly registered requirements or a tuned model choice.

Current status: **{evidence['governance']['status']}**. Distribution shift, later recall and missing original vintages trigger restrictions. Absent diagnostics yield INCOMPLETE_EVIDENCE; missing PSI never silently becomes zero. Even a run with no configured trigger would be labelled research review, not deployment approval.

## Reproduction and evidence

[Execution receipt](execution_receipt.json), [independent review data](independent_review.json), [frozen protocol](../bank_monitoring/reference/fdic_temporal/PROTOCOL.json), [complete reproduction guide](../docs/REPRODUCE.md), [claim map](../docs/CLAIMS.md).

The full current replay passed with maximum probability deviation {receipt['max_probability_error_from_original']:.12g} from the original. Original replay tolerances (rtol 1e-8, atol 1e-9) and frozen source files were preserved. This is numerical reproduction, not identical binary model serialization. No new API access, paid infrastructure, deployed users, financial benefit or bank endorsement is implied.
"""
    memo = f"""# Decision memo — fixed bank-failure monitoring model

**Recommendation: restrict to retrospective research and independent challenge; do not deploy the unchanged monitoring rule.**

The intended decision is whether the model can justify a historical bank-monitoring workflow. On all {receipt['final_rows']:,} final observations, calibrated boosting ranks failures reasonably well (ROC AUC {overall['auc']:.3f}) and improves Brier loss against calibrated full logistic. That comparison does not establish usable future probabilities or monitoring coverage.

The operational counterexample is direct: in the post-hoc 2022–2025 prediction cohorts, the fixed rule caught {late['test_caught_failures']} of {late['observed_failures']} failures. It predicted about {late['expected_failures']:.2f} events where {late['observed_failures']} occurred. The full set of failures remains visible in the explorer and machine-readable case audit. No favorable subset replaces it.

The original policy uses assumed 100:1 missed-failure/false-positive costs. These are not estimated losses or measured benefits of intervening. Bank-cluster uncertainty for the difference in that cost crosses zero. Original release vintages, real publication times, operating capacity, intervention effects and current-regime validation are absent. A prototype cannot substitute for them.

Use the artifact to inspect temporal controls, calibration transport, rare-event metrics and governance failure handling. A later extension would first define and seal new source availability, cohorts, policies and use constraints, then evaluate without modifying this final test. No recommendation to buy, sell, lend to or avoid any current institution follows from these historical scores.

Evidence: [technical validation](VALIDATION_REPORT.md), [execution receipt](execution_receipt.json), [independent review](independent_review.json), [frozen all-case audit](../bank_monitoring/reference/fdic_temporal/failure_cases.csv).
"""
    readme = f"""# Bank-risk model validation

**A pooled AUC of 0.916 did not make the monitoring rule reliable: it missed 9 of 10 failures in the later cohorts.**

A reproducible public-FDIC-data study of {receipt['eligible_rows']:,} bank-year observations, five purged temporal roles, logistic/boosting challengers, separate calibration and a frozen monitoring policy. The final test has {receipt['final_rows']:,} observations and 35 failures. A second metric/ranking implementation checks every annual cohort and failed-bank case.

The recommendation is **restricted research use**, not live monitoring approval. The 2022–2025 subgroup is a post-hoc diagnostic; original information vintages and actual report availability are not established. Bank-certificate failure is not borrower PD/LGD or IFRS 9 compliance.

- [Cohort and failure explorer](https://prasanna-k-123.github.io/credit-risk-model-validation/)
- [Decision memo](reports/DECISION_MEMO.md) · [Technical validation](reports/VALIDATION_REPORT.md)
- [Executed reproduction receipt](reports/execution_receipt.json) · [Independent evidence](reports/independent_review.json)
- [Frozen protocol](bank_monitoring/reference/fdic_temporal/PROTOCOL.json) · [Data and rights](docs/DATA.md)
- [Reproduction and architecture](docs/REPRODUCE.md) · [Claim-to-evidence map](docs/CLAIMS.md)

## What is implemented

Pinned source objects reconstruct the dated panel, exclusions and labels. Seven registered model fits, two calibrators, policy choices, all final predictions and paired bank/year bootstrap calculations actually run. The independent review checks metrics, every annual monitoring/capacity count and all failure cases; it adds training-bin drift diagnostics and governance rules that refuse missing evidence.

The current {stamp} replay passed with maximum probability difference {receipt['max_probability_error_from_original']:.3g} from the frozen study. Original files and tolerances are preserved. This is numerical reproduction, not a claim of bitwise identical models or an independently approved bank model.

## Run

Python 3.12. No account, API key, paid service or separately downloaded dataset is required for the pinned study.

    python -m venv .venv
    # Activate .venv for your platform.
    python -m pip install -r requirements.txt
    python -m pytest -q
    python scripts/reproduce.py
    node tests/check_explorer.cjs

Set OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=2 and MKL_NUM_THREADS=1 for the documented replay. Execution outputs go to ignored artifacts/current; public historical evidence is not overwritten by the default command. See [REPRODUCE](docs/REPRODUCE.md) for details.

## Boundaries

Current historical source revisions and assumed April 1 availability limit point-in-time claims. Repeated banks, rare later failures, annual cadence and separate dependence sensitivities limit transport and uncertainty. Cost/capacity scenarios do not identify realized losses, intervention benefits or financial savings. No production deployment, external endorsement or personal skill certification is claimed.

This repository's primary empirical route is now bank-risk validation. The earlier licensed mortgage study remains in [immutable research history](RESEARCH_HISTORY.md); it is not represented as freshly source-reproduced by this revision.
"""
    html = (ROOT / "docs/explorer.template.html").read_text()
    for marker, text in {"__STYLE__": (ROOT / "docs/explorer.css").read_text(),
                         "__SCRIPT__": (ROOT / "docs/explorer.js").read_text(),
                         "__EVIDENCE_JSON__": json.dumps(evidence, separators=(",", ":"), ensure_ascii=False, allow_nan=False).replace("</", "<\\/")}.items():
        if html.count(marker) != 1: raise ValueError("Template marker missing or duplicated: " + marker)
        html = html.replace(marker, text)
    return {"README.md": readme, "reports/VALIDATION_REPORT.md": report,
            "reports/DECISION_MEMO.md": memo, "docs/index.html": html}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, text in render().items():
        path = ROOT / name
        if args.check:
            if not path.is_file() or path.read_text() != text:
                raise ValueError("Generated public presentation differs: " + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    print("PASS: four public presentations match bound evidence." if args.check else "Built README, technical validation, memo and self-contained explorer.")


if __name__ == "__main__":
    main()
