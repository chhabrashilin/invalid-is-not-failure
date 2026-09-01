"""Verify the evaluator discriminates: FAIL_TO_PASS must FAIL on the unfixed repo.

Without this check a "pass" after the agent runs is not evidence of anything --
the test could have been passing all along, or `test_patch` could have failed to
apply and pytest could be reporting "no tests ran" as success (the exact defect
Phase 0 caught).

Uses no model and no API calls.

    python scripts/phase0/check_evaluator_baseline.py --config configs/phase0/phase05_matplotlib.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import yaml  # noqa: E402

from checkpoint.docker_env import (  # noqa: E402
    docker_available,
    image_exists_locally,
    remove_container,
    start_container,
)
from evaluation.evaluator import evaluate_container  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load((REPO_ROOT / args.config).read_text(encoding="utf-8"))
    inst = cfg["instance"]
    if not docker_available():
        print("STOP: docker unavailable")
        return 2
    if not image_exists_locally(inst["image"]):
        print(f"STOP: image not present: {inst['image']}")
        return 2

    started = datetime.now(timezone.utc)
    out_dir = REPO_ROOT / cfg["output"]["artifact_root"] / cfg["run_id"] / "baseline"
    out_dir.mkdir(parents=True, exist_ok=True)

    cid = start_container(inst["image"], workdir=inst["workdir"])
    try:
        ev = evaluate_container(
            container_id=cid,
            session_id="baseline-unfixed",
            instance_id=inst["instance_id"],
            test_command=cfg["evaluation"]["test_command"],
            benchmark_version=cfg["benchmark_version"],
            artifact_dir=out_dir,
            timeout=float(cfg["evaluation"]["timeout_s"]),
            test_patch_path=REPO_ROOT / cfg["evaluation"]["test_patch_file"],
            test_files=cfg["evaluation"]["test_files"],
            base_commit=inst["base_commit"],
        )
    finally:
        remove_container(cid)

    discriminates = (not ev.success) and ((ev.tests_failed or 0) > 0)
    payload = {
        "kind": "phase0_5_evaluator_baseline_check",
        "purpose": "FAIL_TO_PASS must FAIL on the unmodified repo",
        "instance_id": inst["instance_id"],
        "checked_at": started.isoformat(),
        "success_on_unfixed_repo": ev.success,
        "tests_passed": ev.tests_passed,
        "tests_failed": ev.tests_failed,
        "score": ev.score,
        "raw_artifact_sha256": ev.raw_artifact_sha256,
        "evaluator_discriminates": discriminates,
        "verdict": "OK" if discriminates else "EVALUATOR NOT DISCRIMINATIVE",
        "actual_spend_usd": 0.0,
        "model_calls": 0,
    }
    path = out_dir / "baseline_check.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"artifact={path}")
    return 0 if discriminates else 10


if __name__ == "__main__":
    raise SystemExit(main())
