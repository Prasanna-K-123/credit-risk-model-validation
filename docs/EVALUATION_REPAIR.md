# Evaluation metadata repair

The first primary evaluation attempt stopped with a `KeyError` while adding a source-audit metadata count. The auditor stores that count under `performance.anomalies`; the initial evaluator requested a root-level key.

The original pre-fit evaluator and manifest remain unchanged. `evaluate_release.py` differs by that one lookup only. `reports/evaluation_repair.json` seals both source hashes and the unchanged selection record. It was committed before the repaired evaluator ran. Models, labels, metrics, bootstrap, subgroup rules and all saved predictions are unchanged; no model was refitted or reselected. The first attempt had computed primary results in memory before the metadata error, so the repair is explicitly recorded as occurring after primary-label access.
