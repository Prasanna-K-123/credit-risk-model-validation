# Reproduce the bank-risk study

Use Python 3.12 and the pinned packages in `requirements.txt`. All inputs required for the frozen study are included as compact, checksum-pinned public FDIC source objects. No account, new collection, API key, paid service or loan-data licence is needed.

```sh
python -m venv .venv
# Bash:
source .venv/bin/activate
# PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
```

For Bash:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=1 python scripts/reproduce.py
```

For PowerShell:

```powershell
$env:OPENBLAS_NUM_THREADS="1"
$env:OMP_NUM_THREADS="2"
$env:MKL_NUM_THREADS="1"
python scripts/reproduce.py
```

Then:

```sh
python scripts/build_presentation.py --check
node tests/check_explorer.cjs
```

Node is used only for the explorer's independent behavior harness. The scientific Python route does not require it.

## What runs and where it writes

1. `bank_monitoring/replay_fdic_temporal.py` verifies the original source/packaging/artifact manifest, losslessly expands the original prediction CSV, rebuilds the panel, refits the registered candidates and calibrators, recomputes all final scores, policies and paired bootstrap intervals, and runs the all-case descriptive audit.
2. `validation/review.py` separately calculates metrics using scikit-learn and annual/case decisions with pandas ranking. It verifies identity and count contracts, computes training-defined feature PSI from the audited panel, and evaluates the explicit post-hoc governance rules.
3. `scripts/reproduce.py` writes the actual log, independent review and timestamped environment receipt to ignored `artifacts/current/`. Failures stop the route. A frozen replay failure writes `failure.json`; other failures retain their traceback and partial outputs for diagnosis. No failure is converted into a success receipt.
4. The committed presentation is built from the committed review and its bound execution receipt. `build_presentation.py --check` checks deterministic source regeneration. To deliberately replace public evidence after a successful full run, use `python scripts/reproduce.py --refresh-public`; inspect the diff before committing.

The default run does not overwrite historical references or public receipts. Current execution timing is local elapsed time, not a universal performance claim. This study is modest enough for a CPU laptop; no fitted-model binaries are needed publicly.

## Architecture and evaluation boundaries

`bank_monitoring/` preserves the exact original fitting, source, test and replay files at their original relative paths. The internal `reference/fdic_temporal/artifact_manifest.json` binds original source, compressed objects and outputs. The 29 financial extracts plus registry/failure objects are the source of every predictor/label; a ready-made feature CSV is not silently substituted.

`validation/` is the newer review implementation. `scripts/reproduce.py` orchestrates both routes. `scripts/build_presentation.py` plus `docs/explorer.*` own every generated narrative/explorer value. `tests/` covers the review and publication guard; `bank_monitoring/tests/` retains the original temporal contracts. The source-to-claim map is in [CLAIMS.md](CLAIMS.md).

Frozen model replay uses its original `rtol=1e-8, atol=1e-9` probability/metric contract. The separate review of identical frozen predictions uses `rtol=1e-10, atol=1e-12` for finite floating metrics; counts, keys, flags and frozen bytes must match exactly. A failed comparison requires investigation, not replacing expected values or widening tolerances. Numerical equality is distinct from binary model identity.

The maximum probability discrepancy in the recorded 28 October Linux run was approximately 5.66e-12. Only the observed pinned environment is verified; the commands are portable, but untested operating systems are not certified. Source/environment/version details are in the execution receipt.

## Source refresh and future work

`collect_fdic_temporal.py` and `prefetch_fdic_sources.py` preserve original acquisition logic and receipts. They are not run by the pinned replay. A new live API collection may contain revised values and will not automatically qualify as the same study. Keep a new collection and preregistered future-cohort extension separate; never overwrite frozen evidence to make a refresh pass.

No adverse final cohort may be removed, and no threshold may be reselected using this final test. Further work should resolve actual availability/vintage evidence, prospectively define the next population and intended intervention, and compare simple alternatives before considering deployment.

## CI and releases

Routine verification runs source/contract tests, full pinned replay and presentation/explorer checks with read-only repository permission. It does not upload datasets, models or redundant output artifacts, and it creates no new pip cache.

A release is a separate explicit manual dispatch: existing semantic version tag, exact reviewed 40-character commit, main/dispatch/checkout/tag agreement, successful verification, and ref rechecks before publication. The guard never creates or moves a tag and never overwrites different release notes. Workflow concurrency does not atomically lock external account writers; platform tag protection/immutable-release settings are separate controls. A stored workflow is not evidence that a release has been published.
