"""Run the frozen study, independent review and optional public presentation build."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "bank_monitoring"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BANK))

from validation.review import digest, review


def dump(path: Path, content) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/current")
    parser.add_argument("--refresh-public", action="store_true", help="Update generated public reports only after full replay and review succeed")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) and not output.parent.exists():
        raise ValueError("Choose an existing parent for external execution outputs")
    output.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    dump(output / "execution_receipt.json", {"started_at_utc": started_at, "status": "running", "command": "python scripts/reproduce.py"})
    started = time.perf_counter()
    environment = os.environ.copy()
    for variable, default in (("OPENBLAS_NUM_THREADS", "1"), ("OMP_NUM_THREADS", "2"), ("MKL_NUM_THREADS", "1")):
        environment.setdefault(variable, default)
    result = subprocess.run([sys.executable, str(BANK / "replay_fdic_temporal.py")], cwd=BANK,
                            env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output / "frozen_replay.log").write_text(result.stdout)
    print(result.stdout, end="")
    if result.returncode:
        dump(output / "failure.json", {"started_at_utc": started_at, "stage": "frozen_replay", "exit_code": result.returncode})
        dump(output / "execution_receipt.json", {"started_at_utc": started_at, "status": "failed", "stage": "frozen_replay", "exit_code": result.returncode})
        raise SystemExit(result.returncode)
    from benchmark_fdic_temporal import load_panel
    panel, protocol = load_panel()
    evidence = review(BANK / "reference/fdic_temporal", panel)
    dump(output / "independent_review.json", evidence)
    import numpy, pandas, scipy, sklearn
    source_paths = ("validation/__init__.py", "validation/review.py", "scripts/reproduce.py", "scripts/build_presentation.py", "scripts/release_guard.py")
    source_hashes = {name: digest(ROOT / name) for name in source_paths}
    match = re.search(r"Max probability error ([0-9.eE+-]+)", result.stdout)
    if match is None:
        raise ValueError("Successful frozen replay did not supply its probability comparison")
    receipt = {
        "started_at_utc": started_at, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "command": "python scripts/reproduce.py", "status": "passed",
        "execution": "Full pinned-source panel reconstruction, all registered fits/calibration/policy, final predictions and paired bootstrap, complete descriptive audit, independent score/cohort/case review.",
        "max_probability_error_from_original": float(match.group(1)),
        "eligible_rows": len(panel), "final_rows": len(panel.loc[panel.role.eq("test")]),
        "independent_numeric_and_case_checks": evidence["independent_numeric_and_case_checks"],
        "review_sha256": digest(output / "independent_review.json"),
        "protocol_sha256": digest(BANK / "reference/fdic_temporal/PROTOCOL.json"),
        "frozen_manifest_sha256": digest(BANK / "reference/fdic_temporal/artifact_manifest.json"),
        "review_source_sha256": source_hashes,
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "numpy": numpy.__version__, "pandas": pandas.__version__, "scipy": scipy.__version__,
                    "sklearn": sklearn.__version__, "thread_environment": {k: environment[k] for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}},
        "api_calls_required": 0, "paid_resources_used": False,
        "limitations": ["Uses pinned later-revised source objects, not original publication vintages.",
                        "Numerical replay tolerance was frozen in the original code (rtol 1e-8, atol 1e-9); this is not bitwise model identity.",
                        "Independent review is a second implementation within one portfolio, not an external institutional endorsement.",
                        "Governance status is a research restriction, not proof of production safety."]}
    dump(output / "execution_receipt.json", receipt)
    if args.refresh_public:
        for name in ("independent_review.json", "execution_receipt.json"):
            (ROOT / "reports" / name).write_bytes((output / name).read_bytes())
        subprocess.run([sys.executable, str(ROOT / "scripts/build_presentation.py")], cwd=ROOT, check=True)
    print(f"PASS: {len(panel):,} eligible rows; {evidence['independent_numeric_and_case_checks']} independent comparisons; {evidence['governance']['status']}.")


if __name__ == "__main__":
    main()
