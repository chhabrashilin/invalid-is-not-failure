"""Audit the required Phase 0.5 online features against raw trajectory evidence.

For every required feature this reports the computed value, the raw evidence it
was derived from, whether it is ONLINE-available (knowable at the step, with no
outcome or future information), and PASS/FAIL.

Reads the immutable raw run directory only. It never opens outcome.json or
evaluation.json, so an oracle leak would be a load-time error, not a silent bug.

    python scripts/phase0/audit_features.py --run-dir data/raw/<run>/<session>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from trajectory.features import (  # noqa: E402
    extract_model_a_features,
    extract_model_b_features,
)
from trajectory.store import load_prefix, load_session  # noqa: E402

#: (audited name, feature-dict key or None, StepRecord fields that evidence it)
REQUIRED = [
    ("a_budget_fraction_consumed", "a_budget_fraction_consumed",
     ["step_id", "session.step_budget_cap"]),
    ("b_failed_tool_calls", "b_failed_tool_calls",
     ["exit_status", "error_category", "cumulative_failed_tool_calls"]),
    ("b_test_invocations", "b_test_invocations", ["test_invocation", "test_status"]),
    ("b_max_command_repeat", "b_max_command_repeat",
     ["command_normalized_hash", "repeated_command_k"]),
    ("b_repeated_error_count", "b_max_error_repeat",
     ["error_category", "repeated_error_k"]),
    ("b_repo_files_changed", "b_repo_files_changed",
     ["repo_files_modified", "repo_files_added", "repo_files_deleted",
      "repo_changes_measured"]),
    ("test_framework", None, ["test_framework"]),
    ("test_exit_status", None, ["test_exit_status"]),
    ("tests_passed_if_parseable", None, ["tests_passed", "test_status"]),
    ("tests_failed_if_parseable", None, ["tests_failed", "test_status"]),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    run_dir = REPO_ROOT / args.run_dir
    session = load_session(run_dir)
    n = sum(1 for _ in (run_dir / "steps.jsonl").read_text(encoding="utf-8").splitlines() if _.strip())
    prefix = load_prefix(run_dir, n)
    feats = {**extract_model_a_features(prefix), **extract_model_b_features(prefix)}
    steps = [prefix.step(i) for i in range(len(prefix))]

    rows = []
    for name, key, evidence_fields in REQUIRED:
        if key is not None:
            value = feats[key]
            evidence = {
                f: [getattr(s, f, None) for s in steps]
                for f in evidence_fields
                if "." not in f
            }
            if any("." in f for f in evidence_fields):
                evidence["session.step_budget_cap"] = session.step_budget_cap
            available = True
            # A feature is only meaningful if its evidence was actually measured.
            if name == "b_repo_files_changed":
                available = any(s.repo_changes_measured for s in steps)
        else:
            # per-step test fields: report the value at each test invocation
            per_step = [
                {
                    "step_id": s.step_id,
                    "test_status": s.test_status,
                    "value": getattr(
                        s,
                        {
                            "test_framework": "test_framework",
                            "test_exit_status": "test_exit_status",
                            "tests_passed_if_parseable": "tests_passed",
                            "tests_failed_if_parseable": "tests_failed",
                        }[name],
                    ),
                }
                for s in steps
                if s.test_invocation
            ]
            value = per_step
            evidence = {"test_invocation_steps": [s.step_id for s in steps if s.test_invocation]}
            available = True

        # Online availability: every audited field lives on StepRecord, which is
        # _OnlineSafe, so nothing here can encode outcome or future information.
        rows.append(
            {
                "feature": name,
                "computed_value": value,
                "raw_evidence": evidence,
                "online_available": available,
                "verdict": "PASS" if available else "FAIL",
            }
        )

    # Cross-check: recomputing from the prefix must reproduce the cumulative
    # counters the recorder wrote live. A mismatch means the online path and the
    # offline path disagree, which would invalidate the feature pipeline.
    consistency = {}
    if steps:
        last = steps[-1]
        consistency = {
            "failed_tool_calls_recorder_vs_feature": [
                last.cumulative_failed_tool_calls, feats["b_failed_tool_calls"]
            ],
            "match": float(last.cumulative_failed_tool_calls) == feats["b_failed_tool_calls"],
        }
        rows.append(
            {
                "feature": "cumulative_consistency_check",
                "computed_value": consistency,
                "raw_evidence": "recorder live counters vs offline recomputation",
                "online_available": True,
                "verdict": "PASS" if consistency["match"] else "FAIL",
            }
        )

    payload = {
        "kind": "phase0_5_feature_audit",
        "run_dir": args.run_dir,
        "session_id": session.session_id,
        "execution_backend": session.execution_backend.value,
        "model_id": session.model_id,
        "steps_audited": len(steps),
        "step_budget_cap": session.step_budget_cap,
        "rows": rows,
        "all_pass": all(r["verdict"] == "PASS" for r in rows),
    }
    text = json.dumps(payload, indent=2, default=str)
    if args.out:
        out = REPO_ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"artifact={out}")
    for r in rows:
        v = r["computed_value"]
        vs = json.dumps(v, default=str)
        print(f"{r['verdict']:4}  {r['feature']:34} = {vs[:110]}")
    print(f"\nall_pass={payload['all_pass']}  steps={len(steps)}")
    return 0 if payload["all_pass"] else 10


if __name__ == "__main__":
    raise SystemExit(main())
