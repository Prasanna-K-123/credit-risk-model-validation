# Current status — 26 October 2026

**The new Windows verification completed the full fixed scientific run.**
Its current aggregates support the original model-use restriction. Exact
historical table reproduction remains unproved for two of six cohorts.

Read the [current execution report](exports/windows_verification_20261026.html),
[complete comparison](../reports/portable_20261026/comparison.json), and
[portable commands](PORTABLE_REPRODUCTION.md). The original published reports,
protocol, method hashes, source hashes and expected table hashes remain intact.

## What was executed

All six permitted Release 47 ZIPs matched the original source receipts. Earlier
fresh ingestion produced SQL caches that were then independently attested.
This run verified and reused those exact bytes; it did not repeat ingestion or
upload licensed rows externally.

Native Windows `math.log1p` originally failed the unchanged 2012 byte gate.
A versioned, licensed positive-finite translation of a pinned glibc algorithm
acts only in `mortgage_risk.cohorts.math`. Global math functions remain unchanged.
The translation restored exact bytes for the two training tables, the adaptation
table and the 2021 transport features. The 2016 validation and 2018 stress-test
table hashes still differ. The all-six historical-identity check therefore
remains **failed, 4/6**, and no fit occurred under that failed attempt.

A separate [Windows verification v1 protocol](../compatibility/windows_verification_v1.json)
was recorded before fitting. Independent checks then established:

- Exact reconstruction from raw ZIP strings of all 20 features in both unmatched
  tables: 1,709,460 cells across 85,473 loans, using only origination and the
  six-month lookback.
- All 530,890 current log features within one ulp of an 80-digit reference;
  maximum observed error 0.522338 ulp.
- All 265,445 balance ratios equal independently rounded high-precision division.
- Exact schema/order, unique sorted keys, historical missingness and applicable
  cohort/label counts.

These checks verify the current data against its sources. Original private
arrays are unavailable, so the historical cell-level differences remain
unlocalized. The new protocol does not relabel that limitation as historical
identity.

The unchanged original fit script ran once: **four full fits and two intercept
updates**, with no search. Logistic completed in 31 and 27 iterations without
convergence warnings; boosting completed 200 fixed rounds each. Models and
both label-free test prediction files were sealed before evaluation. Original
evaluation, exact feature alignment, report generation and internal verification
passed, with zero subsequent refits.

## Comparison and current result

The pre-fit comparison contract was unchanged:
`abs(current − historical) <= 1e-10 + 1e-10*abs(historical)`.

All **967 floating scientific fields**, **456 exact integer/Boolean fields**
and **76 prespecified display checks** pass. Selected variants remain unchanged
logistic and retrained boosting; the simplicity rule still recommends logistic.
The current primary HGB-minus-logistic Brier difference is
−0.0007118219328015098, with paired 95% interval
[−0.0009197104789197541, −0.0005154003879141054].

The full 11-file historical comparison nevertheless fails at five digest fields
that trace the two unmatched input tables. All failures are retained. No
tolerance was widened and no second training run was chosen for closer results.

Both prediction-file hashes differ even after explicit LF/CRLF normalization.
All four fitted-model byte hashes also differ. Aggregate agreement does not
establish or quantify historical rowwise prediction agreement. The new seals
establish integrity of this newly executed run.

## Corrected cache handling and public tests

The original `prepare_all_stores.py` trusted an existing database and its old
audit without checking current database bytes. The additive
`prepare_verified_stores.py` instead records a digest immediately after fresh
original ingestion, member checks, SQLite integrity and row-count checks.
Reuse verifies the raw ZIP, ingestion methods and actual database bytes.
An old cache without this receipt requires rebuilding before fitting.

The receipt detects accidental changes; it does not authenticate against someone
who can replace both database and receipt. Five regression tests include a real
SQLite value edit that preserves counts and passes SQLite integrity but is
rejected by the actual cache entrypoint.

The public suite now contains 31 tests: 12 original cohort/model tests, five
cache tests, seven adapter tests, four comparison tests and three independent
raw-feature tests. Three intake tests also pass. The seven original cohort tests
were repeated in the adapter context. License/source identity, boundary accuracy,
module isolation, tamper rejection and future-feature exclusion are covered.

## Reading historical records correctly

The top-level `reports/` evidence still describes the original October 18 study.
New aggregate evidence is separate under `reports/portable_20261026/`.
`docs/PROTOCOL.md`, `docs/IMPLEMENTATION.md`, `study.json` and all 20 original
method files retain their original bytes. Their planning-stage checkpoint
statements do not describe the current completion status. Likewise, the original
`docs/DATA.md` acquisition paragraph and `SOURCE_MANIFEST.json` are historical.

The original report builder retains its historical date, byline, fixed narrative
numbers and broad “all full fits converge” wording. Logistic passed numerical
convergence checks; completing boosting's fixed 200 rounds is not a claim of
global optimality. The dated current report uses the new machine-readable
evidence and makes this distinction explicit.

Prasanna K is currently an economics student at Madras School of Economics,
pursuing M.A. Actuarial Economics, 2026–2028. An original program-name byline is
not a claim that the degree has already been awarded.

## Interpretation

The code and receipts demonstrate an ordered computation, not external
preregistration or a secure human outcome lockbox. Original ingestion reads raw
performance records for structural auditing; fitting and selection do not use
the final held-out labels.

The completed current run supports the same restriction to historical
research/ranking. Later-revised US mortgages do not establish Indian portability,
regulatory default, IFRS 9 ECL, fairness, causal review benefits or live model
approval. Loan bootstrap uncertainty is conditional on the historical data and
resampling assumptions. Personal mastery requires an independent technical
defense; it is not certified by owning these artifacts.
