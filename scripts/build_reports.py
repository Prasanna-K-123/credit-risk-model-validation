"""Build research communication and aggregate scenario cells from final evidence."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mortgage_risk.modelling import review_order
from fit_and_seal import read_frame, sha


def main():
    final=json.loads((ROOT/"reports/final_evaluation.json").read_text())
    selection=json.loads((ROOT/"reports/selection.json").read_text())
    preparation=json.loads((ROOT/"reports/preparation.json").read_text())
    study=json.loads((ROOT/"study.json").read_text())
    flows=[]
    for c in study["cohorts"]:
        a=json.loads((ROOT/f'reports/cohort_audit_{c["role"]}_{c["year"]}.json').read_text())
        flows.append(f'| {c["year"]} | {c["as_of"]} | {c["role"]} | {a["eligible_loans"]:,} | {a["known_outcomes"]:,} | {a["positive_outcomes"]:,} | {a["unresolved_outcomes"]} | {a["event_rate_among_known"]:.3%} |')
    rows=[];contrasts=[];capacity=[];scenario=[]
    for year,r in final["cohorts"].items():
        d=r["paired_brier"];ci=d["paired_percentile_95_interval"]
        contrasts.append(f'| {year} | {d["hgb_minus_logit"]:.9f} | [{ci[0]:.9f}, {ci[1]:.9f}] |')
        for family,m in r["models"].items():
            rows.append(f'| {year} | {family} | {m["brier"]:.6f} | {m["log_loss"]:.6f} | {m["roc_auc"]:.4f} | {m["average_precision"]:.4f} | {m["observed_expected_ratio"]:.3f} | {m["calibration"]["intercept"]:.3f} | {m["calibration"]["slope"]:.3f} |')
            for fraction,b in m["review_capacity"].items():
                lo,hi=b["capture_bounds"]
                capacity.append(f'| {year} | {family} | {float(fraction):.0%} | {b["reviewed"]:,} | {b["known_positive_captured"]} | {b["known_outcome_recall"]:.2%} | [{lo:.2%}, {hi:.2%}] |')
        vintage=r["source_vintage"];role="stress_test" if year=="2020" else "transport_test"
        frame=read_frame(ROOT/f"data/prepared/{role}_{vintage}.csv")
        pred=pd.read_csv(ROOT/f"artifacts/predictions_{vintage}.csv",dtype={"loan_id":str},float_precision="round_trip")
        assert np.array_equal(frame.loan_id,pred.loan_id)
        exposure=np.expm1(frame.log_current_upb.to_numpy(float))
        for family in ["logit","hgb"]:
            p=pred[family].to_numpy(float);order=review_order(p,pred.loan_id)
            for fraction,b in r["models"][family]["review_capacity"].items():
                indices=order[:b["reviewed"]]
                scenario.append({"outcome_year":year,"model":family,"capacity":fraction,
                    "reviewed":b["reviewed"],"known_capture":b["known_outcome_recall"],
                    "capture_bounds":b["capture_bounds"],
                    "reviewed_upb_usd":float(exposure[indices].sum()),
                    "probability_weighted_reviewed_exposure_usd":float((p[indices]*exposure[indices]).sum()),
                    "all_probability_weighted_exposure_usd":float((p*exposure).sum())})
    validation=[]
    for family,scores in selection["validation_brier"].items():
        for variant,score in scores.items():
            validation.append(f'| {family} | {variant} | {score:.9f} | {"Yes" if selection["selected_variants"][family]==variant else ""} |')
    text="""# Credit risk under economic stress

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
"""+"\n".join(flows)+"""

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
"""+"\n".join(validation)+"""

Selected variants are unchanged logistic and retrained boosting. Boosting's small
validation advantage lies inside the .0001 simplicity tolerance, so logistic is
the frozen recommendation. Models and predictions for both tests were sealed
and committed before final-label evaluation. The evaluation repair note records
a subsequent one-key audit-metadata lookup correction; no model, selection,
prediction, metric or bootstrap rule changed.

## Held-out results

| Outcome year | Frozen model | Brier ↓ | Log loss ↓ | ROC AUC | Average precision | Observed / expected | Calibration intercept | Slope |
|---|---|---:|---:|---:|---:|---:|---:|---:|
"""+"\n".join(rows)+"""

Average precision uses the step-weighted precision–recall definition. Its event
rate reference is 4.8578% in 2020 and 0.5933% in 2023. Joint calibration intercept
and slope are unpenalized diagnostic fits, with observed-information intervals
in the JSON. They do not recalibrate the released probabilities.

The primary contrast is selected boosting minus selected logistic on identical
known-outcome loans. A paired 2,000-resample loan bootstrap uses seed 20261016.

| Outcome year | Brier difference, HGB − logistic | Paired percentile 95% interval |
|---|---:|---|
"""+"\n".join(contrasts)+"""

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
"""+"\n".join(capacity)+"""

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
"""
    (ROOT/"reports/TECHNICAL_REPORT.md").write_text(text)
    memo="""# Model-validation decision memo

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
"""
    (ROOT/"reports/DECISION_MEMO.md").write_text(memo)
    (ROOT/"reports/RECRUITER_BRIEF.md").write_text("# Credit-risk project: concise explanation\n\nBuilt a chronological model-validation study over 300,000 Freddie Mac loans and 20.15 million monthly records. Audited six source vintages, constructed leakage-controlled SQL snapshots and explicitly censored 12-month labels, and compared fixed logistic/boosting models with adaptation-only updates. Sealed both test prediction files before evaluation.\n\nThe challenger improved 2020 Brier by .0007118 (paired 95% interval [.0005154, .0009197] improvement), yet observed events were 6.2–8.3 times predicted across models. The resulting memo restricts probability use despite useful ranking. Separate 2023 transport, unresolved-outcome bounds, review-capacity diagnostics and broad-group uncertainty preserve the failure cases.\n\nBusiness relevance: probability monitoring, credit-model validation, temporal drift, risk review allocation and model governance. This is historical US mortgage research, not a deployable Indian underwriting or IFRS 9 model.\n")
    aggregate={"selection":{k:selection[k] for k in ["selected_variants","recommended_family_from_validation","validation_brier"]},
               "cohorts":{year:{k:r[k] for k in ["eligible","known","events","unresolved","models","paired_brier"]} for year,r in final["cohorts"].items()},
               "scenarios":scenario,"scope":final["scope"]}
    (ROOT/"reports/demo_aggregates.json").write_text(json.dumps(aggregate,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"technical_report_words":len(text.split()),"memo_words":len(memo.split()),"aggregate_scenarios":len(scenario)}))


if __name__=="__main__":
    main()
