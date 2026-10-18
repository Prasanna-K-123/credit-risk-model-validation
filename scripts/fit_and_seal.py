"""Fit exactly four fixed models/two intercepts; seal before test labels."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import warnings
import joblib
import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from mortgage_risk.modelling import (FEATURES, CATEGORICAL, NUMERIC, pipeline,
                                    raw_logits, intercept_update, choose_variant, choose_family)


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def read_frame(path):
    frame=pd.read_csv(path,dtype={x:str for x in ["loan_id"]+CATEGORICAL},keep_default_na=False)
    for column in NUMERIC+(["label"] if "label" in frame else []):
        frame[column]=pd.to_numeric(frame[column],errors="coerce")
    for column in CATEGORICAL:
        frame[column]=frame[column].replace("","MISSING")
    return frame


def verify_prefit():
    seal=json.loads((ROOT/"reports/prefit_manifest.json").read_text())
    for name,digest in seal["method_files"].items():
        if sha(ROOT/name)!=digest:
            raise ValueError("Pre-fit method seal changed: "+name)
    preparation=json.loads((ROOT/"reports/preparation.json").read_text())
    if preparation["test_outcomes_accessed"]:
        raise ValueError("Test separation failed")
    for item in preparation["prepared"]:
        p=ROOT/f'data/prepared/{item["role"]}_{item["year"]}.csv'
        if sha(p)!=item["private_table_sha256"]:
            raise ValueError("Prepared data changed")
    return preparation


def main():
    preparation=verify_prefit()
    artifacts=ROOT/"artifacts"
    artifacts.mkdir(exist_ok=True)
    marker=artifacts/"training_started.json"
    if marker.exists():
        raise RuntimeError("A fit has already started here; use a clean checkout for reproduction")
    marker.write_text(json.dumps({"started_utc":datetime.now(timezone.utc).isoformat(),
                                  "full_fit_budget":4,"intercept_fit_budget":2})+"\n")
    train=pd.concat([read_frame(ROOT/f"data/prepared/train_{y}.csv") for y in [2012,2013]],ignore_index=True)
    adaptation=read_frame(ROOT/"data/prepared/adaptation_2015.csv")
    validation=read_frame(ROOT/"data/prepared/validation_2016.csv")
    train=train[train.label.notna()].copy()
    adaptation=adaptation[adaptation.label.notna()].copy()
    val=validation[validation.label.notna()].copy()
    pooled=pd.concat([train,adaptation],ignore_index=True)
    yval=val.label.to_numpy(float)
    models,updates,records,selected={},{},{},{}
    for family in ["logit","hgb"]:
        for variant,frame in [("unchanged",train),("retrained",pooled)]:
            model=pipeline(family)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                model.fit(frame[FEATURES],frame.label.to_numpy(int))
            failures=[str(x.message) for x in caught if issubclass(x.category,ConvergenceWarning)]
            if failures:
                raise RuntimeError("Fixed fit did not converge: "+repr(failures))
            key=f"{family}_{variant}"
            models[key]=model
            joblib.dump(model,artifacts/f"{key}.joblib",compress=3)
            print(json.dumps({"fit":key,"known_training_rows":len(frame),
                              "iterations":np.asarray(model.named_steps['model'].n_iter_).tolist(),
                              "convergence_warnings":failures}),flush=True)
        original=models[f"{family}_unchanged"]
        updates[family]=intercept_update(raw_logits(original,adaptation),adaptation.label.to_numpy(int))
        scores={}
        for variant in ["unchanged","recalibrated","retrained"]:
            m=models[f'{family}_{"unchanged" if variant=="recalibrated" else variant}']
            delta=updates[family]["delta"] if variant=="recalibrated" else 0.
            p=expit(raw_logits(m,val)+delta)
            scores[variant]=float(np.mean((p-yval)**2))
        records[family]=scores
        selected[family]=choose_variant(scores)
    recommendation=choose_family(records["logit"][selected["logit"]],records["hgb"][selected["hgb"]])
    predictions={}
    for c in preparation["prepared"]:
        if c["has_forward_labels"]:
            continue
        role,year=c["role"],c["year"]
        frame=read_frame(ROOT/f"data/prepared/{role}_{year}.csv")
        if "label" in frame or "label_reason" in frame:
            raise ValueError("Held-out snapshot contains outcomes")
        pred=frame[["loan_id"]].copy()
        for family,variant in selected.items():
            model=models[f'{family}_{"unchanged" if variant=="recalibrated" else variant}']
            delta=updates[family]["delta"] if variant=="recalibrated" else 0.
            pred[family]=expit(raw_logits(model,frame)+delta)
        path=artifacts/f"predictions_{year}.csv"
        pred.to_csv(path,index=False,float_format="%.17g")
        predictions[str(year)]={"rows":len(pred),"sha256":sha(path),
                                "snapshot_sha256":c["private_table_sha256"]}
    seal={"sealed_utc":datetime.now(timezone.utc).isoformat(),
          "protocol_sha256":sha(ROOT/"docs/PROTOCOL.md"),
          "prefit_manifest_sha256":sha(ROOT/"reports/prefit_manifest.json"),
          "preparation_sha256":sha(ROOT/"reports/preparation.json"),
          "validation_brier":records,"selected_variants":selected,
          "recommended_family_from_validation":recommendation,
          "intercept_updates":updates,"full_fits":4,"intercept_fits":2,
          "known_fit_rows":{"training":len(train),"adaptation":len(adaptation),"validation":len(val)},
          "models":{p.name:sha(p) for p in sorted(artifacts.glob("*.joblib"))},
          "test_prediction_files":predictions,"test_outcomes_accessed":False}
    (ROOT/"reports/selection.json").write_text(json.dumps(seal,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:seal[k] for k in ["selected_variants","recommended_family_from_validation","validation_brier","full_fits","intercept_fits"]},indent=2))


if __name__=="__main__":
    main()
