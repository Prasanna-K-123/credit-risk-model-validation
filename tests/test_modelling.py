import unittest
import numpy as np
from scipy.special import expit
from mortgage_risk.modelling import capacity_bounds, choose_family, choose_variant, intercept_update, review_order, pipeline, FEATURES, NUMERIC, CATEGORICAL
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))

spec = spec_from_file_location("prepare_study", Path(__file__).resolve().parents[1]/"scripts/prepare_study.py")
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


class ModellingRulesTest(unittest.TestCase):
    def test_transitive_links_external_parent_and_duplicate_failure(self):
        excluded, audit = mod.linked_later([(2012,"a","parent"),(2013,"b","parent"),
                                          (2015,"c","b"),(2016,"d","")])
        self.assertEqual(excluded, {"b","c"})
        self.assertEqual(audit["excluded_later_records"], 2)
        with self.assertRaises(ValueError):
            mod.linked_later([(2012,"a",""),(2013,"a","")])

    def test_recalibration_score_and_selection_tolerances(self):
        z, y = np.array([-3., -2., 0., 2.]), np.array([0,0,1,1])
        result = intercept_update(z,y)
        self.assertAlmostEqual(expit(z+result["delta"]).mean(), y.mean(), places=12)
        self.assertEqual(choose_variant({"unchanged":.01+5e-9,"recalibrated":.01,"retrained":.02}), "unchanged")
        self.assertEqual(choose_family(.01009,.01), "logit")
        self.assertEqual(choose_family(.01011,.01), "hgb")

    def test_capacity_bounds_enumerate_unknown_assignments(self):
        y = np.array([1,0,np.nan,np.nan])
        mask = np.array([True,False,True,False])
        b = capacity_bounds(y,mask)
        recalls = []
        for a in [0,1]:
            for c in [0,1]:
                assigned = np.array([1,0,a,c])
                recalls.append(assigned[mask].sum()/assigned.sum())
        self.assertEqual(b["capture_bounds"], [min(recalls),max(recalls)])
        self.assertEqual(b["precision_bounds"], [.5,1.])

    def test_capacity_ties_independent_of_input_order(self):
        ids = np.array(["b","a","c"])
        order = review_order([.2,.2,.3],ids)
        permutation = np.array([2,0,1])
        other = review_order(np.array([.2,.2,.3])[permutation],ids[permutation])
        self.assertEqual(list(ids[order]), list(ids[permutation][other]))

    def test_fitting_only_preprocessing_and_unknown_category(self):
        import pandas as pd
        frame=pd.DataFrame({c:[1.,3.,np.nan] for c in NUMERIC})
        for c in CATEGORICAL:
            frame[c]=["A","B","A"]
        frame["future_outcome"]=[0,1,1]
        for family in ["logit","hgb"]:
            pre=pipeline(family).named_steps["preprocess"]
            pre.fit(frame)
            imputer=pre.named_transformers_["numeric"].named_steps["impute"]
            before=imputer.statistics_.copy()
            test=frame.iloc[[0]].copy()
            test[NUMERIC]=1e9
            test[CATEGORICAL]="UNSEEN"
            transformed=pre.transform(test)
            self.assertTrue(np.isfinite(transformed).all())
            np.testing.assert_array_equal(imputer.statistics_,before)
            np.testing.assert_array_equal(before,np.full(len(NUMERIC),2.))
            self.assertNotIn("future_outcome",pre.get_feature_names_out())


if __name__ == "__main__":
    unittest.main()
