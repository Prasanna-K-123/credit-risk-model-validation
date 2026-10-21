**Publication update — 21 October 2026:** This study is completed and published. The report below retains its original 18 October release-candidate wording. See the [current research home](../README.md) and [recorded reproduction](reproduction_verification.json).

# Credit risk under economic stress

Prasanna K · M.A. Actuarial Economics, Madras School of Economics  
Research completed 18 October 2026 · Release candidate

## Decision

**Restrict both frozen models to historical research and ranking diagnostics;
reject their unchanged probabilities for operational loss or capital decisions.**
The nonlinear challenger improves held-out Brier score, but this does not repair
large aggregate underprediction. The validation-based recommendation remains
unchanged logistic regression under the predeclared simplicity tolerance. Test
results are evidence about that decision, not permission to select again.

## Question and scope

Does a model trained on comparatively low-event historical cohorts remain useful
when the event rate and population change? This study uses six official Freddie
Mac Release 47 annual samples: 300,000 originated loans and 20,151,667 monthly
records. Each sample contains 50,000 loans. One eligible snapshot per loan is used.
The target is a reported 90+ day delinquency, REO or specified distress exit in
the next 12 reporting months, before voluntary payoff. It is not regulatory
default, realized financial loss, an Indian underwriting model or IFRS 9 ECL.

The July 2026 release incorporates later revisions. Features obey SQL reporting
cutoffs, but immutable historical releases are unavailable. Cohort differences
cannot be attributed solely to COVID-19 or any single economic cause. Accepted
loans alone do not identify rejected-applicant performance.

## Data integrity and outcome flow

All six source ZIP hashes, 12 member CRCs, field counts, key relationships and SQL
integrity checks pass. There are no duplicate IDs or supplied pre-HARP-linked
loans across the six files. The transitive-link exclusion logic is tested even
though no exclusion is needed in these samples. This cannot rule out common
borrowers with different undisclosed identifiers.

Two 2015 loan histories have three missing months. Original data are preserved:
the fixed six-month snapshot rule and unresolved-follow-up rules handle them.
The earlier 2012 feature/label CSV reproduces its original SHA-256 byte for byte.

| Source vintage | Snapshot | Role | Eligible | Known | Positive | Unresolved | Known event rate |
|---|---|---|---:|---:|---:|---:|---:|
| 2012 | 201312 | train | 45,129 | 45,122 | 171 | 7 | 0.379% |
| 2013 | 201412 | train | 45,535 | 45,531 | 167 | 4 | 0.367% |
| 2015 | 201612 | adaptation | 42,952 | 42,948 | 254 | 4 | 0.591% |
| 2016 | 201712 | validation | 45,407 | 45,399 | 192 | 8 | 0.423% |
| 2018 | 201912 | stress_test | 40,066 | 40,059 | 1,946 | 7 | 4.858% |
| 2021 | 202212 | transport_test | 46,356 | 46,350 | 275 | 6 | 0.593% |

Positive distress evidence remains known despite earlier missing observations.
Complete event-free observation or voluntary payoff with complete prior history
establishes a negative. Sales/transfers/defects without prior distress, unknown
codes and incomplete histories are censored. Reporting months determine labels;
effective exit dates never move an event across the cutoff. Full source mismatch
counts are published in the audit and final JSON. Known-case scoring does not
assume independent censoring; all-eligible rate and review-capture bounds are
reported separately. Both test unresolved fractions are far below the fixed 2%
approval veto, but that alone does not justify approval.

## Fixed methods and validation decision

The original protocol was fixed on 16 October. The implemented methods were
hashed and committed before fitting on 18 October. Both families share 16 numeric
and four categorical predictors: origination attributes and six-month performance
history, with sentinel decoding, calendar age and no future performance. IDs,
geography, seller/servicer, disposition and loss fields are excluded. Modification
status means observed in the six-month lookback, not lifetime modification history.

Numeric medians, missingness indicators and one-hot categories are fitted only
on the applicable training sample. Unknown categories map to all-zero indicators;
boosting never treats arbitrary category codes as ordered values. Logistic uses
standardization, L2 C=1 and at most 2,000 iterations. Histogram boosting uses
learning rate .05, 200 iterations, seven leaves, minimum 200 rows per leaf, L2=10
and no early stopping. Neither uses class weights or target-based sampling.

Exactly four full fits and two adaptation-only intercept adjustments produce
six candidates. All full fits converge; logistic iterations are 31 and 27.
There is no hyperparameter search. Each family's validation Brier minimum selects
unchanged/recalibrated/retrained, with declared numerical ties. The final family
rule prefers logistic within .0001 Brier of boosting.

| Family | Variant | Validation Brier | Selected within family |
|---|---|---:|---|
| hgb | recalibrated | 0.003726356 |  |
| hgb | retrained | 0.003488586 | Yes |
| hgb | unchanged | 0.003550964 |  |
| logit | recalibrated | 0.003549959 |  |
| logit | retrained | 0.003516522 |  |
| logit | unchanged | 0.003508143 | Yes |

Selected variants are unchanged logistic and retrained boosting. Boosting's small
validation advantage lies inside the .0001 simplicity tolerance, so logistic is
the frozen recommendation. Models and predictions for both tests were sealed
and committed before final-label evaluation. The evaluation repair note records
a subsequent one-key audit-metadata lookup correction; no model, selection,
prediction, metric or bootstrap rule changed.

## Held-out results

| Outcome year | Frozen model | Brier ↓ | Log loss ↓ | ROC AUC | Average precision | Observed / expected | Calibration intercept | Slope |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2020 | hgb | 0.045743 | 0.249317 | 0.7155 | 0.1721 | 6.155 | 0.203 | 0.562 |
| 2020 | logit | 0.046455 | 0.262207 | 0.6930 | 0.1600 | 8.324 | 0.629 | 0.620 |
| 2023 | hgb | 0.004920 | 0.024998 | 0.9005 | 0.2930 | 1.840 | 0.679 | 0.980 |
| 2023 | logit | 0.005307 | 0.028965 | 0.8847 | 0.2392 | 2.297 | 0.616 | 0.891 |

Average precision uses the step-weighted precision–recall definition. Its event
rate reference is 4.8578% in 2020 and 0.5933% in 2023. Joint calibration intercept
and slope are unpenalized diagnostic fits, with observed-information intervals
in the JSON. They do not recalibrate the released probabilities.

The primary contrast is selected boosting minus selected logistic on identical
known-outcome loans. A paired 2,000-resample loan bootstrap uses seed 20261016.

| Outcome year | Brier difference, HGB − logistic | Paired percentile 95% interval |
|---|---:|---|
| 2020 | -0.000711822 | [-0.000919710, -0.000515400] |
| 2023 | -0.000387614 | [-0.000569092, -0.000202392] |

The primary interval is below zero, establishing an advantage conditional on
this historical cohort and the loan-resampling assumptions. It does not justify
deploying either probability model. In 2020 observed events exceed expected by
8.324 times for logistic and 6.155 for boosting. Ranking remains informative,
while absolute risk levels fail. In the separately labeled 2023 transport test,
underprediction remains 2.297 and 1.840 times. The 2023 result cannot replace the
primary comparison or trigger reselection.

## Review allocation, uncertainty and failure cases

Capacity is a fraction of all eligible loans, rounded upward. Frozen probabilities
rank loans; SHA-256 ID hashes break ties. No threshold is chosen on test labels.
Known recall divides captured known positives by all known positives. Bounds
assign unresolved outcomes adversarially inside/outside the selected group;
they are identification bounds, not confidence intervals or intervention benefits.

| Year | Model | Capacity | Reviewed | Known positives captured | Known recall | All-eligible capture bounds |
|---|---|---:|---:|---:|---:|---|
| 2020 | hgb | 1% | 401 | 174 | 8.94% | [8.91%, 8.94%] |
| 2020 | hgb | 5% | 2,004 | 402 | 20.66% | [20.58%, 20.66%] |
| 2020 | hgb | 10% | 4,007 | 586 | 30.11% | [30.02%, 30.15%] |
| 2020 | logit | 1% | 401 | 169 | 8.68% | [8.65%, 8.68%] |
| 2020 | logit | 5% | 2,004 | 383 | 19.68% | [19.61%, 19.68%] |
| 2020 | logit | 10% | 4,007 | 573 | 29.45% | [29.35%, 29.48%] |
| 2023 | hgb | 1% | 464 | 135 | 49.09% | [48.21%, 49.28%] |
| 2023 | hgb | 5% | 2,318 | 174 | 63.27% | [62.37%, 63.54%] |
| 2023 | hgb | 10% | 4,636 | 192 | 69.82% | [68.82%, 70.04%] |
| 2023 | logit | 1% | 464 | 132 | 48.00% | [47.14%, 48.19%] |
| 2023 | logit | 5% | 2,318 | 169 | 61.45% | [60.57%, 61.73%] |
| 2023 | logit | 10% | 4,636 | 183 | 66.55% | [65.59%, 66.79%] |

Broad FICO, LTV and original-term diagnostics include paired Brier-difference
intervals and Wilson event-rate intervals. Cells below 30 known loans are
suppressed; cells with fewer than 30 events carry an explicit instability flag.
These descriptive comparisons have no multiplicity-adjusted superiority claim.
Protected attributes are unavailable, so no fairness conclusion is possible.
Numeric missingness/median shifts and categorical proportions are published
against training. Test drift is descriptive and never changes preprocessing.

The bootstrap treats loans as independent after supplied-link checks. Hidden
borrower overlap, geographic/calendar dependence and common economic shocks can
make its uncertainty too narrow. It is not a confidence interval for a new macro
regime. Equal-count calibration bins are descriptive, not underwriting rules.

## Use restrictions and reproducibility

The aggregate explorer changes capacity and explicit severity/review-cost
assumptions. Probability × outstanding balance × assumed severity is a conditional
scenario based on miscalibrated research probabilities. Serious delinquency is
not a realized financial loss. The study does not identify the causal effect of
reviewing a borrower; there are no achieved avoided-loss or profitability claims.

Full reproduction requires a permitted Freddie Mac account and the six pinned
source ZIPs. Raw rows, IDs, feature/label tables, SQL stores, predictions and fitted
models remain private. Public evidence contains aggregates and hashes only.
The README lists source auditing, preparation, fitting, sealing, evaluation and
report commands. Original protocol/method manifests, selection seal and the
explicit metadata-repair record preserve the order of scientific decisions.

Operational approval would require a separately authorized, later-cohort study
with fresh probability calibration, population validation, intervention economics
and governance. That is outside this frozen release; it is not performed by
retuning on these tests.
