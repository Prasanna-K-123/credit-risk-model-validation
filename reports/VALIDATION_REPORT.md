# Bank-risk validation: pooled performance and later monitoring failure

Current execution: 2026-10-28. This is a second implementation of metric and decision checks within one research portfolio, not an independent institutional opinion or regulatory approval.

## Decision and intended user

A model reviewer asks whether a historical bank-failure model supports its intended monitoring rule. **Restrict the fixed model to retrospective research and challenge analysis.** Its calibrated booster has pooled AUC 0.915546, but missed 9 of 10 failures in the later 2022–2025 prediction cohorts. A better pooled score does not establish a reliable operating policy.

The later slice was selected for descriptive investigation after seeing annual results. It is **post hoc**, not a new untouched test. It is retained to expose a failure mode, not to tune a replacement model.

## Data lineage and target

The frozen snapshot contains 29 December financial extracts, the FDIC institution registry and failure/assistance records. From these, the actual source builder reconstructs 237,253 eligible bank-year observations. Its exclusions and event coverage are recorded in [eligibility_audit.json](../bank_monitoring/reference/fdic_temporal/eligibility_audit.json). Integrity checks bind source bytes, schema, predictor whitelist, protocol, roles and final row identities.

The target is certificate failure during (April 1, next April 1], with nonfailure closure/insurance exit as a competing outcome. It is not borrower default, borrower PD/LGD, loss severity, IFRS 9 adequacy or a current bank rating. Reports are assumed available three months after December 31; original publication timestamps and contemporary revisions are not reconstructed. The pinned objects are later-revised historical values. These limitations prevent a point-in-time prospective-performance claim.

| Role | Report years | Bank-year rows | Failure events | Last outcome horizon |
|---|---|---:|---:|---|
| development | 1992–2005 | 148,144 | 105 | 2007-04-01 |
| selection | 2007–2008 | 16,649 | 204 | 2010-04-01 |
| calibration | 2010 | 7,561 | 82 | 2012-04-01 |
| policy | 2012 | 7,003 | 25 | 2014-04-01 |
| test | 2014–2024 | 57,896 | 35 | 2026-04-01 |


Role boundaries include purged years so earlier outcome horizons precede later role prediction dates. Repeated certificates across time are intentional. This measures temporal transport among the eligible historical institutions, not generalization to unseen banks. Registry matching, known origin/insurance dates, inactive dates and positive assets determine eligibility; the exclusions remain part of the population definition.

## Models and choices made before final scoring

The constant development-event-rate and capital-only logistic models are baselines. Full logistic uses training-only median imputation/robust scaling and C candidates 0.01, 0.1 and 1.0. Histogram boosting uses native missing routing and 7, 15 or 31 leaves, with fixed iteration, learning-rate and regularization settings. Both families use the same development rows; selection minimizes separate-year log loss. The selected values are C=0.1 and 7 leaves. No final-score model reselection occurs.

Two monotone logistic calibrators are fit only on the calibration year. The policy year chooses an illustrative cost-minimizing threshold with a false-negative weight of 100 and false-positive weight of 1; exact ties prefer less monitoring. These weights are scenarios, not measured bank financial losses or estimated intervention benefits. Annual top-1% review is a separate descriptive capacity diagnostic with public certificate ID tie-breaking.

## Results: keep ranking, calibration and decisions separate

| Model | ROC AUC | Average precision | Brier | Fixed-rule caught / 35 | Monitored |
|---|---:|---:|---:|---:|---:|
| Development-rate baseline | 0.500000 | 0.000605 | 0.000604178 | 0 | 0 |
| Capital-only logistic | 0.918904 | 0.027756 | 0.000604083 | 20 | 1470 |
| Full logistic, raw | 0.838060 | 0.052297 | 0.000597511 | 18 | 445 |
| Full logistic, calibrated | 0.838060 | 0.052297 | 0.000635647 | 18 | 445 |
| Boosting, raw | 0.915546 | 0.149048 | 0.000555635 | 22 | 381 |
| Boosting, calibrated | 0.915546 | 0.149048 | 0.000556234 | 22 | 381 |


The calibrated booster predicts 28.7692 failures versus 35 observed over all final rows. Its fixed rule monitors 381 observations, catches 22 failures and generates 359 false positives. In the later post-hoc slice it predicts 3.0006 failures versus 10 observed and catches only 1. Overall calibration can conceal severe cohort-specific problems.

The constant baseline has average precision equal to the final prevalence (approximately 0.000605). Average precision is therefore reported alongside ROC AUC, avoiding a ranking-only story in a very rare-event population. Zero-failure annual cohorts retain undefined ROC/AP rather than receiving invented perfect scores.

## Uncertainty

The original registered comparison is calibrated boosting minus calibrated full logistic. Its paired 500-replicate bank-cluster and annual-cohort percentile calculations were actually replayed.

| Resampling unit | Difference in Brier, 95% interval | Difference in illustrative cost, 95% interval |
|---|---|---|
| CERT | [-0.000165166, -0.000010190] | [-0.018129, 0.001289] |
| prediction_date | [-0.000155805, -0.000016845] | [-0.013808, -0.002235] |


The bank-cluster cost interval crosses zero while the annual-cohort interval does not. Neither bootstrap jointly represents all bank and common-year dependence, all fitting/selection uncertainty or future regime changes. There are only 11 final annual cohorts and 35 failure events. The intervals are sensitivity evidence, not a guarantee of nominal prospective coverage.

## Independent challenge and added diagnostics

The frozen study implements its own weighted ROC/AP logic; [validation/review.py](../validation/review.py) instead uses scikit-learn metrics and separate pandas ranking/grouping. It checks all six model outputs, 66 annual model/cohort rows, and all 35 failed-bank cases for each model: 1470 numeric/count/flag comparisons. Counts and identities must be exact; finite floating comparisons use rtol 1e-10 and atol 1e-12. Fractional counts, invalid boolean flags, missing/duplicate rows, inconsistent horizons and nonfinite probabilities fail.

The source panel is still constructed by the hash-checked frozen builder; this is not a claim that a second implementation independently re-extracted every original API response. Pinned sources and the full fitted-probability replay provide the separate source-to-score route.

Added on 28 October 2026: feature PSI uses **development-only decile edges**, a separate missing bucket and 0.5 pseudocount smoothing. It is descriptive distribution shift, not a significance test. Nominal bank assets and changing balance-sheet composition affect interpretation.

| Predictor | Training-to-final PSI |
|---|---:|
| log_assets | 0.806539 |
| net_interest_margin_fraction | 0.773967 |
| cash_to_assets | 0.490755 |
| equity_to_assets | 0.265457 |
| securities_to_assets | 0.160003 |
| loans_to_assets | 0.088643 |
| deposits_to_assets | 0.077285 |
| return_on_assets_fraction | 0.051945 |
| nonperforming_assets_fraction | 0.012521 |


The post-hoc example governance policy enforces every declared rule: absolute Brier ceiling 0.20, no worse Brier than the constant baseline, maximum feature PSI 0.20, later recall floor 0.50 and evidence of actual information vintages. The absolute Brier ceiling alone is deliberately weak for rare events; the baseline comparison and other checks prevent treating it as sufficient. The PSI/recall values are illustrative review triggers, not regulatory standards, newly registered requirements or a tuned model choice.

Current status: **RESTRICTED_RESEARCH**. Distribution shift, later recall and missing original vintages trigger restrictions. Absent diagnostics yield INCOMPLETE_EVIDENCE; missing PSI never silently becomes zero. Even a run with no configured trigger would be labelled research review, not deployment approval.

## Reproduction and evidence

[Execution receipt](execution_receipt.json), [independent review data](independent_review.json), [frozen protocol](../bank_monitoring/reference/fdic_temporal/PROTOCOL.json), [complete reproduction guide](../docs/REPRODUCE.md), [claim map](../docs/CLAIMS.md).

The full current replay passed with maximum probability deviation 5.65858471191e-12 from the original. Original replay tolerances (rtol 1e-8, atol 1e-9) and frozen source files were preserved. This is numerical reproduction, not identical binary model serialization. No new API access, paid infrastructure, deployed users, financial benefit or bank endorsement is implied.
