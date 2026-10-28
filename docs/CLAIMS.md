# Public claim-to-evidence map

| Public claim | Inspectable evidence | Boundary |
|---|---|---|
| 237,253 eligible bank-year observations | Frozen `eligibility_audit.json`; panel rebuilt by `benchmark_fdic_temporal.load_panel`; current execution receipt | Eligibility population, not all historical institutions |
| 57,896 final rows and 35 failures | `summary.json` population; full compressed predictions; independent review | 11 annual prediction cohorts, not prospective cases |
| Five temporal roles with purged boundaries | `PROTOCOL.json`; `src/fdic_temporal.py::assert_temporal_partitions`; original temporal tests | Assumed report availability, revised source values |
| Fixed model selection and separate calibration/policy | `benchmark_fdic_temporal.py::run`; `selection_trials.csv`; `PROTOCOL.json` | No new reselection in review |
| Pooled calibrated-boosting AUC approximately 0.916 | Frozen predictions/summary and independent sklearn metric | Ranking does not imply probability or decision reliability |
| 9 of 10 later failures missed | `descriptive_audit.json`, all 35 `failure_cases.csv` rows, independent annual/case checks | 2022–2025 slice is post hoc |
| Better pooled Brier than calibrated logistic | Frozen paired uncertainty and independent metrics | Comparison baseline matters; not production adequacy |
| Bank- and year-bootstrap cost intervals differ | `summary.json::paired_uncertainty`; complete replay | Separate dependence sensitivities, only 11 year clusters |
| Feature distribution shift | `reports/independent_review.json::feature_drift`; `validation/review.py::feature_psi` | Added post hoc; train-bin PSI and 0.5 smoothing; no significance claim |
| Missing diagnostics cannot pass governance | `govern`, `ReviewPolicy`, negative-control tests | Illustrative review policy, not regulatory standards |
| Full actual source-to-result execution | `reports/execution_receipt.json`; original manifest; reproduction command/log | Numerical reproduction, not bitwise serialized model equality |
| Explorer filters preserve all failures/counts | Generated evidence payload; `tests/check_explorer.cjs` | Static research demonstration, no live service/users |
| Public data access | FDIC API and Data.gov links in `DATA.md`; source snapshot | No FDIC endorsement |
| Research history retained | Immutable mortgage commit and original FDIC hashes in `RESEARCH_HISTORY.md` | No fabricated manual authorship, mastery or development chronology |

All relative frozen-evidence names above refer to `bank_monitoring/reference/fdic_temporal/`, and the original source path is relative to `bank_monitoring/`. The generated report/memo/README/explorer must come from `scripts/build_presentation.py`; hand-editing a claim without its underlying evidence will fail regeneration checks.
