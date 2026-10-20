# Credit risk and model validation under economic stress

[![Public research checks](https://github.com/Prasanna-K-123/credit-risk-model-validation/actions/workflows/verify.yml/badge.svg)](https://github.com/Prasanna-K-123/credit-risk-model-validation/actions/workflows/verify.yml)

**A better held-out score did not make the probabilities safe to use.**

A six-vintage Freddie Mac mortgage study by Prasanna K, M.A. Actuarial Economics,
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

- [Live aggregate explorer](https://prasanna-k-123.github.io/credit-risk-model-validation/)
- [Technical report](reports/TECHNICAL_REPORT.md)
- [Decision memo](reports/DECISION_MEMO.md)
- [Frozen protocol](docs/PROTOCOL.md) and [implementation details](docs/IMPLEMENTATION.md)
- [Final aggregate evidence](reports/final_evaluation.json)
- [Selection/prediction seal](reports/selection.json)
- [Data and use restrictions](docs/DATA.md)
- [Evaluation metadata repair](docs/EVALUATION_REPAIR.md)

## Automated public checks

The automated checks run on public files without private data, credentials or model refitting. They run the unit tests. Raw-source model reproduction is separate.

## Reproduce

Use the exact packages in `requirements.txt`. The scientific comparison uses four
unique full model fits and two intercept-only adaptation updates, with no search.
Test predictions are sealed before evaluation.

Obtain permitted personal noncommercial access through the [official Freddie Mac
dataset page](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset).
Review its current terms. Acquire Release 47 samples for 2012, 2013, 2015, 2016,
2018 and 2021. Place them in `data/raw/sample_YEAR.zip`. Required hashes appear
in `source_intake/reports/intake_summary.json`; changed bytes fail ingestion.
No protected download is automated here. From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/prepare_all_stores.py
python scripts/check_data_ready.py --source-dir data/raw --report reports/source_readiness.json
python scripts/prepare_study.py
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 python scripts/fit_and_seal.py
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 python scripts/evaluate_release.py
python scripts/build_reports.py
python scripts/build_demo.py
python tools/polish_demo_layout.py
python scripts/verify_results.py
```

This checks hashes, CRCs, schema, key relationships, source gaps, SQL integrity
and supplied cross-cohort links. The original 2012 CSV must reproduce exactly.
Preparation builds four labeled fitting/validation cohorts and two label-free
test snapshots. Preserve the supplied pre-fit manifest; `fit_and_seal.py` checks
every original method hash and refuses an existing started-fit marker. Use a
clean working copy for reproduction; it repeats the same candidates, not search.
Run-seal dates differ between reproductions and are excluded from scientific
comparisons. `evaluate_release.py` differs from the retained original evaluator
by one documented audit-metadata key repair; no model or scoring rule changed.

Open `docs/index.html` for the self-contained aggregate explorer. Capacity,
assumed severity and review cost select saved aggregates or arithmetic scenarios.
No individual lending decision or causal avoided-loss estimate occurs. The public
explorer has been checked across all 12 cohort/model/capacity views, keyboard
controls, three report links and desktop/375px/320px iframe widths. These are
browser CSS checks, not phone OS or touch-input certification. See the
[recorded browser verification](reports/browser_verification.json).

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
