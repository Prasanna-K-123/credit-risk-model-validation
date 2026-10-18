# Implementation fixed before model fitting

18 October 2026. This implements protocol v1 without changing its cohort,
feature, model, selection or evaluation budget.

- Original 2012 feature/label CSV must reproduce its prior SHA-256 before
  fitting. The restored protocol, SQL and label functions remain unchanged.
- `modified_by_snapshot` means modification observed in the six-month feature
  lookback. It does not establish that a loan has never been modified earlier.
- Both families use explicit one-hot categories with unknown categories mapped
  to all-zero indicators. Histogram boosting never treats category codes as
  ordered quantities. Numerical missingness indicators are learned only from
  the fitting sample; keep-empty features prevents silently dropping a column.
- The four full fits use the two fixed estimator settings; each original fit
  has one intercept-only adaptation update. No class balancing is applied.
- Supplied pre-HARP links are joined transitively before eligibility. A linked
  later source cohort is excluded even if its earlier linked loan is ineligible.
  No IDs or individual predictions appear in public results.
- Primary and transport test snapshots are built without their forward labels.
  Selected model files and both test prediction files are hashed and sealed
  before the evaluation script is allowed to construct those labels.
- Review capacity is `ceil(fraction × all eligible test loans)`, ranked by frozen
  probability with SHA-256 loan-ID tie breaking. Known-label recall and sharp
  all-eligible capture/precision bounds are distinguished.
- Broad descriptive strata are FICO <680 / 680–739 / >=740 / missing, LTV <=80 /
  >80 / missing, and original term <=180 / >180 / missing. Cells below 30 loans
  have no published numeric performance. Wilson event-rate intervals and paired
  Brier-difference bootstrap intervals describe uncertainty; few-event cells
  cannot establish stable subgroup performance or fairness.
- Point calibration diagnostics are unpenalized likelihood fits of the observed
  outcome on frozen predicted log odds; they are diagnostic only. They never
  replace released probabilities. The displayed precision–recall summary is
  average precision (step-weighted PR area), with the event rate as reference.
- Percentile paired bootstrap intervals use 2,000 loan resamples and seed
  20261016 for each separately reported contrast. They assume independent loans
  after supplied-link exclusion; undisclosed common borrowers and shared macro
  shocks remain limitations. No population-level causal or policy claim follows.

The historical ZIP manifest documents the received checkpoint. A separate
pre-fit manifest seals the implemented methods; a selection record seals the
models and predictions; the final manifest records the evaluated release.
