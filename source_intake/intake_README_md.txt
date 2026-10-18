# Mortgage credit-risk model validation

A six-cohort research study of calendar-safe distress prediction, model recalibration and transport under economic stress. Model development is not yet complete; no accuracy or stress-performance result is claimed.

The [source intake](source_intake/README.md) audits six original Freddie Mac sample archives: 300,000 loans and 20,151,667 monthly observations. All member CRC/hash, schema and key checks pass. Two 2015 loan histories contain three missing calendar months, recorded without imputation. The earlier frozen eligibility and censoring rules must handle these gaps when cohorts are built.

[Aggregate source reports](source_intake/reports/intake_summary.json) and [intake acceptance](source_intake/reports/intake_acceptance.json) document the evidence. Raw loan-level data are excluded from this repository. This is personal noncommercial academic research using a revised historical source, not a current lending system or an immutable historical-release backtest.
