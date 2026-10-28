# Decision memo — fixed bank-failure monitoring model

**Recommendation: restrict to retrospective research and independent challenge; do not deploy the unchanged monitoring rule.**

The intended decision is whether the model can justify a historical bank-monitoring workflow. On all 57,896 final observations, calibrated boosting ranks failures reasonably well (ROC AUC 0.916) and improves Brier loss against calibrated full logistic. That comparison does not establish usable future probabilities or monitoring coverage.

The operational counterexample is direct: in the post-hoc 2022–2025 prediction cohorts, the fixed rule caught 1 of 10 failures. It predicted about 3.00 events where 10 occurred. The full set of failures remains visible in the explorer and machine-readable case audit. No favorable subset replaces it.

The original policy uses assumed 100:1 missed-failure/false-positive costs. These are not estimated losses or measured benefits of intervening. Bank-cluster uncertainty for the difference in that cost crosses zero. Original release vintages, real publication times, operating capacity, intervention effects and current-regime validation are absent. A prototype cannot substitute for them.

Use the artifact to inspect temporal controls, calibration transport, rare-event metrics and governance failure handling. A later extension would first define and seal new source availability, cohorts, policies and use constraints, then evaluate without modifying this final test. No recommendation to buy, sell, lend to or avoid any current institution follows from these historical scores.

Evidence: [technical validation](VALIDATION_REPORT.md), [execution receipt](execution_receipt.json), [independent review](independent_review.json), [frozen all-case audit](../bank_monitoring/reference/fdic_temporal/failure_cases.csv).
