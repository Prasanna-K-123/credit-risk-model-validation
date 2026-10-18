# Data provenance and permitted outputs

Source: [Freddie Mac Single-Family Loan-Level Dataset](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset).
Prasanna supplied the official Clarity 2012 annual ZIP on 16 October 2026. The
archive itself is retained unchanged; acquisition did not provide an independent
provider checksum, so a hash establishes the analyzed bytes, not external
authenticity certification.

The [July 2026 guide](https://www.freddiemac.com/fmac-resources/research/pdf/general_user_guide_july_2026.pdf),
[official headers](https://www.freddiemac.com/fmac-resources/research/docs/file_headers_july_2026.zip)
and [Release 47 notes](https://www.freddiemac.com/fmac-resources/research/pdf/release_notes.pdf)
define this layout. There are 31 origination fields and 35 performance fields.
Release 47 moves servicer and MI cancellation into monthly performance and adds
new fields. Old column positions and old recovery signs must not be reused.

The [November 2025 dataset terms](https://capitalmarkets.freddiemac.com/crt/docs/pdfs/fre_terms_conditions_sflld.pdf)
permit academic/research outputs for noncommercial purposes subject to their
conditions, including non-reconstruction of source data and no identification
of individuals. The project is a noncommercial research study. Public deliverables
are code, methods, aggregate results and a synthetic/aggregate demonstration.
No raw records, loan identifiers, source ZIPs, feature tables or row-level scores
are redistributed. Access to raw data remains through the provider; a code
license must not purport to license Freddie Mac data. No commercial product,
securities mapping, borrower identification or provider endorsement is claimed.

## Fixed source checksums

| File | SHA-256 |
|---|---|
| sample_2012.zip | 57b6b0281ee956dd1b8b4a7a24e4d3469fcbc8292fd7df981aa2a494f6a50220 |
| sample_orig_2012.txt | a428c6af7b1d4408f16bacd89eef57dac4a0b0cbb3276314f044176920cc98b8 |
| sample_perf_2012.txt | 5271ee93afc9f18ef99084037e0fe5880d1b1d7eaf6434e2204ddd0ebe784b04 |
| Official July 2026 header ZIP | db1390531ca9ea9ce11de2b2e1f42114dba5461d7e10a0eb508a4f464ff9e25a |

The 70,498,252-byte data ZIP contains two members: 6,459,950 and 507,818,159
uncompressed bytes. Streaming every row verified both ZIP CRCs and member hashes.

## Observed audit findings

The 2012 sample has 50,000 unique loans and 4,510,559 unique loan-months. Every
performance identifier matches an origination row; every origination has a
performance history. There are no internal calendar gaps. Coverage spans
January 2012–March 2026; individual histories span 1–171 observed months.

Each origination quarter has exactly 12,500 rows. Report this observed balance
and avoid treating the sample as a volume-weighted national population. Annual
samples are not pooled with weights intended to reproduce national lending.

DTI uses a missing sentinel on 17,400 loans; VantageScore is unavailable for all
50,000. Zero is not a substitute for missing information. Four first-payment
dates are later than the proposed December 2013 training snapshot; eligibility
uses actual dates and observed history, not a vintage-name assumption.

There are 444 within-loan decreases in reported loan age. Calendar chronology
therefore uses YYYYMM dates. Seventy-five exit records have an effective date
different from their reporting month (74 later, one earlier). Labels consistently
use the reporting month and disclose this limitation.

The first training cohort contains 45,129 eligible loans. Among 45,122 resolved
outcomes, 171 have reported credit distress; seven outcomes are unresolved.
There are 2,670 voluntary competing payoffs. These are training-data feasibility
counts, not a test result, model accuracy or achieved business impact.

The complete machine-readable audits are in `reports/`. Schema and relational
integrity do not establish that all reported financial information is correct.
These are revised historical data, not archived point-in-time release snapshots.

## Remaining acquisition

Required, fixed in the protocol: `sample_2013.zip`, `sample_2015.zip`,
`sample_2016.zip`, `sample_2018.zip`, `sample_2021.zip`. Audit each uploaded file
before fitting. None is claimed acquired at this checkpoint. Do not reuse the
2012 file as a substitute for the validation or test cohorts.
