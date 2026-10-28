# Bank-risk model validation

**A pooled AUC of 0.916 did not make the monitoring rule reliable: it missed 9 of 10 failures in the later cohorts.**

A reproducible public-FDIC-data study of 237,253 bank-year observations, five purged temporal roles, logistic/boosting challengers, separate calibration and a frozen monitoring policy. The final test has 57,896 observations and 35 failures. A second metric/ranking implementation checks every annual cohort and failed-bank case.

The recommendation is **restricted research use**, not live monitoring approval. The 2022–2025 subgroup is a post-hoc diagnostic; original information vintages and actual report availability are not established. Bank-certificate failure is not borrower PD/LGD or IFRS 9 compliance.

- [Cohort and failure explorer](https://prasanna-k-123.github.io/credit-risk-model-validation/)
- [Decision memo](reports/DECISION_MEMO.md) · [Technical validation](reports/VALIDATION_REPORT.md)
- [Executed reproduction receipt](reports/execution_receipt.json) · [Independent evidence](reports/independent_review.json)
- [Frozen protocol](bank_monitoring/reference/fdic_temporal/PROTOCOL.json) · [Data and rights](docs/DATA.md)
- [Reproduction and architecture](docs/REPRODUCE.md) · [Claim-to-evidence map](docs/CLAIMS.md)

## What is implemented

Pinned source objects reconstruct the dated panel, exclusions and labels. Seven registered model fits, two calibrators, policy choices, all final predictions and paired bank/year bootstrap calculations actually run. The independent review checks metrics, every annual monitoring/capacity count and all failure cases; it adds training-bin drift diagnostics and governance rules that refuse missing evidence.

The current 2026-10-28 replay passed with maximum probability difference 5.66e-12 from the frozen study. Original files and tolerances are preserved. This is numerical reproduction, not a claim of bitwise identical models or an independently approved bank model.

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
