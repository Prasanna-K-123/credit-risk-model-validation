import tempfile
from pathlib import Path
import unittest
import zipfile

from audit_uploads import audit_archive, calendar_label, month_index


class IntakeBoundaries(unittest.TestCase):
    def fixture(self, path, periods):
        ids = [b"F13Q10000001", b"F13Q10000002"]
        orig = []
        for loan in ids:
            row = [b""] * 31
            row[19] = loan
            orig.append(b"|".join(row) + b"\n")
        perf = []
        for loan, month in periods:
            row = [b""] * 35
            row[0], row[1] = loan, month
            perf.append(b"|".join(row) + b"\n")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("sample_orig_2013.txt", b"".join(orig))
            z.writestr("sample_perf_2013.txt", b"".join(perf))

    def test_calendar_boundary_and_invalid_month(self):
        self.assertEqual(month_index(b"201401") - month_index(b"201312"), 1)
        self.assertEqual(calendar_label(month_index(b"202002")), 202002)
        for value in [b"202000", b"202013", b"2020-1", b"189912"]:
            with self.assertRaises(ValueError):
                month_index(value)

    def test_duplicate_gap_and_orphan_are_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample_2013.zip"
            self.fixture(p, [(b"F13Q10000001", b"201312"),
                             (b"F13Q10000001", b"201312"),
                             (b"F13Q10000001", b"201402"),
                             (b"F13Q10000002", b"201401"),
                             (b"F13Q10000999", b"201401")])
            result = audit_archive(p, 2013)
            perf = result["members"]["perf"]
            self.assertEqual(perf["rows"], 5)
            self.assertEqual(perf["unique_loan_months"], 4)
            self.assertEqual(perf["duplicate_loan_months"], 1)
            self.assertEqual(perf["missing_internal_calendar_months"], 1)
            self.assertEqual(perf["rows_without_origination_key"], 1)
            self.assertFalse(result["structural_checks_pass"])

    def test_changed_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample_2013.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("sample_orig_2013.txt", b"bad\n")
                z.writestr("sample_perf_2013.txt", b"bad\n")
            with self.assertRaisesRegex(ValueError, "field count"):
                audit_archive(p, 2013)


if __name__ == "__main__":
    unittest.main()
