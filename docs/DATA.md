# Data, lineage and permitted use

The main study uses official public FDIC BankFind financial, institution and failure/assistance data. It contains institution identifiers and historical financial observations, not individual borrower records.

Primary access and documentation:

- [FDIC API documentation](https://api.fdic.gov/banks/docs/)
- [Financial/regulatory data catalogue](https://catalog.data.gov/dataset/institution-financial-and-regulatory-data)
- [Institution data catalogue](https://catalog.data.gov/dataset/fdic-institutions-name-and-location)
- [Failure/assistance data catalogue](https://catalog.data.gov/dataset/bank-failures-and-assistance-data)

The catalogue distribution metadata identifies public, unrestricted access and public-domain terms. The implementation's MIT licence applies to code, not an invented endorsement or ownership claim over FDIC data. Preserve source attribution and do not imply FDIC approved the study.

`bank_monitoring/reference/fdic_temporal/source_snapshot.json` records exact extract bytes, SHA256 values, row counts, API source receipts and query/index context. Twenty-nine annual financial JSON objects, plus institution/failure objects, are compacted losslessly with gzip. The complete pinned final predictions are also compressed; their expanded SHA256 is checked before review. `artifact_manifest.json` binds the source code and released artifacts.

Predictors are explicitly limited to balance-sheet ratios, reported performance ratios and nominal log assets. Certificate identifiers, names, current status, event dates and future macro variables are excluded as predictors. Development data define imputation/scaling and newer PSI bin edges. The original panel builder preserves eligibility exclusions, competing exits, all final cohorts and missing-value diagnostics.

These are later-revised historical source values, not original release vintages. The three-month reporting lag is assumed. Current registry status is used with dated origin/exit fields to reconstruct eligibility; unknown dates and inconsistent cases are excluded and counted. This does not establish perfect contemporaneous population reconstruction. The annual target differs from loan default and includes competing nonfailure exits.

The public failure table refers to dated historical FDIC certificate failures only. It must not be read as a current bank-rating list. There is no private customer, employer or commercial bank information in the repository.

The prior Freddie Mac mortgage study has a different, licensed source contract. Its raw observations are not included or substituted into this study. See [research history](../RESEARCH_HISTORY.md).
