# Running the preserved study and the current Windows verification

Use Python 3.12 and `requirements.txt` in a fresh private reproduction copy.
Keep original scientific methods, the 2012 byte gate, source hashes and fit budget
unchanged. Never delete a fitting-start marker to repeat a fitted study.

There are two explicitly different routes:

| Route | Input requirement | Honest interpretation |
|---|---|---|
| `portable_reproduction.py` | All six prepared tables must match historical hashes exactly | Historical input identity, followed by a separately checked aggregate comparison |
| `windows_verification.py` v1 | The six declared current hashes, independent raw-feature/numeric checks, and all original method/source gates | A new Windows refit; the historical 4/6 identity failure remains visible |

The [current execution report](exports/windows_verification_20261026.html)
documents the completed second route. Its 967 floating fields, 456 discrete
numeric fields and 76 report-display checks agree under the locked rules.
Historical model/prediction binary identity and rowwise historical agreement are
not established.

## Input and cache setup

Acquire permitted personal noncommercial access to the six Release 47 ZIPs
listed in the README. Put them in `data/raw/sample_YEAR.zip`. Revised source
bytes require a separately reviewed data release; changing a pinned hash is not
a repair. Raw rows and generated data/model files remain private and ignored.

Repository-local `.gitattributes` preserves exact committed source bytes.
No global Git setting or system control needs changing. An existing checkout
with changed method bytes should be replaced by a clean copy, not “repaired”
by regenerating historical seals.

Use `scripts/prepare_verified_stores.py --rebuild` for initial ingestion.
It invokes the original ingestion method, checks source/member bytes, SQLite
integrity and counts, then records the actual database hashes.
For already-attested caches, use `--verify-only` instead. Changed bytes or
missing provenance fail; the old existence-only cache entrypoint is historical.

The recorded October 26 scientific run reused caches from earlier fresh
ingestion after rechecking their exact bytes. It did not reingest data again.

## Complete current Windows v1 route — PowerShell

After creating `.venv` with Python 3.12 and installing `requirements.txt`,
run from the fresh reproduction root:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = 'src'
$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:NUMEXPR_NUM_THREADS = '2'
$env:BLIS_NUM_THREADS = '2'
$env:VECLIB_MAXIMUM_THREADS = '2'
New-Item -ItemType Directory -Force data/tmp | Out-Null
$env:TEMP = (Resolve-Path data/tmp).Path
$env:TMP = $env:TEMP
function Invoke-StudyPython {
    & .venv/Scripts/python.exe @args
    if ($LASTEXITCODE -ne 0) { throw 'Study stage failed; preserve the evidence.' }
}
Invoke-StudyPython scripts/prepare_verified_stores.py --rebuild
Invoke-StudyPython scripts/windows_verification.py prepare
Invoke-StudyPython scripts/windows_verification.py fit
Invoke-StudyPython scripts/windows_verification.py evaluate
Invoke-StudyPython scripts/windows_verification.py compare
```

Replace the initial `--rebuild` with `--verify-only` when valid cache
attestations already exist. Every stage stops on an unexpected failure.

The new `prepare` command invokes the unchanged strict preparation first.
It can recognize only the specific, declared two-table historical mismatch;
other source, schema, method, runtime or table mismatches still fail.
It records the failed historical check, independently reconstructs the current
inputs, and seals the distinct Windows protocol before fitting. It never
changes the historical expected hashes or labels them passed.

In the recorded run, strict preparation had already completed and stopped at
that identity check. The executed continuation was
`windows_input_checks.py`, a recorded 31-test run, then
`windows_verification.py authorize`, `fit`, `evaluate`, and `compare`.
The fresh-copy `prepare` command composes preparation, independent checks and
the new input seal. The name `authorize` refers to recording that declared
protocol; it grants no data-access rights or operational model approval.

## Strict historical route

Use the same Python environment and thread/UTF-8 settings in a separate fresh
copy. After verified cache setup, substitute these four commands:

```powershell
Invoke-StudyPython scripts/portable_reproduction.py prepare
Invoke-StudyPython scripts/portable_reproduction.py fit
Invoke-StudyPython scripts/portable_reproduction.py evaluate
Invoke-StudyPython scripts/portable_reproduction.py compare
```

The current host's first command fails the all-six historical table check,
after four exact matches. Its original 2012 gate passes under the adapter.
The strict workflow must stop there; do not remove its assertion, change the
expected digest, or call its fit stage on failed inputs. The separate Windows
protocol above is a new execution claim, not a relabeling of this result.

## Bash environment

For a matching Python 3.12 environment:

```bash
set -e
export PYTHONUTF8=1 PYTHONPATH=src
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
export NUMEXPR_NUM_THREADS=2 BLIS_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2
mkdir -p data/tmp
export TEMP="$PWD/data/tmp" TMP="$PWD/data/tmp"
python scripts/prepare_verified_stores.py --rebuild
python scripts/portable_reproduction.py prepare
python scripts/portable_reproduction.py fit
python scripts/portable_reproduction.py evaluate
python scripts/portable_reproduction.py compare
```

The explicit adapter is portable Python. A Linux installation is not automatically
the original native runtime. The Windows v1 protocol additionally requires its
specific current input hashes; it is not a generic fallback for any mismatch.

## Runtime provenance and independent tests

The [pinned source and permission notice](../third_party/glibc/README.md)
identify the exact glibc revision and source blob. Python adapter version 1.0.0
supports positive finite binary64 inputs, preserves separate arithmetic
operations and rejects unsupported values. It acts only in
`mortgage_risk.cohorts.math` during preparation/evaluation; process-wide
`math.log1p` is unchanged. No C code is compiled or native executable installed.

The public suite has 31 tests, plus three intake tests. The seven original cohort
tests also run inside the actual adapter context. Tests include boundary and
neighbor inputs, a 400-digit accuracy reference, monotonicity, domain rejection,
exact upstream blob identity, proxy restoration, cache corruption and raw-feature
tamper rejection. An accuracy bound alone does not establish historical byte
identity.

Windows v1 additionally checks all 530,890 current log cells against an 80-digit
reference and all 265,445 balance ratios by high-precision division. Direct ZIP
reconstruction verifies all 20 features for every eligible 2016 and 2018 loan
using only origination and the six-month lookback. The declared current hashes,
checker source, results, runtime, thread caps and all execution files are sealed
before fitting.

## Execution, comparison and outputs

The original script fits four fixed models and two adaptation-only intercepts.
It retains validation selection rules, the fitting-start marker, label-free
test snapshots and pre-evaluation model/prediction seals. The original evaluator
retains its exact snapshot/label feature-alignment assertion. Original internal
verification recomputes scores, review selections and scenario amounts without
refitting.

The [pre-fit comparison contract](../compatibility/reproduction_contract_v1.json)
is unchanged: exact discrete values and
`abs(new-old) <= 1e-10 + 1e-10*abs(old)` for every scientific floating value
in the eleven named JSON files. Only individually enumerated timestamps and
generated hashes are excluded. The complete Windows comparison retains the
five non-matching input-related digests and therefore remains failed, even
though every numeric field passes. The separate 76-field display comparison
and decision assessment use only the originally prespecified rules.

No tolerance widening, candidate expansion, or repeated fitting for a closer
match is allowed. Similar aggregate values cannot establish historical rowwise
predictions. Raw and explicitly LF-normalized prediction hashes, plus model
binary identity, are reported separately.

Top-level historical reports are archived in the reproduction workspace under
`reports/portable/historical/` before preparation. Newly generated evidence is
written under `reports/windows_verification_v1/`, with current scientific JSONs
under `current/`. The public dated copy is
`reports/portable_20261026/`; original published reports remain unchanged.

Original report builders retain historical dates, degree-program bylines and
some fixed narrative values. Use current JSON and the dated execution report
for new-run claims. Raw rows, IDs, SQL caches, prepared tables, fitted objects
and row-level predictions remain in ignored private directories.
