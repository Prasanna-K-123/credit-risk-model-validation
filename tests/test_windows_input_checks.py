"""Independent raw feature checks must detect a changed feature and ignore future data."""
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
from windows_input_checks import raw_feature_check
from mortgage_risk.portable_log1p import positive_log1p


class WindowsRawFeatureTests(unittest.TestCase):
    def fixture(self, root):
        target = root/"data/raw"
        target.mkdir(parents=True)
        orig = [""]*31
        for i,value in {0:"750",1:"201801",5:"0",7:"P",8:"80",9:"30",10:"100000",
                        11:"80",12:"4",17:"SF",19:"SYNTHETIC",20:"P",21:"360",27:"N"}.items():
            orig[i]=value
        records=[]
        for month in range(7,13):
            perf=[""]*35
            for i,value in {0:"SYNTHETIC",1:str(201900+month),2:"90000",3:"00",10:"4"}.items():
                perf[i]=value
            records.append("|".join(perf))
        # An invalid future payload must never enter feature reconstruction.
        records.append("SYNTHETIC|202001|FUTURE_PAYLOAD_NOT_FOR_FEATURES")
        with zipfile.ZipFile(target/"sample_2018.zip","w") as z:
            z.writestr("sample_orig_2018.txt","|".join(orig)+"\n")
            z.writestr("sample_perf_2018.txt","\n".join(records)+"\n")
        row={"loan_id":"SYNTHETIC","fico":"750","dti":"30","ltv":"80","cltv":"80",
             "mi_pct":"0","original_term":"360","original_rate":"4","purpose":"P","occupancy":"P",
             "property_type":"SF","relief_refinance":"N","current_rate":"4","current_dq":"0",
             "max_dq_6m":"0","dq_months_6m":"0","balance_ratio_6m":"1",
             "modified_by_snapshot":"0","calendar_age":"24",
             "log_current_upb":str(positive_log1p(90000)),"log_original_upb":str(positive_log1p(100000))}
        return row

    def test_all_features_reconstruct_without_future_payload(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);row=self.fixture(root)
            result=raw_feature_check(root,{"year":2018,"as_of":201912},[row])
            self.assertTrue(result["passed"])
            self.assertEqual(result["numeric_cells_exact"]+result["categorical_cells_exact"],20)
            self.assertEqual(result["raw_feature_window_records"],6)

    def test_changed_numeric_feature_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);row=self.fixture(root);row["fico"]="749"
            with self.assertRaisesRegex(ValueError,"feature mismatch"):
                raw_feature_check(root,{"year":2018,"as_of":201912},[row])

    def test_changed_categorical_feature_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);row=self.fixture(root);row["purpose"]="C"
            with self.assertRaisesRegex(ValueError,"feature mismatch"):
                raw_feature_check(root,{"year":2018,"as_of":201912},[row])


if __name__ == "__main__":
    unittest.main()
