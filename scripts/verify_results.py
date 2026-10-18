"""Check original seals and recompute scores and public scenario amounts."""
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fit_and_seal import sha, verify_prefit, read_frame
from mortgage_risk.modelling import review_order

if __name__=="__main__":
    verify_prefit()
    selection=json.loads((ROOT/"reports/selection.json").read_text())
    final=json.loads((ROOT/"reports/final_evaluation.json").read_text())
    assert final["selection_sha256"]==sha(ROOT/"reports/selection.json")
    repair=json.loads((ROOT/"reports/evaluation_repair.json").read_text())
    assert sha(ROOT/repair["release_evaluator"])==repair["release_sha256"]
    aggregate=json.loads((ROOT/"reports/demo_aggregates.json").read_text())
    checks={"unchanged_prefit_method_files":True,"sealed_model_files":0,"sealed_test_predictions":0,
            "recomputed_brier_scores":0,"capacity_selections":0,"aggregate_scenario_cells":0}
    for name,digest in selection["models"].items():
        assert sha(ROOT/"artifacts"/name)==digest
        checks["sealed_model_files"]+=1
    excluded=set(json.loads((ROOT/"data/prepared/excluded_ids.json").read_text()))
    for vintage,role,outcome in [(2018,"stress_test","2020"),(2021,"transport_test","2023")]:
        path=ROOT/f"artifacts/predictions_{vintage}.csv"
        assert sha(path)==selection["test_prediction_files"][str(vintage)]["sha256"]
        checks["sealed_test_predictions"]+=1
        frame=read_frame(ROOT/f"data/cohorts/{role}_{vintage}.csv")
        frame=frame[~frame.loan_id.isin(excluded)].reset_index(drop=True)
        pred=pd.read_csv(path,dtype={"loan_id":str},float_precision="round_trip")
        assert np.array_equal(frame.loan_id,pred.loan_id)
        y=frame.label.to_numpy(float);known=np.isfinite(y);r=final["cohorts"][outcome]
        assert len(y)==r["eligible"] and int(known.sum())==r["known"]
        assert int(np.nansum(y))==r["events"] and int((~known).sum())==r["unresolved"]
        for family in ["logit","hgb"]:
            p=pred[family].to_numpy(float)
            assert np.isfinite(p).all() and np.all((p>=0)&(p<=1))
            assert abs(np.mean((p[known]-y[known])**2)-r["models"][family]["brier"])<1e-15
            checks["recomputed_brier_scores"]+=1
            order=review_order(p,pred.loan_id)
            for fraction,b in r["models"][family]["review_capacity"].items():
                ix=order[:b["reviewed"]]
                assert int(np.nansum(y[ix]))==b["known_positive_captured"]
                checks["capacity_selections"]+=1
                cell=next(c for c in aggregate["scenarios"] if c["outcome_year"]==outcome and c["model"]==family and c["capacity"]==fraction)
                expected=float((p[ix]*np.expm1(frame.log_current_upb.to_numpy(float)[ix])).sum())
                assert abs(cell["probability_weighted_reviewed_exposure_usd"]-expected)<1e-6
                checks["aggregate_scenario_cells"]+=1
            for cell in r["models"][family]["equal_count_calibration"]:assert cell["n"]>=30
        for cells in r["subgroups"].values():
            for cell in cells.values():assert cell.get("suppressed") or cell["n_known"]>=30
    assert len(aggregate["scenarios"])==12
    for name in ["TECHNICAL_REPORT.md","DECISION_MEMO.md","RECRUITER_BRIEF.md"]:
        assert (ROOT/"reports"/name).stat().st_size>500
    html=(ROOT/"docs/index.html").read_text()
    assert '__DATA__' not in html and 'loan_id' not in html
    for name in ["technical_report","decision_memo","protocol"]:
        assert (ROOT/f"docs/exports/{name}.html").stat().st_size>1000
    result={"passed":True,"checks":checks,"model_refits_during_verification":0,
            "source_terms":"Raw data/model artifacts remain private; aggregates only.",
            "gate_F":"Open: publication, live browser verification and tagged release required."}
    (ROOT/"reports/final_verification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2))
