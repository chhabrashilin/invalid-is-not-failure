"""Regenerate every controlled result (E1-E5) cited in the short paper.

    uv run python scripts/paper/reproduce_all.py

No paid API and no model inference is used. E1-E3 need a local Docker daemon and
one SWE-bench image; E4-E5 are pure-Python and always run. Each experiment writes
a machine-readable JSON file to results/paper/.

Every numeric claim in the paper must trace to one of these files.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

OUT_DIR = REPO_ROOT / "results" / "paper"
INSTANCE = "matplotlib__matplotlib-23412"
IMAGE = f"swebench/sweb.eval.x86_64.matplotlib_1776_{INSTANCE.split('__')[1]}:latest"
BASE_COMMIT = "f06c2c3abdaf4b90285ce5ca7fedbb8ace715911"
TEST_FILE = "lib/matplotlib/tests/test_patches.py"
TEST_ID = f"{TEST_FILE}::test_dash_offset_patch_draw[png]"
TEST_CMD = (
    "source /opt/miniconda3/bin/activate && conda activate testbed && cd /testbed && "
    f'python -m pytest -rA -q "{TEST_ID}"'
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, payload: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"  -> {path.relative_to(REPO_ROOT)}")
    return path


# ---------------------------------------------------------------------------
# E1: omitting the official test_patch silently destroys the SWE-bench verdict
# ---------------------------------------------------------------------------
def e1_test_patch_effect() -> dict:
    from checkpoint.docker_env import remove_container, start_container
    from evaluation.evaluator import evaluate_container

    patch = REPO_ROOT / f"configs/phase0/test_patch_{INSTANCE}.diff"
    arms = {}
    for arm, use_patch in (("without_test_patch", False), ("with_test_patch", True)):
        cid = start_container(IMAGE, workdir="/testbed")
        try:
            ev = evaluate_container(
                container_id=cid,
                session_id=f"e1-{arm}",
                instance_id=INSTANCE,
                test_command=TEST_CMD,
                benchmark_version="SWE-bench_Verified",
                artifact_dir=OUT_DIR / "e1_raw",
                timeout=1800.0,
                test_patch_path=patch if use_patch else None,
                test_files=[TEST_FILE] if use_patch else None,
                base_commit=BASE_COMMIT if use_patch else None,
            )
            arms[arm] = {
                "success": ev.success,
                "tests_passed": ev.tests_passed,
                "tests_failed": ev.tests_failed,
                "score": ev.score,
                "raw_artifact_sha256": ev.raw_artifact_sha256,
            }
        finally:
            remove_container(cid)

    return {
        "experiment": "E1",
        "claim": (
            "Omitting the official test_patch makes the FAIL_TO_PASS node id "
            "non-existent, so pytest collects nothing and the verdict is vacuous "
            "rather than a real failure signal."
        ),
        "instance_id": INSTANCE,
        "fail_to_pass_id": TEST_ID,
        "arms": arms,
        "corrected_invariant": (
            "The evaluator resets test files to base_commit and applies the "
            "official test_patch before running FAIL_TO_PASS."
        ),
        "generated_at": _now(),
    }


# ---------------------------------------------------------------------------
# E2: a failing test piped into `tail` reports success without pipefail
# ---------------------------------------------------------------------------
def e2_pipeline_exit_code() -> dict:
    from checkpoint.docker_env import exec_command, remove_container, start_container

    cases = {}
    cid = start_container(IMAGE, workdir="/testbed")
    try:
        for label, cmd in (
            ("failing_pipeline", "false | tail -5"),
            ("passing_pipeline", "true | tail -5"),
            ("failing_pytest_pipeline", f'python -c "import sys; sys.exit(1)" | tail -5'),
        ):
            cases[label] = {
                "command": cmd,
                "exit_status_with_pipefail": exec_command(cid, cmd, pipefail=True).exit_status,
                "exit_status_without_pipefail": exec_command(cid, cmd, pipefail=False).exit_status,
            }
    finally:
        remove_container(cid)

    masked = [
        k for k, v in cases.items()
        if v["exit_status_with_pipefail"] != 0 and v["exit_status_without_pipefail"] == 0
    ]
    return {
        "experiment": "E2",
        "claim": (
            "Without `set -o pipefail` a shell pipeline reports the status of its "
            "LAST stage, so a failing command piped into `tail` is recorded as a "
            "successful tool call and every failure-rate feature is biased toward zero."
        ),
        "cases": cases,
        "commands_whose_failure_is_masked": masked,
        "corrected_invariant": "Every agent command runs under `set -o pipefail`.",
        "generated_at": _now(),
    }


# ---------------------------------------------------------------------------
# E3: container-wide file counting is dominated by environment churn
# ---------------------------------------------------------------------------
def e3_repo_scoped_changes() -> dict:
    from checkpoint.docker_env import (
        container_diff_summary,
        exec_command,
        remove_container,
        start_container,
    )
    from instrumentation.repo_state import measure_repo_changes

    cid = start_container(IMAGE, workdir="/testbed")
    try:
        before_container = container_diff_summary(cid)
        before_repo = measure_repo_changes(cid, "/testbed", BASE_COMMIT)

        # Environment churn ONLY: no repository file is touched.
        exec_command(
            cid,
            "source /opt/miniconda3/bin/activate && conda activate testbed && "
            "cd /testbed && python -c \"import matplotlib, json, sys; print('warm')\"",
        )
        after_churn_container = container_diff_summary(cid)
        after_churn_repo = measure_repo_changes(cid, "/testbed", BASE_COMMIT)

        # One genuine single-line source edit.
        exec_command(
            cid,
            "cd /testbed && printf '\\n# measurement-integrity probe\\n' >> "
            "lib/matplotlib/patches.py",
        )
        after_edit_container = container_diff_summary(cid)
        after_edit_repo = measure_repo_changes(cid, "/testbed", BASE_COMMIT)
    finally:
        remove_container(cid)

    def repo_files(r) -> int:
        return r.files_modified + r.files_added + r.files_deleted

    return {
        "experiment": "E3",
        "claim": (
            "A container-wide file-change count attributes environment and cache "
            "churn to the agent; a repository-scoped git measurement attributes "
            "only the agent's own edits."
        ),
        "container_wide_docker_diff": {
            "at_start": before_container,
            "after_environment_churn_only": after_churn_container,
            "after_one_source_edit": after_edit_container,
        },
        "repository_scoped_git": {
            "at_start": repo_files(before_repo),
            "after_environment_churn_only": repo_files(after_churn_repo),
            "after_one_source_edit": repo_files(after_edit_repo),
            "lines_added_after_edit": after_edit_repo.lines_added,
            "measured_flag": after_edit_repo.measured,
        },
        "container_wide_inflation_from_churn": after_churn_container - before_container,
        "repo_scoped_inflation_from_churn": repo_files(after_churn_repo) - repo_files(before_repo),
        "corrected_invariant": (
            "Repository-change features are computed from git state scoped to the "
            "benchmark repository, with a `measured` flag so a failed measurement "
            "is never read as zero change."
        ),
        "generated_at": _now(),
    }


# ---------------------------------------------------------------------------
# E4: adversarial oracle/future-leakage regression (pure Python)
# ---------------------------------------------------------------------------
def e4_oracle_leakage() -> dict:
    from instrumentation.recorder import TrajectoryRecorder
    from trajectory.features import extract_model_a_features, extract_model_b_features
    from trajectory.schema import ActionType, SessionMeta, TrajectoryPrefix

    session = SessionMeta(
        session_id="e4",
        task_id="t",
        scaffold="mini-swe-agent",
        scaffold_version="2.4.6",
        model_id="deterministic",
        run_id="e4",
        git_commit="0" * 40,
        git_dirty=False,
        benchmark_version="SWE-bench_Verified",
        harness_version="paper",
        step_budget_cap=10,
        start_ts=_now(),
    )
    rec = TrajectoryRecorder("e4", start_monotonic=0.0)
    for i in range(3):
        rec.record_step(
            action_type=ActionType.BASH,
            command=f"echo step-{i}",
            prompt_tokens=10,
            completion_tokens=5,
            context_length_tokens=10,
            stdout="ok",
            exit_status=0,
        )
    k = 3
    baseline_prefix = TrajectoryPrefix(session, list(rec.steps), k)
    baseline = {
        **extract_model_a_features(baseline_prefix),
        **extract_model_b_features(baseline_prefix),
    }

    # Adversary: append absurdly predictive FUTURE steps after the cut.
    for i in range(20):
        rec.record_step(
            action_type=ActionType.BASH,
            command="echo THE-ANSWER-IS-FAILURE" if i % 2 else "echo catastrophe",
            prompt_tokens=10**6,
            completion_tokens=10**6,
            context_length_tokens=10**6,
            stdout="FATAL " * 100,
            stderr="FATAL " * 100,
            exit_status=127,
        )
    poisoned_prefix = TrajectoryPrefix(session, list(rec.steps), k)
    after = {
        **extract_model_a_features(poisoned_prefix),
        **extract_model_b_features(poisoned_prefix),
    }

    changed = {key: [baseline[key], after[key]] for key in baseline if baseline[key] != after[key]}

    # The prefix must also refuse to hand out steps at or beyond the cut.
    try:
        poisoned_prefix.step(k)
        boundary_enforced = False
        boundary_error = None
    except Exception as exc:
        boundary_enforced = True
        boundary_error = type(exc).__name__

    # And it must expose no outcome/Y_success attribute at all.
    outcome_attrs = [
        a for a in ("y_success", "success", "outcome", "evaluation", "termination_reason")
        if hasattr(poisoned_prefix, a)
    ]

    return {
        "experiment": "E4",
        "claim": (
            "Appending 20 maximally predictive future steps to a trajectory cannot "
            "change any online feature computed from the length-k prefix."
        ),
        "prefix_length_k": k,
        "future_steps_appended": 20,
        "n_features_compared": len(baseline),
        "features_changed_by_future_information": changed,
        "prefix_len_stays": len(poisoned_prefix),
        "reading_step_at_or_beyond_cut_raises": boundary_enforced,
        "boundary_error_type": boundary_error,
        "outcome_attributes_exposed_on_prefix": outcome_attrs,
        "corrected_invariant": (
            "Online feature extraction accepts only a TrajectoryPrefix, which holds "
            "a copy of the first k steps and exposes no outcome record."
        ),
        "generated_at": _now(),
    }


# ---------------------------------------------------------------------------
# E5: infrastructure-invalid executions may never receive a task label
# ---------------------------------------------------------------------------
def e5_infrastructure_invalid_labels() -> dict:
    from pydantic import ValidationError

    from trajectory.schema import (
        PROVIDER_INFRASTRUCTURE_TERMINATIONS,
        ScientificRunDisposition,
        TerminationReason,
    )

    results = {}
    for reason in sorted(TerminationReason, key=lambda r: r.value):
        infra = reason in PROVIDER_INFRASTRUCTURE_TERMINATIONS
        try:
            ScientificRunDisposition(
                session_id="e5",
                termination_reason=reason,
                valid_for_success_modelling=True,
                y_success=False,
            )
            labelling_allowed = True
        except ValidationError:
            labelling_allowed = False
        results[reason.value] = {
            "classified_as_provider_infrastructure": infra,
            "labelling_with_y_success_allowed": labelling_allowed,
        }

    violations = [
        r for r, v in results.items()
        if v["classified_as_provider_infrastructure"] and v["labelling_with_y_success_allowed"]
    ]

    # Observed dispositions from the real (provider-invalid) runs, if present.
    observed_path = REPO_ROOT / "artifacts/phase0_5/scientific_run_dispositions.json"
    observed = {}
    if observed_path.exists():
        d = json.loads(observed_path.read_text(encoding="utf-8"))
        observed = {
            "sessions": len(d["runs"]),
            "all_invalid": all(not r["valid_scientific_sample"] for r in d["runs"]),
            "all_unlabelled": all(r["y_success"] is None for r in d["runs"]),
            "termination_reasons": sorted({r["corrected_termination_reason"] for r in d["runs"]}),
        }

    return {
        "experiment": "E5",
        "claim": (
            "A run terminated by provider infrastructure (503, timeout, or quota) "
            "is not a task failure and is structurally prevented from receiving a "
            "Y_success label."
        ),
        "per_termination_reason": results,
        "invariant_violations": violations,
        "observed_real_runs": observed,
        "corrected_invariant": (
            "Provider-infrastructure terminations are enumerated in one set that a "
            "schema validator iterates, so a newly added reason cannot silently "
            "escape the rule."
        ),
        "generated_at": _now(),
    }


EXPERIMENTS = {
    "e1": ("e1_test_patch_effect.json", e1_test_patch_effect, True),
    "e2": ("e2_pipeline_exit_code.json", e2_pipeline_exit_code, True),
    "e3": ("e3_repo_scoped_changes.json", e3_repo_scoped_changes, True),
    "e4": ("e4_oracle_leakage.json", e4_oracle_leakage, False),
    "e5": ("e5_infrastructure_invalid_labels.json", e5_infrastructure_invalid_labels, False),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", choices=sorted(EXPERIMENTS), help="subset to run")
    ap.add_argument("--skip-docker", action="store_true")
    args = ap.parse_args()

    from checkpoint.docker_env import docker_available, image_exists_locally

    docker_ok = (not args.skip_docker) and docker_available() and image_exists_locally(IMAGE)
    if not docker_ok and not args.skip_docker:
        print(f"NOTE: docker or image unavailable ({IMAGE}); E1-E3 will be skipped.")

    selected = args.only or sorted(EXPERIMENTS)
    summary = {"generated_at": _now(), "experiments": {}}
    rc = 0
    for key in selected:
        name, fn, needs_docker = EXPERIMENTS[key]
        if needs_docker and not docker_ok:
            print(f"[{key.upper()}] SKIPPED (needs docker + {IMAGE})")
            summary["experiments"][key] = {"status": "skipped", "reason": "docker/image unavailable"}
            continue
        print(f"[{key.upper()}] running ...")
        t0 = time.monotonic()
        try:
            payload = fn()
            payload["wall_time_s"] = time.monotonic() - t0
            _write(name, payload)
            summary["experiments"][key] = {"status": "ok", "file": name}
        except Exception as exc:  # noqa: BLE001 - report, never fabricate
            print(f"[{key.upper()}] FAILED: {type(exc).__name__}: {exc}")
            summary["experiments"][key] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            rc = 1
    _write("summary.json", summary)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
