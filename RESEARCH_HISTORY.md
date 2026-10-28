# Research history and empirical scope

The primary route in this repository is now public-data **bank-risk model validation**. It incorporates the frozen FDIC temporal study previously developed under the same account's credit-risk research collection. Original source files, protocol, source snapshot, empirical results and hash manifest remain unchanged under `bank_monitoring/`; the 28 October 2026 revision adds integration, a separate review implementation, governance diagnostics and presentation.

The older mortgage implementation and its historical receipts remain at immutable commit [bf0656308e541570f13d3481f9aa95bcc3615f7e](https://github.com/Prasanna-K-123/credit-risk-model-validation/tree/bf0656308e541570f13d3481f9aa95bcc3615f7e). This revision does not claim a fresh reconstruction from its six licensed Freddie Mac archives. Its original 4/6 exact historical prepared-input identity limitation and separately recorded Windows comparisons must not be relabelled as complete byte identity.

Bank failure and borrower distress are different targets and populations. No mortgage metric, loan count, loss estimate or IFRS 9 claim is carried into the bank-risk headline. The scope change provides a fully public source-to-result route while preserving the earlier work's provenance instead of fabricating a new development history.

The original FDIC protocol is dated 10 October 2026. Its source-freeze commit/tree identifiers are preserved in the artifact manifest. The current reproduction verifies those frozen bytes; it does not independently certify an external preregistration service or recreate the circumstances of the first experiment. New governance/PSI diagnostics are explicitly post hoc, and no original model, split, candidate grid, calibrator or threshold was retuned.

## Test dependency maintenance — 28 October 2026

The supported installation in the repository-root `requirements.txt` pins
**pytest 9.0.3**, the minimum fix for
[CVE-2025-71176 / GHSA-6w46-j5rx-g56g](https://github.com/advisories/GHSA-6w46-j5rx-g56g).
The issue concerns predictable temporary-directory handling on UNIX when another
local user can interfere with the shared temporary area. It is a test-harness
issue, not an FDIC model or static-explorer vulnerability.

The first maintenance commit,
[`4b5a4ad25fbf`](https://github.com/Prasanna-K-123/credit-risk-model-validation/commit/4b5a4ad25fbf9cd9df1cdee5bc1a4697495b55e5),
changed the nested historical requirements file. Its 42 tests passed, but
[CI's full reproduction](https://github.com/Prasanna-K-123/credit-risk-model-validation/actions/runs/40715940945)
correctly rejected that change because the file belongs to the frozen research
manifest. Unit-test success did not establish that the complete reproduction
contract still held.

The correction restores `bank_monitoring/requirements-fdic-temporal.txt` to its
exact original bytes, including the historical pytest 8.3.3 entry. That nested
file is preserved research evidence and is **not the supported installation
route**. The root requirements independently specify the same four scientific
packages and patched pytest 9.0.3; they do not include the historical file.
Neither the frozen manifest nor its tolerance or scientific outputs changed.

The current default suite passes **44 tests and 17 subtests**, including two
new early checks: validate every frozen-source file and reject a simulated edit
to the historical dependency pin. The full pinned-source fitting, calibration,
policy and independent-review pipeline then passes with maximum probability
difference `5.658584711909498e-12`, 237,253 eligible rows and 1,470 independent
comparisons. The four generated presentations match their evidence and all
850 explorer-script checks pass. This repeat fit verifies the unchanged study;
it is not a new model selection or an additional untouched evaluation.

The patched pytest temporary-directory fixture also passed a separate ownership,
private-base-permission and file-access smoke check, without claiming exhaustive
exploit testing. A current advisory query returns no known advisory for the five
packages in the supported root installation. Older environments and execution
records retain their historical dates.
