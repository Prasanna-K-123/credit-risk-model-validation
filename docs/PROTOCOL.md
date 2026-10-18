# Credit Risk and Model Validation Under Economic Stress

Protocol v1 · fixed 16 October 2026, before fitting any model.

## Decision and estimand

Assess whether a model that ranks risk well still supports credible monitoring
probabilities and review allocation after the population and economic conditions
change. Compare a transparent logistic baseline with one nonlinear challenger;
compare leaving each model unchanged, intercept recalibration, and retraining.

The target is a reported serious-delinquency/REO/foreclosure event during the next
12 reporting months among eligible, already-originated US mortgages. This is
neither regulatory default nor an Indian underwriting or IFRS 9 model. The
analysis cannot estimate returns on rejected applications, which are absent.

## Fixed data and chronological cohorts

Use the six official Release 47 annual samples below. No additional vintage is
required for this release. Dataset failures may justify an explicit amendment;
an unattractive result does not. Sample size is determined by the provider's
annual sample and the eligibility rules, never by model performance.

| Vintage | Snapshot | Outcome months | Role |
|---|---|---|---|
| 2012 | December 2013 | January–December 2014 | Training |
| 2013 | December 2014 | January–December 2015 | Training |
| 2015 | December 2016 | January–December 2017 | Adaptation: recalibration or retraining |
| 2016 | December 2017 | January–December 2018 | Validation: fixed candidate selection |
| 2018 | December 2019 | January–December 2020 | Primary held-out stress evaluation |
| 2021 | December 2022 | January–December 2023 | Secondary held-out transport evaluation |

Each loan contributes one snapshot. Before fitting, reject duplicate identifiers
across files. Group any identifiers linked through the supplied pre-HARP field;
retain the earliest assigned cohort and exclude linked later-cohort observations.
Report only aggregate overlap counts. No external borrower identification or
record linkage is allowed. These controls cannot prove that all different loans
belong to different people.

The validation outcome window ends a full calendar year before the primary
test snapshot. No 2020 or 2023 outcomes, thresholds or distributions may influence
training, imputation, calibration, hyperparameters or candidate selection.
Predictions and a selection record must be saved before final evaluation.
The later test is a fixed-model transport check, not a second chance to select.

This is a retrospective study using the July 2026 release. SQL respects historical
reporting-month cutoffs, but the source incorporates later corrections and field
revisions. We do not possess historical release snapshots and cannot claim an
actually deployable historical backtest. Differences across cohorts cannot be
attributed solely to COVID-19, interest rates or any single cause.

## Eligibility and labels

At the snapshot require positive balance, delinquency 00–02, no exit, first payment
due by the snapshot, and six consecutive monthly observations ending there. The
six-month window must have known numeric delinquency and no prior exit. Previous
cured delinquency is allowed; it is not silently excluded using future outcomes.

The following forward rules are fixed in `outcome_12m`:

- Any recorded 90+ day delinquency, REO, or exit code 02/03/09 in the next 12
  reporting months is a positive. A documented positive remains known despite
  an earlier missing observation.
- Voluntary repayment (01), with complete known preceding observations, is a
  competing event and a negative for this **before-payoff** estimand. It does
  not prove the borrower would have stayed healthy if the loan had remained.
- Sales/transfers/defects (15/16/96) without a preceding positive are censored.
  They are neither assumed defaults nor assigned healthy labels.
- Twelve complete event-free months establish a negative. Unknown codes,
  gaps or truncated follow-up otherwise yield an unresolved outcome.

Use reporting months consistently. Do not move events backward or forward using
a mismatching zero-balance effective date. Count and disclose such mismatches.
The target concerns reports, not an independently observed legal event date.
Report the flow from original sample to eligible, known and unresolved outcomes.

Fit and score on known outcomes; separately report unresolved fractions and
worst/best-case bounds over all eligible loans, including review-capture bounds.
These bounds are not confidence intervals. Do not assume censoring is independent
or invent inverse-censoring weights. If unresolved follow-up exceeds 2% in a test
cohort, the report must withhold unconditional approval for that cohort.

## Frozen feature set

The SQL snapshot supplies FICO, DTI, original LTV/CLTV, mortgage-insurance share,
original term and rate, current rate, log original/current balance, calendar age,
current delinquency, maximum delinquency and delinquent-month count over six
months, six-month balance ratio, historical modification status, and categorical
purpose, occupancy, property type and relief-refinance status.

Decode documented sentinel values before preprocessing. Fit medians, missingness
indicators, scaling and category encoders only on the applicable fitting sample.
Use the same frozen feature list for both model families. Keep identifiers,
dates, outcome reasons, future performance, disposition/loss fields, seller,
servicer, geographic identifiers, VantageScore, assistance flags and estimated
current property value out of the predictor matrix. Some excluded fields have
changed disclosure availability across cohorts. Calendar age comes from dates,
not the provider's age field, which can reset after modification.

## Bounded model budget

- Logistic regression: L2 penalty, C=1, maximum 2,000 iterations; median imputation
  plus missingness indicators; numeric standardization; one-hot categories.
- Histogram gradient boosting classifier: learning rate 0.05, 200 iterations,
  at most 7 leaves, minimum 200 observations per leaf, L2=10; no early stopping
  or parameter search. Use explicit categorical encoding and unknown-category
  handling, without ordinal-distance interpretation of categories.
- Neither family uses class weighting, oversampling or target-dependent sampling.
  The output must retain its interpretation as an event probability.
- For each family, retain (a) the original training fit, (b) that frozen fit with
  an intercept-only log-odds adjustment fitted on adaptation outcomes, and (c)
  a fresh fit on training plus adaptation with identical settings. This is six
  candidates, four full model fits and two one-parameter adjustments.

Use deterministic seed 20261016 where randomness exists. Clamp probabilities only
for numerical evaluation at [1e-8,1−1e-8]; do not use clipping to improve metrics.
Any failure to converge is a failure to report and resolve, not permission to
silently add a model family. No automatic hyperparameter search.

Select one treatment per model family using minimum validation Brier score;
ties within 1e-8 prefer unchanged, then recalibrated, then retrained. Freeze both
selected candidates. Recommend the lower validation-Brier candidate for the
primary comparison, preferring logistic when the difference is within 0.0001.
This rule is declared before validation outcomes are acquired.

## Evaluation and decisions

Primary test contrast: selected nonlinear candidate minus selected logistic
candidate in Brier score on the same known-outcome loans in the 2020 cohort.
Negative differences favor the nonlinear model. Report a paired 2,000-resample
loan bootstrap interval with seed 20261016. Separate confidence intervals for
different models are not a confidence interval for their difference.

Also report log loss, ROC AUC, precision–recall AUC with its event-rate reference,
observed/expected events, calibration intercept/slope, equal-count calibration
groups, and recall/precision at 1%, 5% and 10% review capacity. Break ties by a
deterministic hash of loan ID only. Never choose a final threshold on test labels.
Show missingness/population drift and uncertainty by broad FICO, LTV and original
term strata. Suppress unstable small-group interpretation and no subgroup cells
below 30 loans; the absence of protected attributes prevents a fairness claim.

The 2023 cohort supplies a separately labeled secondary transport result with
the same frozen models and reporting rules. It does not replace the 2020
primary comparison. All additional subgroup and capacity comparisons are
descriptive, without multiplicity-adjusted claims of superiority.

The interface changes review capacity and explicit conditional-loss and review-cost
assumptions. A 90+ day event is not a realized financial loss: any probability ×
exposure × severity output is a scenario conditioned on stated assumptions.
The dataset does not identify the causal effectiveness of reviewing a borrower;
never present simulated avoided losses or intervention benefits as achieved.

The model-validation memo must recommend approve, restrict or reject within the
study's scope. Unexplained leakage, schema failures or unresolved labels invalidate
approval. A larger AUC alone does not justify approval. Calibration failures and
wide intervals may support restriction even if ranking looks strong. A null or
negative result is a valid outcome; do not retune on either test cohort.

## Completion

Release requires all six source audits, cross-cohort checks, runnable models,
held-out uncertainty, a technical report and concise decision memo, an aggregate
demonstration, and a tagged reproducible code release. Raw rows, identifiers,
private feature tables, predictions and the SQLite stores are never published.
No fitted model or finished credit-risk project is claimed at this checkpoint.
