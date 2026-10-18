# Model-validation decision memo

Prasanna K · 18 October 2026

**Decision: restrict both models to historical research/ranking diagnostics;
reject unchanged probabilities for operational expected-loss or capital use.**

The six-vintage study audits 300,000 Freddie Mac loans and 20.15 million monthly
records. It compares a fixed logistic baseline with a bounded histogram-boosting
challenger, unchanged/adaptation-recalibrated/retrained variants, chronological
validation, a primary 2020 stress test and a separate 2023 transport test.

Validation selects unchanged logistic and retrained boosting. The predeclared
.0001 Brier simplicity tolerance recommends logistic. That recommendation was
sealed with both test prediction files before final evaluation and remains fixed.

On 40,059 known outcomes in 2020, boosting Brier is .045743 versus .046455 for
logistic. The paired difference is −.000711822, with a 2,000-loan-bootstrap 95%
interval [−.000919710, −.000515400]. This is a meaningful historical comparison,
but observed events are 6.155 and 8.324 times predicted respectively. AUCs of
.7155 and .6930 do not offset that probability failure. At 5% review capacity,
boosting captures 402/1,946 known positives; logistic captures 383/1,946. These
are allocation diagnostics, not causal effects of review.

The unchanged 2023 transport check favors boosting in Brier too, while observed
events remain 1.840 times expected for boosting and 2.297 for logistic. It is
secondary evidence and cannot be used to choose a replacement model. There
are seven unresolved outcomes in 2020 and six in 2023; both fractions are below
the fixed 2% veto. Explicit worst/best-case bounds accompany the known-case scores.

No unexplained schema or linkage failure is observed. The original 2012 cohort
reproduces byte for byte; all full fits converge. One report-metadata lookup
was repaired transparently after the first primary evaluation attempt, with
all models, predictions and evaluation rules unchanged.

The data are a later-revised July 2026 release of originated US mortgages.
Historical-release availability, rejected-applicant outcomes, Indian portability,
regulatory default, fairness and intervention effectiveness are not established.
Loan-bootstrap intervals can understate common-shock dependence. Conditional
severity/cost scenarios are illustrative and must not be treated as provisions,
achieved savings or live borrower decisions.

The credible project result is the detection of monitoring failure under a
changed population—not a claim that a higher AUC or a nonlinear model is safe
to deploy. A new independently held-out study would be required for operational
probability approval.
