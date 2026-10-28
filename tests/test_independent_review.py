from dataclasses import replace
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validation.review import (MODELS, ReviewPolicy, annual_review, assert_equal,
                               check_predictions, feature_psi, govern, metrics,
                               integral_count, evidence_boolean)


def example():
    frame = pd.DataFrame({"CERT": [3, 1, 2], "report_date": ["2021-12-31"] * 3,
                          "prediction_date": ["2022-04-01"] * 3, "horizon_end": ["2023-04-01"] * 3,
                          "failure_date": ["", "2022-10-01", ""], "failure": [0, 1, 0],
                          "nonfailure_exit": [0, 0, 1]})
    for name in MODELS:
        frame["p_" + name] = [0.5, 0.5, 0.1]
    return frame


class MetricTests(unittest.TestCase):
    def test_tie_correct_auc_and_average_precision(self):
        result = metrics([0, 1, 0], [0.5, 0.5, 0.1], 0.5)
        self.assertEqual(result["auc"], 0.75)
        self.assertEqual(result["average_precision"], 0.5)
        self.assertAlmostEqual(result["brier"], (0.25 + 0.25 + 0.01) / 3)
        self.assertEqual(result["test_caught_failures"], 1)
        self.assertEqual(result["false_positives"], 1)
        self.assertAlmostEqual(result["weighted_cost_per_row"], 1 / 3)

    def test_single_class_and_monitor_none_are_explicit(self):
        result = metrics([0, 0], [0, 1], np.nextafter(1.0, np.inf))
        self.assertIsNone(result["auc"])
        self.assertIsNone(result["average_precision"])
        self.assertEqual(result["test_monitor_count"], 0)
        self.assertTrue(np.isfinite(result["log_loss"]))

    def test_probability_label_and_cost_domains(self):
        for y, p, threshold, weight in (([0, 1], [0.1, np.nan], 0.5, 100), ([0, 2], [0.1, 0.5], 0.5, 100),
                                          ([0, 1], [0.1, 1.1], 0.5, 100), ([0, 1], [0.1, 0.5], np.inf, 100),
                                          ([0, 1], [0.1, 0.5], 0.5, 0), ([], [], 0.5, 100)):
            with self.subTest(y=y, p=p), self.assertRaises(ValueError):
                metrics(y, p, threshold, weight)

    def test_capacity_ties_use_certificate_and_preserve_small_cohort(self):
        row = annual_review(example(), "constant", 0.5)[0]
        self.assertEqual(row["review_capacity"], 1)
        self.assertEqual(row["captured_failures_at_capacity"], 1)
        self.assertEqual(row["test_monitor_count"], 2)

    def test_exact_counts_not_tolerant(self):
        with self.assertRaises(ValueError): assert_equal(1000000001, 1000000000, "count")
        with self.assertRaises(ValueError): assert_equal(1.0, 1, "integer type")
        with self.assertRaises(ValueError): assert_equal(float("nan"), 0.0, "metric")
        assert_equal(0.5 + 1e-14, 0.5, "roundoff")

    def test_saved_counts_and_booleans_never_coerce_invalid_evidence(self):
        for value in (1.5, float("nan"), float("inf"), -1, True, "1"):
            with self.assertRaises(ValueError): integral_count(value, "rows")
        self.assertEqual(integral_count(3.0, "rows"), 3)
        for value in ("False", "True", "maybe", 0, 1, float("nan")):
            with self.assertRaises(ValueError): evidence_boolean(value, "monitor")
        self.assertFalse(evidence_boolean(False, "monitor"))


class PredictionContractTests(unittest.TestCase):
    def test_valid_rows(self):
        check_predictions(example())

    def test_schema_duplicates_and_keys(self):
        for frame in (example().drop(columns="p_constant"), pd.concat([example(), example()]), example().assign(CERT=[0, 1, 2])):
            with self.assertRaises(ValueError): check_predictions(frame)

    def test_event_censoring_and_temporal_boundaries(self):
        for frame in (example().assign(horizon_end="2022-04-01"), example().assign(failure=[0, 0, 0]),
                      example().assign(nonfailure_exit=[0, 1, 1]), example().assign(prediction_date="2021-04-01")):
            with self.assertRaises(ValueError): check_predictions(frame)


class DriftTests(unittest.TestCase):
    def test_identical_distribution_and_missing_bucket(self):
        a = [0, 1, 2, 3, np.nan]
        r = feature_psi(a, a)
        self.assertEqual(r["psi"], 0.0)
        self.assertEqual(r["training_counts"][-1], 1)
        self.assertEqual(sum(r["training_counts"]), 5)

    def test_bins_use_training_only_and_shift_is_detected(self):
        a = np.arange(100)
        original = feature_psi(a, a)
        shifted = feature_psi(a, np.arange(100, 200))
        self.assertEqual(original["finite_inner_edges"], shifted["finite_inner_edges"])
        self.assertGreater(shifted["psi"], 1)

    def test_empty_infinite_and_all_missing_training_rejected(self):
        for a, b in (([], [1]), ([1], []), ([np.nan], [1]), ([1], [np.inf])):
            with self.assertRaises(ValueError): feature_psi(a, b)


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.good = {"brier": 0.01, "constant_brier": 0.02, "max_feature_psi": 0.01, "late_recall": 0.9, "actual_vintages": True}

    def test_brier_rule_enforced(self):
        result = govern({**self.good, "brier": 0.9})
        self.assertEqual(result["status"], "RESTRICTED_RESEARCH")
        self.assertTrue({"brier", "brier_vs_constant"} <= {x["rule"] for x in result["findings"]})

    def test_missing_psi_never_defaults_to_zero(self):
        for value in (None, "absent"):
            d = dict(self.good)
            if value == "absent": del d["max_feature_psi"]
            else: d["max_feature_psi"] = value
            result = govern(d)
            self.assertEqual(result["status"], "INCOMPLETE_EVIDENCE")
            self.assertEqual(result["findings"][0]["kind"], "missing")

    def test_each_declared_policy_rule_is_effective(self):
        mutations = {"max_feature_psi": 0.5, "late_recall": 0.1, "actual_vintages": False}
        for key, value in mutations.items():
            with self.subTest(rule=key):
                result = govern({**self.good, key: value})
                self.assertIn(key, {x["rule"] for x in result["findings"]})
        self.assertIn("brier_vs_constant", {x["rule"] for x in govern({**self.good, "constant_brier": 0.001})["findings"]})

    def test_invalid_diagnostics_and_policy_fail_closed(self):
        for value in (float("nan"), float("inf"), -0.1, True):
            with self.assertRaises(ValueError): govern({**self.good, "brier": value})
        with self.assertRaises(ValueError): govern({**self.good, "actual_vintages": 1})
        with self.assertRaises(ValueError): ReviewPolicy(max_feature_psi=-1)
        with self.assertRaises(ValueError): ReviewPolicy(minimum_late_recall=2)

    def test_no_configured_trigger_is_not_deployment_approval(self):
        result = govern(self.good)
        self.assertEqual(result["status"], "RESEARCH_REVIEW_NO_CONFIGURED_TRIGGER")
        self.assertIn("no regulatory approval", result["scope"])


if __name__ == "__main__": unittest.main()
