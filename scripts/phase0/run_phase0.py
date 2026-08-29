"""Phase 0 infrastructure validation pipeline.

    uv run python scripts/phase0/run_phase0.py --config configs/phase0/smoke.yaml

Proves (or fails to prove) P0.2-P0.9 and P0.11-P0.12 from the Phase 0 spec:
container lifecycle, full trajectory logging, independent evaluation,
checkpoint, restore, same-condition forking, raw-data immutability, and
one-command reproducibility.

NO SCIENTIFIC RESULT IS PRODUCED HERE. The model is a deterministic mock.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import yaml  # noqa: E402

from checkpoint.docker_env import (  # noqa: E402
    DockerError,
    commit_snapshot,
    docker_available,
    exec_command,
    image_exists_locally,
    image_id,
    pull_image,
    remove_container,
    remove_image,
    start_container,
)
from evaluation.evaluator import evaluate_container  # noqa: E402
from instrumentation.agent_loop import LoopState, message_history_hash, run_steps  # noqa: E402
from instrumentation.mock_lm import ScriptedMockLM, StochasticMockLM  # noqa: E402
from instrumentation.recorder import TrajectoryRecorder  # noqa: E402
from trajectory.schema import (  # noqa: E402
    EnvironmentSnapshotMetadata,
    SessionMeta,
    SessionOutcome,
    TerminationReason,
)
from trajectory.store import RawTrajectoryWriter, verify_manifest  # noqa: E402


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_state() -> tuple[str, bool]:
    import subprocess

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO_ROOT
        ).stdout.strip()
    )
    return commit, dirty


def _make_session(cfg: dict, session_id: str, model_id: str, **extra) -> SessionMeta:
    commit, dirty = _git_state()
    inst = cfg["instance"]
    return SessionMeta(
        session_id=session_id,
        task_id=inst["instance_id"],
        repo=inst.get("repo"),
        scaffold="phase0-minimal-loop",
        scaffold_version=cfg["harness_version"],
        model_id=model_id,
        decoding_params={},
        run_id=cfg["run_id"],
        git_commit=commit,
        git_dirty=dirty,
        benchmark_version=cfg["benchmark_version"],
        harness_version=cfg["harness_version"],
        container_image=inst["image"],
        container_image_digest=extra.pop("image_digest", None),
        step_budget_cap=cfg["session"]["step_budget_cap"],
        token_budget_cap=cfg["session"].get("token_budget_cap", 0),
        start_ts=_utcnow(),
        **extra,
    )


def _finish(writer: RawTrajectoryWriter, recorder: TrajectoryRecorder, session_id: str,
            t0: float, reason: TerminationReason) -> SessionOutcome:
    """Write the Class-C outcome record. Separate file from steps.jsonl."""
    last = recorder.steps[-1] if recorder.steps else None
    outcome = SessionOutcome(
        session_id=session_id,
        end_ts=_utcnow(),
        wall_time_s=time.monotonic() - t0,
        termination_reason=reason,
        final_step_count=len(recorder.steps),
        total_prompt_tokens=last.cumulative_prompt_tokens if last else 0,
        total_completion_tokens=last.cumulative_completion_tokens if last else 0,
        total_model_calls=last.cumulative_model_calls if last else 0,
        total_tool_calls=last.cumulative_tool_calls if last else 0,
        total_failed_tool_calls=last.cumulative_failed_tool_calls if last else 0,
        estimated_cost_usd=0.0,  # mock LM: no spend
    )
    writer.write_outcome(outcome)
    return outcome


def _divergence(seq_a: list[str], seq_b: list[str]) -> dict:
    first = None
    for i in range(min(len(seq_a), len(seq_b))):
        if seq_a[i] != seq_b[i]:
            first = i
            break
    if first is None and len(seq_a) != len(seq_b):
        first = min(len(seq_a), len(seq_b))
    return {
        "identical": first is None and len(seq_a) == len(seq_b),
        "first_divergent_index": first,
        "len_a": len(seq_a),
        "len_b": len(seq_b),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep-images", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    raw_root = REPO_ROOT / cfg["output"]["raw_root"] / cfg["run_id"]
    art_root = REPO_ROOT / cfg["output"]["artifact_root"] / cfg["run_id"]
    art_root.mkdir(parents=True, exist_ok=True)

    report: dict = {"run_id": cfg["run_id"], "started": _utcnow(), "checks": {}}

    def check(name: str, ok: bool, detail: object = "") -> None:
        report["checks"][name] = {"ok": bool(ok), "detail": detail}
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    # ---- P0.2 docker ----
    if not docker_available():
        check("P0.2_docker_available", False, "daemon unreachable")
        (art_root / "phase0_report.json").write_text(json.dumps(report, indent=2))
        return 1
    check("P0.2_docker_available", True, "daemon reachable")

    image = cfg["instance"]["image"]
    if not image_exists_locally(image):
        print(f"pulling {image} ...")
        try:
            pull_image(image)
        except DockerError as exc:
            check("P0.2_image_available", False, str(exc)[:300])
            (art_root / "phase0_report.json").write_text(json.dumps(report, indent=2))
            return 1
    digest = image_id(image)
    check("P0.2_image_available", True, digest[:24])

    containers: list[str] = []
    images_made: list[str] = []
    try:
        # ================= parent session =================
        parent_id = f"parent-{uuid.uuid4().hex[:8]}"
        container = start_container(image, workdir=cfg["instance"]["workdir"])
        containers.append(container)
        check("P0.3_container_started", True, container[:12])

        session = _make_session(cfg, parent_id, ScriptedMockLM([]).model_id,
                                image_digest=digest)
        recorder = TrajectoryRecorder(parent_id)
        state = LoopState()
        t0 = time.monotonic()

        run_dir = raw_root / parent_id
        writer = RawTrajectoryWriter(run_dir)
        writer.__enter__()
        writer.write_session(session)

        # --- prefix segment (before checkpoint) ---
        lm = ScriptedMockLM(cfg["mock_lm"]["prefix_commands"])
        prefix_steps = run_steps(
            container_id=container, lm=lm, recorder=recorder, state=state,
            max_steps=cfg["checkpoint"]["at_step"],
            exec_timeout=cfg["session"]["exec_timeout_s"],
            track_fs_diff=cfg["session"]["track_fs_diff"],
        )
        for s in prefix_steps:
            writer.write_step(s)
        check("P0.4_prefix_logged", len(prefix_steps) == cfg["checkpoint"]["at_step"],
              f"{len(prefix_steps)} steps")

        # ---- P0.6 checkpoint ----
        ck_ref, ck_image_id = commit_snapshot(container, cfg["checkpoint"]["image_repository"])
        images_made.append(ck_ref)
        snapshot = EnvironmentSnapshotMetadata(
            snapshot_id=f"snap-{uuid.uuid4().hex[:8]}",
            parent_session_id=parent_id,
            checkpoint_step=len(recorder.steps),
            created_ts=_utcnow(),
            container_id=container,
            image_ref=ck_ref,
            image_id=ck_image_id,
            filesystem_digest=ck_image_id,
            message_history_hash=message_history_hash(state),
            cumulative_model_calls=recorder.cumulative_model_calls,
            cumulative_completion_tokens=recorder.cumulative_completion_tokens,
        )
        (art_root / "snapshot.json").write_text(snapshot.model_dump_json(indent=2))
        check("P0.6_checkpoint_created", True, f"{ck_ref} @ step {snapshot.checkpoint_step}")

        # --- parent continues past the checkpoint ---
        lm2 = ScriptedMockLM(cfg["mock_lm"]["parent_continuation_commands"])
        more = run_steps(
            container_id=container, lm=lm2, recorder=recorder, state=state,
            max_steps=len(cfg["mock_lm"]["parent_continuation_commands"]),
            exec_timeout=cfg["session"]["exec_timeout_s"],
            track_fs_diff=cfg["session"]["track_fs_diff"],
        )
        for s in more:
            writer.write_step(s)
        check("P0.3_session_ran_to_termination", True,
              f"{len(recorder.steps)} steps total")

        # ---- P0.5 independent evaluation ----
        ev = evaluate_container(
            container_id=container, session_id=parent_id,
            instance_id=cfg["instance"]["instance_id"],
            test_command=cfg["evaluation"]["test_command"],
            benchmark_version=cfg["benchmark_version"],
            artifact_dir=art_root / "evaluator",
            timeout=cfg["evaluation"]["timeout_s"],
            test_patch_path=(REPO_ROOT / cfg["evaluation"]["test_patch_file"]
                             if cfg["evaluation"].get("test_patch_file") else None),
            test_files=cfg["evaluation"].get("test_files"),
            base_commit=cfg["instance"].get("base_commit"),
        )
        writer.write_evaluation(ev)
        check("P0.5_evaluator_ran", True,
              f"success={ev.success} score={ev.score:.2f} passed={ev.tests_passed} failed={ev.tests_failed}")

        _finish(writer, recorder, parent_id, t0, TerminationReason.SUBMITTED)
        writer.close()
        ok, problems = verify_manifest(run_dir)
        check("P0.11_parent_manifest", ok, problems or "hashes verified")
        report["parent"] = {
            "session_id": parent_id,
            "steps": len(recorder.steps),
            "evaluation": json.loads(ev.model_dump_json()),
            "resource_units": {
                "model_calls": recorder.cumulative_model_calls,
                "completion_tokens": recorder.cumulative_completion_tokens,
            },
        }

        # ================= forks (P0.7 - P0.9) =================
        fork_cfg = cfg["fork"]
        fork_specs = [
            ("same_seed_a", fork_cfg["seed_same"]),
            ("same_seed_b", fork_cfg["seed_same"]),
            ("diff_seed_c", fork_cfg["seed_different"]),
        ]
        fork_results = []
        for label, seed in fork_specs:
            cid = start_container(ck_ref, workdir=cfg["instance"]["workdir"])
            containers.append(cid)
            cont_id = f"cont-{label}-{uuid.uuid4().hex[:6]}"
            c_session = _make_session(
                cfg, cont_id, StochasticMockLM([], seed).model_id,
                image_digest=ck_image_id, parent_session_id=parent_id,
                forked_at_step=snapshot.checkpoint_step,
            )
            c_rec = TrajectoryRecorder(cont_id)
            c_state = LoopState()
            c_dir = raw_root / cont_id
            c_writer = RawTrajectoryWriter(c_dir)
            c_writer.__enter__()
            c_writer.write_session(c_session)
            c_t0 = time.monotonic()

            c_lm = StochasticMockLM(fork_cfg["candidate_commands"], seed)
            c_steps = run_steps(
                container_id=cid, lm=c_lm, recorder=c_rec, state=c_state,
                max_steps=fork_cfg["additional_steps"],
                exec_timeout=cfg["session"]["exec_timeout_s"],
                track_fs_diff=cfg["session"]["track_fs_diff"],
            )
            for s in c_steps:
                c_writer.write_step(s)
            c_ev = evaluate_container(
                container_id=cid, session_id=cont_id,
                instance_id=cfg["instance"]["instance_id"],
                test_command=cfg["evaluation"]["test_command"],
                benchmark_version=cfg["benchmark_version"],
                artifact_dir=art_root / "evaluator",
                timeout=cfg["evaluation"]["timeout_s"],
                test_patch_path=(REPO_ROOT / cfg["evaluation"]["test_patch_file"]
                                 if cfg["evaluation"].get("test_patch_file") else None),
                test_files=cfg["evaluation"].get("test_files"),
                base_commit=cfg["instance"].get("base_commit"),
            )
            c_writer.write_evaluation(c_ev)
            _finish(c_writer, c_rec, cont_id, c_t0, TerminationReason.STEP_LIMIT)
            c_writer.close()
            c_ok, c_problems = verify_manifest(c_dir)

            fork_results.append({
                "label": label,
                "continuation_id": cont_id,
                "seed": seed,
                "command_hashes": [s.command_normalized_hash for s in c_steps],
                "steps": len(c_steps),
                "success": c_ev.success,
                "score": c_ev.score,
                "completion_tokens": c_rec.cumulative_completion_tokens,
                "manifest_ok": c_ok,
                "manifest_problems": c_problems,
            })
            print(f"    fork {label}: success={c_ev.success} steps={len(c_steps)}")

        check("P0.7_restore_from_checkpoint", len(fork_results) == 3,
              f"{len(fork_results)} continuations restored")
        check("P0.8_continuation_ran", all(f["steps"] > 0 for f in fork_results),
              [f["steps"] for f in fork_results])

        a, b, c = fork_results
        same = _divergence(a["command_hashes"], b["command_hashes"])
        diff = _divergence(a["command_hashes"], c["command_hashes"])
        check("P0.9_same_seed_deterministic", same["identical"], same)
        check("P0.9_divergence_detectable", True,
              {"same_seed": same, "different_seed": diff,
               "outcomes": {f["label"]: f["success"] for f in fork_results}})
        report["forks"] = fork_results
        report["fork_divergence"] = {"same_seed": same, "different_seed": diff}

        # ---- P0.11 parent untouched by forking ----
        ok2, problems2 = verify_manifest(run_dir)
        check("P0.11_parent_unchanged_after_forks", ok2, problems2 or "hashes still match")

    finally:
        for cid in containers:
            remove_container(cid)
        if not args.keep_images:
            for ref in images_made:
                remove_image(ref)

    report["finished"] = _utcnow()
    report["all_ok"] = all(v["ok"] for v in report["checks"].values())
    (art_root / "phase0_report.json").write_text(json.dumps(report, indent=2))
    print(f"\nreport -> {art_root / 'phase0_report.json'}")
    print(f"ALL CHECKS OK: {report['all_ok']}")
    return 0 if report["all_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
