"""Verify sealed predictions, then construct held-out labels once for reporting."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mortgage_risk.evaluation import metrics, paired_brier, wilson
from mortgage_risk.modelling import FEATURES, NUMERIC, CATEGORICAL, review_order, capacity_bounds
from build_cohort import build
from fit_and_seal import sha, read_frame, verify_prefit


def subgroup_labels(frame):
    fico=np.where(frame.fico.isna(),"missing",np.where(frame.fico<680,"<680",np.where(frame.fico<740,"680–739",">=740")))
    ltv=np.where(frame.ltv.isna(),"missing",np.where(frame.ltv<=80,"<=80",">80"))
    term=np.where(frame.original_term.isna(),"missing",np.where(frame.original_term<=180,"<=180",">180"))
    return {"fico":fico,"ltv":ltv,"original_term":term}


def main():
    preparation=verify_prefit()
    selection_path=ROOT/"reports/selection.json"
    selection=json.loads(selection_path.read_text())
    if selection["test_outcomes_accessed"] or sha(ROOT/"reports/prefit_manifest.json")!=selection["prefit_manifest_sha256"]:
        raise ValueError("Selection/protocol separation failed")
    for name,digest in selection["models"].items():
        if sha(ROOT/"artifacts"/name)!=digest:
            raise ValueError("Frozen fitted model changed")
    if sha(ROOT/"reports/preparation.json")!=selection["preparation_sha256"]:
        raise ValueError("Prepared input seal changed")
    for year,item in selection["test_prediction_files"].items():
        if sha(ROOT/f"artifacts/predictions_{year}.csv")!=item["sha256"]:
            raise ValueError("Frozen predictions changed")
    # From this line onward test labels may be observed; no fit/selection is called.
    excluded=set(json.loads((ROOT/"data/prepared/excluded_ids.json").read_text()))
    study=json.loads((ROOT/"study.json").read_text())
    train=pd.concat([read_frame(ROOT/f"data/prepared/train_{y}.csv") for y in [2012,2013]],ignore_index=True)
    results={"evaluated_utc":datetime.now(timezone.utc).isoformat(),
             "selection_sha256":sha(selection_path),"primary_outcome_year":2020,
             "secondary_outcome_year":2023,"cohorts":{}}
    for c in study["cohorts"]:
        if c["role"] not in {"stress_test","transport_test"}:
            continue
        year,role=c["year"],c["role"]
        unfiltered=build(year,c["as_of"],role)
        labelled=read_frame(ROOT/f"data/cohorts/{role}_{year}.csv")
        labelled=labelled[~labelled.loan_id.isin(excluded)].reset_index(drop=True)
        snapshot=read_frame(ROOT/f"data/prepared/{role}_{year}.csv")
        pd.testing.assert_frame_equal(snapshot[["loan_id"]+FEATURES],labelled[["loan_id"]+FEATURES],check_dtype=False,check_exact=True)
        pred=pd.read_csv(ROOT/f"artifacts/predictions_{year}.csv",dtype={"loan_id":str},float_precision="round_trip")
        if not np.array_equal(pred.loan_id,labelled.loan_id):
            raise ValueError("Prediction/label alignment failed")
        y=labelled.label.to_numpy(float)
        known=np.isfinite(y)
        n=len(y);positive=int(np.nansum(y));unresolved=int((~known).sum())
        result={"source_vintage":year,"outcome_year":int(str(c["as_of"])[:4])+1,
                "eligible":n,"known":int(known.sum()),"events":positive,
                "unresolved":unresolved,"unresolved_fraction":unresolved/n,
                "all_eligible_event_rate_bounds":[positive/n,(positive+unresolved)/n],
                "unconditional_approval_withheld_for_censoring":unresolved/n>.02,
                "models":{},"subgroups":{},"drift":{},
                "paired_brier":paired_brier(y[known],pred.logit.to_numpy()[known],pred.hgb.to_numpy()[known])}
        for family in ["logit","hgb"]:
            p=pred[family].to_numpy(float)
            m=metrics(y[known],p[known])
            order=review_order(p,pred.loan_id)
            m["review_capacity"]={}
            for fraction in study["review_capacities"]:
                k=math.ceil(fraction*n)
                mask=np.zeros(n,dtype=bool);mask[order[:k]]=True
                m["review_capacity"][str(fraction)]=capacity_bounds(y,mask)
            for row in m["equal_count_calibration"]:
                if row["n"]<30:
                    raise ValueError("Small calibration cell publication")
            result["models"][family]=m
        labels=subgroup_labels(labelled)
        for feature,strata in labels.items():
            result["subgroups"][feature]={}
            for name in sorted(set(strata)):
                mask=(strata==name)&known
                count=int(mask.sum())
                if count<30:
                    result["subgroups"][feature][name]={"suppressed":True,"reason":"Fewer than 30 known-outcome loans"}
                else:
                    events=int(y[mask].sum())
                    result["subgroups"][feature][name]={"n_known":count,"events":events,
                        "event_rate":events/count,"event_rate_wilson_95":wilson(events,count),
                        "few_event_caution":events<30,
                        "logit_brier":float(np.mean((pred.logit.to_numpy()[mask]-y[mask])**2)),
                        "hgb_brier":float(np.mean((pred.hgb.to_numpy()[mask]-y[mask])**2)),
                        "paired_brier":paired_brier(y[mask],pred.logit.to_numpy()[mask],pred.hgb.to_numpy()[mask])}
        for feature in NUMERIC:
            result["drift"][feature]={
                "training_missing_fraction":float(train[feature].isna().mean()),
                "test_missing_fraction":float(labelled[feature].isna().mean()),
                "training_median":float(train[feature].median()) if train[feature].notna().any() else None,
                "test_median":float(labelled[feature].median()) if labelled[feature].notna().any() else None}
        for feature in CATEGORICAL:
            result["drift"][feature]={"training_proportions":train[feature].value_counts(normalize=True).sort_index().to_dict(),
                                      "test_proportions":labelled[feature].value_counts(normalize=True).sort_index().to_dict()}
        result["reporting_exit_date_mismatches_all_source_records"]=json.loads((ROOT/f"reports/data_audit_{year}.json").read_text())["performance"]["anomalies"]["exit_effective_month_differs_from_reporting_month"]
        results["cohorts"][str(result["outcome_year"])]=result
        print(json.dumps({"cohort":result["outcome_year"],"known":result["known"],"events":positive,"unresolved":unresolved,"paired_brier":result["paired_brier"]}),flush=True)
    results["scope"]="Latest-release retrospective US mortgage monitoring; not Indian underwriting, regulatory default, a causal COVID effect or deployable historical release backtest."
    (ROOT/"reports/final_evaluation.json").write_text(json.dumps(results,indent=2,sort_keys=True,allow_nan=False)+"\n")


if __name__=="__main__":
    main()
