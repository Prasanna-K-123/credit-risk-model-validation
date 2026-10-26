# Credit risk and model validation under economic stress

[![Public research checks](https://github.com/Prasanna-K-123/credit-risk-model-validation/actions/workflows/verify.yml/badge.svg)](https://github.com/Prasanna-K-123/credit-risk-model-validation/actions/workflows/verify.yml)

**A better held-out score did not make the probabilities safe to use.**

A six-vintage Freddie Mac mortgage study by Prasanna K, an economics student at
Madras School of Economics. Audited 300,000 loans and 20,151,667 monthly records;
constructed chronological SQL snapshots and explicitly censored 12-month labels;
compared fixed logistic and histogram-boosting models with bounded adaptation.

On the primary 2020 stress test, selected boosting improves Brier by 0.000711822
against selected logistic (paired 95% interval for HGB − logistic:
[−0.000919710, −0.000515400]). Yet observed events are **6.155 times predicted
for boosting and 8.324 times for logistic**. The memo restricts both models to historical research
and ranking diagnostics, rejecting unchanged probabilities for operational loss
or capital use. The separate 2023 transport check preserves the same models.

The validation-based recommendation remains unchanged logistic under the fixed
0.0001 simplicity tolerance. Neither model is reselected using test results.

- [Current Windows verification (26 October)](docs/exports/windows_verification_20261026.html)
- [Live aggregate explorer](https://prasanna-k-123.github.io/credit-risk-model-validation/)
- [Technical report](reports/TECHNICAL_REPORT.md)
- [Decision memo](reports/DECISION_MEMO.md)
- [Frozen protocol](docs/PROTOCOL.md) and [implementation details](docs/IMPLEMENTATION.md)
- [Final aggregate evidence](reports/final_evaluation.json)
- [Selection/prediction seal](reports/selection.json)
- [Data and use restrictions](docs/DATA.md)
- [Evaluation metadata repair](docs/EVALUATION_REPAIR.md)

## Automated public checks

The public suite runs without private data or model refitting: 12 original
cohort/model tests, five cache-integrity tests, seven licensed-adapter tests,
four comparison tests and three independent raw-feature tests (31 total).
Three source-intake tests also reject schema, key and gap defects.

## Reproduce

The [26 October current-status note](docs/CURRENT_STATUS_20261026.md) records a
completed, newly fitted Windows verification. All 967 floating aggregate fields
pass the predeclared absolute-plus-relative 1e-10 comparison; all 456 discrete
numeric fields and 76 report-display checks match. The original selection and
probability-use restriction remain unchanged.

**Exact historical input identity remains 4/6.** Two prepared-table hashes and
their dependent digests differ; the full historical comparison remains failed.
Independent raw-feature reconstruction verifies the current tables. The new
model and prediction files are separately sealed, with no claim of historical
rowwise or binary identity. Original scientific reports remain unchanged; new
evidence is under [reports/portable_20261026](reports/portable_20261026/summary.json).

Use Python 3.12 and the exact packages in `requirements.txt`. Repository-local
`.gitattributes` preserves the source bytes required by the historical seals.
Use a clean private reproduction copy; retain any fitting-start marker and
never replace expected historical hashes.

Obtain permitted personal noncommercial access through the [official Freddie Mac
dataset page](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset).
Review its current terms. Supply Release 47 samples for 2012, 2013, 2015, 2016,
2018 and 2021 as `data/raw/sample_YEAR.zip`. The required hashes are in
`source_intake/reports/intake_summary.json`; revised source bytes fail.

The [portable guide](docs/PORTABLE_REPRODUCTION.md) gives complete PowerShell
and Bash commands, pinned upstream attribution and both distinct routes:

- `scripts/portable_reproduction.py` preserves the all-six historical identity
  check and stops if it fails.
- `scripts/windows_verification.py` executes the explicit Windows v1 protocol,
  preserving that failure and independently verifying the declared current inputs
  before the unchanged four-fit/two-update study.

The additive `prepare_verified_stores.py` ingests sources and attests private SQL
cache bytes. Later reuse requires a matching attestation; mere file existence
or an old integrity statement is insufficient. The original cache entrypoint
is retained as historical code. Test predictions are sealed before evaluation;
no hyperparameter search or test-based reselection occurs.

The published aggregate explorer remains the historical view. Its recorded
[browser checks](reports/browser_verification.json) cover that version, not a
new device certification for this maintenance. The current execution report
links the new aggregate evidence. Capacity/severity/cost scenarios do not
identify intervention benefits or achieved avoided losses.

## Private artifacts and interpretation

Raw rows, identifiers, SQL stores, feature/label tables, fitted models and
individual predictions are ignored by Git. Research evidence contains aggregates
and hashes only. The original `SOURCE_MANIFEST.json` describes the received
checkpoint, not the completed tree. `study.json`'s pre-fit flag is historical
protocol metadata; current run state appears under `reports/`.

These are originated US mortgages in a later-revised July 2026 release. SQL
cutoffs do not establish immutable contemporary release availability. The target
is reported distress before payoff, not regulatory default or realized loss.
Unresolved outcomes receive bounds. Hidden borrower/common-shock dependence can
weaken loan-bootstrap intervals. Broad-group diagnostics do not establish fairness.
Indian portability, IFRS 9 compliance and intervention effects are not established.

The [21 October publication-status note](reports/publication_status_revision_20261021.json) clarifies the original report label. The original report-builder code, frozen methods, empirical results and dated reproduction hashes are retained.
