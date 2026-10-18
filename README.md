# Credit Risk and Model Validation Under Economic Stress

A retrospective mortgage-monitoring study: when does good risk ranking stop
producing reliable probabilities and useful review decisions?

**Current status:** data engineering checkpoint. The 2012 source sample and its
training-cohort construction are audited. The six-vintage study protocol is fixed;
five source files, model fitting and held-out evaluation remain pending. There
are no model-performance or financial-impact claims yet.

- [Analysis protocol](docs/PROTOCOL.md)
- [Data provenance and limitations](docs/DATA.md)
- [Source audit](reports/data_audit_2012.json)
- [Training-cohort audit](reports/cohort_audit_train_2012.json)

## Reproduce the available data checkpoint

Before fitting, run the source-input gate against the downloaded ZIP directory:

```bash
python scripts/check_data_ready.py --source-dir /path/to/downloads
```

Exit code 2 identifies missing, unaudited or changed sources and blocks progress
to fitting. A pass still requires the protocol's separate cross-cohort checks.

Python 3.12.14; this stage uses the standard library only (SQLite 3.53.1 in the
recorded environment). Obtain the official ZIP under Freddie Mac's terms.
The audited source checksum is enforced by the importer.

```bash
python scripts/ingest_audit.py --zip /path/to/sample_2012.zip --year 2012
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/build_cohort.py --year 2012 --as-of 201312 --role train
```

The importer reads the ZIP without extraction, checks every row, and writes a
local SQLite store. The SQL query restricts features to the snapshot and the
preceding five months. The separate label function distinguishes reported credit
distress, voluntary payoff, transfers and incomplete observation. Tests challenge
future-data leakage, calendar boundaries and misleading negative labels.

Raw data, loan IDs, private feature tables and SQLite files remain under ignored
local paths. Public outputs will contain aggregate research results only. The
study concerns already-originated US mortgages; it is not an Indian lending,
IFRS 9 compliance or live investment system.
