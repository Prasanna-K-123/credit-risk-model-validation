import sqlite3
import unittest

from mortgage_risk.cohorts import outcome_12m, snapshot_rows
from mortgage_risk.schema import ORIGINATION, PERFORMANCE_STORED, add_months, month_index


def complete(as_of, dq="00"):
    return [(add_months(as_of, i), dq, "") for i in range(1, 13)]


class OutcomesTest(unittest.TestCase):
    def test_exact_window_and_boundary_event(self):
        records = complete(201912)
        records[-1] = (202012, "03", "")
        self.assertEqual(outcome_12m(records, 201912).value, 1)
        self.assertEqual(outcome_12m(complete(201912) + [(202101, "09", "")], 201912).value, 0)

    def test_payoff_is_competing_and_sale_is_censored(self):
        self.assertEqual(outcome_12m([(202001, "00", "01")], 201912).value, 0)
        for code in ["15", "16", "96"]:
            self.assertIsNone(outcome_12m([(202001, "00", code)], 201912).value)
        for code in ["02", "03", "09"]:
            self.assertEqual(outcome_12m([(202001, "00", code)], 201912).value, 1)

    def test_unknowns_gaps_and_truncation_cannot_make_negative(self):
        r = complete(201912)
        r[3] = (202004, "XX", "")
        self.assertIsNone(outcome_12m(r, 201912).value)
        self.assertIsNone(outcome_12m(complete(201912)[1:], 201912).value)
        self.assertIsNone(outcome_12m(complete(201912)[:-1], 201912).value)
        self.assertIsNone(outcome_12m([(202002, "00", "01")], 201912).value)
        r[-1] = (202012, "03", "")
        self.assertEqual(outcome_12m(r, 201912).value, 1)

    def test_reo_and_duplicate_failure(self):
        self.assertEqual(outcome_12m([(202001, "RA", "")], 201912).value, 1)
        with self.assertRaises(ValueError):
            outcome_12m([(202001, "00", ""), (202001, "01", "")], 201912)

    def test_calendar_boundaries(self):
        self.assertEqual(add_months(201912, 2), 202002)
        self.assertEqual(add_months(202001, -1), 201912)
        with self.assertRaises(ValueError):
            month_index(201913)


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE origination (" + ",".join(c + " TEXT" for c in ORIGINATION) + ")")
        self.db.execute("CREATE TABLE performance (" + ",".join(c + (" TEXT" if c in {"loan_id", "delinquency", "modification", "zero_balance_code", "zero_balance_date", "payment_deferral", "assistance_plan"} else " REAL") for c in PERFORMANCE_STORED) + ")")
        orig = dict.fromkeys(ORIGINATION, "")
        orig.update(loan_id="SYNTHETIC", fico="750", dti="999", ltv="80", cltv="80", mi_pct="0",
                    original_term="360", original_rate="4", original_upb="100000", first_payment_date="201801",
                    purpose="P", occupancy="P", property_type="SF", relief_refinance="N")
        self.db.execute("INSERT INTO origination VALUES (" + ",".join("?" for _ in ORIGINATION) + ")", [orig[c] for c in ORIGINATION])
        for month in range(7, 13):
            self.add_period(201900+month, "00", 90000, loan_age=1)

    def tearDown(self):
        self.db.close()

    def add_period(self, period, dq, balance, loan_age=12):
        item = dict.fromkeys(PERFORMANCE_STORED, "")
        item.update(loan_id="SYNTHETIC", period=period, current_upb=balance, delinquency=dq,
                    loan_age=loan_age, remaining_term=330, current_rate=4, non_interest_upb=0)
        self.db.execute("INSERT INTO performance VALUES (" + ",".join("?" for _ in PERFORMANCE_STORED) + ")", [item[c] for c in PERFORMANCE_STORED])

    def test_future_mutation_cannot_change_features_and_age_does_not_reset(self):
        before = snapshot_rows(self.db, 201912)
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0]["calendar_age"], 24)
        self.assertIsNone(before[0]["dti"])
        self.add_period(202001, "99", 9999999)
        self.assertEqual(before, snapshot_rows(self.db, 201912))

    def test_missing_history_prevents_snapshot(self):
        self.db.execute("DELETE FROM performance WHERE period=201908")
        self.assertEqual(snapshot_rows(self.db, 201912), [])


if __name__ == "__main__":
    unittest.main()
