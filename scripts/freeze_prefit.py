"""Seal implemented methods before any full fit or held-out outcome access."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

if __name__=="__main__":
    if (ROOT/"artifacts/training_started.json").exists():
        raise RuntimeError("Cannot replace the pre-fit seal after fitting starts")
    names=["study.json","requirements.txt","docs/PROTOCOL.md","docs/IMPLEMENTATION.md"]
    for directory in ["scripts","src","tests","sql"]:
        names += [str(p.relative_to(ROOT)) for p in (ROOT/directory).rglob("*")
                  if p.is_file() and p.suffix in {".py",".sql"}]
    result={"frozen_utc":datetime.now(timezone.utc).isoformat(),
            "full_model_fits_completed":0,"test_outcomes_accessed":False,
            "method_files":{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(names)},
            "runtime_versions":{n:importlib.metadata.version(n) for n in
                                ["numpy","scipy","pandas","scikit-learn","joblib"]}}
    (ROOT/"reports/prefit_manifest.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"method_files":len(names),"full_model_fits_completed":0,"test_outcomes_accessed":False}))
