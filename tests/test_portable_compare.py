"""A strict comparison must fail on changed scientific evidence."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from portable_compare import compare, report_precision


class PortableCompareTests(unittest.TestCase):
    def test_numeric_rule_and_exact_counts(self):
        self.assertTrue(compare({"metric": 0.04, "count": 10}, {"metric": 0.04+1e-12, "count": 10})["passed"])
        self.assertFalse(compare({"metric": 0.04}, {"metric": 0.04+1e-8})["passed"])
        self.assertFalse(compare({"count": 10}, {"count": 11})["passed"])
        self.assertFalse(compare({"count": 10}, {"count": 10.0})["passed"])

    def test_only_explicit_metadata_excluded(self):
        result = compare({"time": "old", "score": 0.1}, {"time": "new", "score": 0.2}, excluded=("/time",))
        self.assertFalse(result["passed"])
        self.assertEqual([d["path"] for d in result["differences"]], ["/score"])
        self.assertEqual(result["excluded_metadata"][0]["path"], "/time")

    def test_missing_keys_lists_and_nonfinite_fail(self):
        self.assertFalse(compare({"a": 1}, {})["passed"])
        self.assertFalse(compare([1, 2], [1])["passed"])
        self.assertFalse(compare({"x": float("nan")}, {"x": float("nan")})["passed"])

    def test_display_precision_is_distinct_and_explicit(self):
        fields = [{"file": "a", "path": "/brier", "decimal_places": 6}]
        old = {"a": {"brier": 0.04574312}}
        new = {"a": {"brier": 0.04574315}}
        self.assertFalse(compare(old, new)["passed"])
        self.assertTrue(report_precision(old, new, fields)["passed"])


if __name__ == "__main__":
    unittest.main()
