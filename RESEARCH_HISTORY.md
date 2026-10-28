# Research history and empirical scope

The primary route in this repository is now public-data **bank-risk model validation**. It incorporates the frozen FDIC temporal study previously developed under the same account's credit-risk research collection. Original source files, protocol, source snapshot, empirical results and hash manifest remain unchanged under `bank_monitoring/`; the 28 October 2026 revision adds integration, a separate review implementation, governance diagnostics and presentation.

The older mortgage implementation and its historical receipts remain at immutable commit [bf0656308e541570f13d3481f9aa95bcc3615f7e](https://github.com/Prasanna-K-123/credit-risk-model-validation/tree/bf0656308e541570f13d3481f9aa95bcc3615f7e). This revision does not claim a fresh reconstruction from its six licensed Freddie Mac archives. Its original 4/6 exact historical prepared-input identity limitation and separately recorded Windows comparisons must not be relabelled as complete byte identity.

Bank failure and borrower distress are different targets and populations. No mortgage metric, loan count, loss estimate or IFRS 9 claim is carried into the bank-risk headline. The scope change provides a fully public source-to-result route while preserving the earlier work's provenance instead of fabricating a new development history.

The original FDIC protocol is dated 10 October 2026. Its source-freeze commit/tree identifiers are preserved in the artifact manifest. The current reproduction verifies those frozen bytes; it does not independently certify an external preregistration service or recreate the circumstances of the first experiment. New governance/PSI diagnostics are explicitly post hoc, and no original model, split, candidate grid, calibrator or threshold was retuned.

## Test dependency maintenance — 28 October 2026

The current test harness now pins **pytest 9.0.3** instead of 8.3.3. This is the
minimum patched release for [CVE-2025-71176 / GHSA-6w46-j5rx-g56g](https://github.com/advisories/GHSA-6w46-j5rx-g56g),
which concerns predictable temporary-directory handling on UNIX when another
local user can interfere with the shared temporary area. It is a test-environment
issue, not an FDIC model or static-explorer vulnerability.

The existing suite passes **42 tests and 17 subtests** with the patched pin. A
separate temporary-directory fixture smoke check confirms owner-only base
permissions and normal file access in the tested environment; it is not an
exhaustive exploit test. A current PyPI advisory query reports no known advisory
for pytest 9.0.3. No scientific fitting or source/output-seal change was needed.
The earlier requirements and execution records remain historical evidence.
