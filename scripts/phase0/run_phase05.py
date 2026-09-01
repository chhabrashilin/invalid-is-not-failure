"""Phase 0.5 real-agent pipeline.

    python scripts/phase0/run_phase05.py --config configs/phase0/phase05_matplotlib.yaml

Runs ONE genuine mini-SWE-agent trajectory against a real SWE-bench_Verified
instance with a real provider model, then:

  * evaluates it independently (clean state + official test_patch),
  * takes a real checkpoint at a pre-declared ONLINE step index,
  * restores that checkpoint and runs same-condition continuations,
  * measures divergence between continuations.

SEPARATION INVARIANTS
  * The agent never sees `test_patch`, FAIL_TO_PASS, or PASS_TO_PASS.
  * Provider infrastructure events (503 / timeout) are retried BELOW agent
    semantics and never become tool failures or behavioural features.
  * A run whose provider retries are exhausted is VALID_SCIENTIFIC_SAMPLE=false
    and receives NO Y_success.
  * The checkpoint index is a fixed fraction of the pre-declared step budget,
    never of the realized trajectory length.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "phase0"))

import yaml  # noqa: E402

from checkpoint.docker_env import (  # noqa: E402
    commit_snapshot,
    container_diff_summary,
    docker_available,
    exec_command,
    image_exists_locally,
    remove_container,
    start_container,
)
from evaluation.evaluator import evaluate_container  # noqa: E402
from instrumentation.mini_swe_adapter import (  # noqa: E402
    InstrumentationContext,
    InstrumentedAgent,
    Phase05GeminiModel,
    SpendCapExceeded,
    agent_library_version,
)
from instrumentation.provider_retry import (  # noqa: E402
    CallBudget,
    CallCapExceeded,
    CompositeCallBudget,
    GlobalAttemptLedger,
    NonRetryableProviderError,
    ProviderTimeout,
    ProviderUnavailable,
)
from instrumentation.recorder import TrajectoryRecorder  # noqa: E402
from trajectory.schema import (  # noqa: E402
    ContinuationRecord,
    ProviderFinalStatus,
    EnvironmentSnapshotMetadata,
    ExecutionBackend,
    SessionMeta,
    SessionOutcome,
    TerminationReason,
)
from trajectory.store import RawTrajectoryWriter  # noqa: E402

from preflight_gemini import (  # noqa: E402
    ALT_ENV,
    CREDENTIAL_ENV,
    load_agent_dotenv,
    load_windows_user_scope_env,
)

from minisweagent.environments.docker import DockerEnvironment  # noqa: E402
from minisweagent.exceptions import (  # noqa: E402
    FormatError,
    InterruptAgentFlow,
)

HISTORICAL_GLOBAL_PROVIDER_ATTEMPTS = 12
#: Upstream's shipped SWE-bench scaffold. Used unmodified: changing prompts
#: based on observed behaviour would invalidate the run.
SWEBENCH_AGENT_CONFIG = (
    Path(sys.prefix) / "Lib/site-packages/minisweagent/config/benchmarks/swebench.yaml"
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_state() -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO_ROOT
        ).stdout.strip()
    )
    return commit, dirty


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _messages_hash(messages: list[dict]) -> str:
    return _sha(json.dumps(messages, sort_keys=True, ensure_ascii=False, default=str))


class AttachedDockerEnvironment(DockerEnvironment):
    """DockerEnvironment bound to a container we already started.

    Upstream starts (and `--rm`s) its own container, which is incompatible with
    `docker commit` checkpointing and with restoring a snapshot. Only container
    ownership changes; `execute` remains the pinned upstream implementation.
    """

    def __init__(self, *, container_id: str, **kwargs):
        self._attached_container_id = container_id
        super().__init__(**kwargs)

    def _start_container(self):  # noqa: D102 - see class docstring
        self.container_id = self._attached_container_id

    def cleanup(self):  # container lifecycle is owned by the runner
        return

    def __del__(self):
        return


def _load_agent_templates() -> dict:
    """Read upstream's SWE-bench scaffold config, unmodified."""
    if not SWEBENCH_AGENT_CONFIG.is_file():
        raise SystemExit(f"upstream swebench config not found at {SWEBENCH_AGENT_CONFIG}")
    return yaml.safe_load(SWEBENCH_AGENT_CONFIG.read_text(encoding="utf-8"))


def _make_model(cfg: dict, budget, provider_records: list, scope: str):
    mcfg = cfg["model"]
    upstream = _load_agent_templates()
    return Phase05GeminiModel(
        model_name=mcfg["model_id"],
        model_kwargs={"temperature": mcfg.get("temperature", 0.0)},
        observation_template=upstream["model"]["observation_template"],
        cost_tracking="ignore_errors",
        call_budget=budget,
        provider_records=provider_records,
        provider_scope=scope,
        provider_retry_delays=tuple(mcfg.get("provider_retry_delays_s", [5.0, 15.0, 30.0])),
        provider_request_timeout_s=float(mcfg.get("provider_request_timeout_s", 90.0)),
        provider_retry_timeouts=True,
    )


def _make_agent(cfg: dict, model, container_id: str, recorder, *, step_limit: int,
                on_step=None, budget=None):
    upstream = _load_agent_templates()
    inst = cfg["instance"]
    env = AttachedDockerEnvironment(
        container_id=container_id,
        # `image` is required by upstream's config model but unused when
        # attaching: the container already exists and we own its lifecycle.
        image=inst["image"],
        **{k: v for k, v in upstream["environment"].items() if k != "environment_class"},
    )
    instr = InstrumentationContext(
        recorder=recorder,
        container_id=container_id,
        workdir=inst["workdir"],
        base_commit=inst["base_commit"],
        track_repo_changes=True,
        spend_cap_usd=float(cfg["model"].get("spend_cap_usd", 0.0)),
        call_budget=budget,
        on_step=on_step,
    )
    agent = InstrumentedAgent(
        model,
        env,
        instrumentation=instr,
        system_template=upstream["agent"]["system_template"],
        instance_template=upstream["agent"]["instance_template"],
        step_limit=step_limit,
        cost_limit=0.0,  # free tier: the call ledger is the real ceiling
    )
    return agent, instr, env


def _make_session(cfg: dict, session_id: str, **extra) -> SessionMeta:
    commit, dirty = _git_state()
    inst = cfg["instance"]
    return SessionMeta(
        session_id=session_id,
        task_id=inst["instance_id"],
        repo=inst.get("repo"),
        scaffold="mini-swe-agent/swebench",
        scaffold_version=agent_library_version(),
        execution_backend=ExecutionBackend.MINI_SWE_AGENT,
        agent_library_version=agent_library_version(),
        model_id=cfg["model"]["model_id"],
        decoding_params={"temperature": cfg["model"].get("temperature", 0.0)},
        run_id=cfg["run_id"],
        git_commit=commit,
        git_dirty=dirty,
        benchmark_version=cfg["benchmark_version"],
        harness_version=cfg["harness_version"],
        container_image=inst["image"],
        step_budget_cap=cfg["session"]["step_budget_cap"],
        token_budget_cap=cfg["session"].get("token_budget_cap", 0),
        start_ts=_utcnow(),
        **extra,
    )


def _termination_reason(exc: BaseException | None, exit_status: str) -> tuple[TerminationReason, bool]:
    """Map an agent ending to (reason, valid_scientific_sample)."""
    if isinstance(exc, ProviderUnavailable):
        return TerminationReason.PROVIDER_UNAVAILABLE, False
    if isinstance(exc, ProviderTimeout):
        return TerminationReason.PROVIDER_TIMEOUT, False
    if isinstance(exc, NonRetryableProviderError):
        # A 429 is provider infrastructure, not agent behaviour. Mapping it to
        # CRASH would let it escape the no-Y_success guard.
        record = getattr(exc, "record", None)
        if record is not None and record.provider_final_status == ProviderFinalStatus.RATE_LIMITED:
            return TerminationReason.PROVIDER_RATE_LIMITED, False
        return TerminationReason.CRASH, False
    if isinstance(exc, CallCapExceeded):
        return TerminationReason.CRASH, False
    if isinstance(exc, SpendCapExceeded):
        return TerminationReason.COST_LIMIT, True
    if exit_status in ("Submitted", "submitted"):
        return TerminationReason.SUBMITTED, True
    if exit_status in ("LimitsExceeded", "TimeExceeded", "RepeatedFormatError"):
        return TerminationReason.STEP_LIMIT, True
    if exc is not None:
        return TerminationReason.CRASH, True
    return TerminationReason.SUBMITTED, True


def _provider_totals(records: list) -> dict:
    return {
        "provider_physical_attempts": sum(r.provider_attempt_count for r in records),
        "provider_503_count": sum(r.provider_503_count for r in records),
        "provider_timeout_count": sum(r.provider_timeout_count for r in records),
        "provider_retry_delay_total_s": sum(r.provider_retry_delay_total for r in records),
        "logical_model_calls": len(records),
        "provider_final_statuses": [r.provider_final_status.value for r in records],
    }


def _normalized_commands(steps) -> list[str]:
    return [s.command_normalized_hash for s in steps]


def _divergence(a, b) -> dict:
    seq_a, seq_b = _normalized_commands(a), _normalized_commands(b)
    first = None
    for i in range(min(len(seq_a), len(seq_b))):
        if seq_a[i] != seq_b[i]:
            first = i
            break
    if first is None and len(seq_a) != len(seq_b):
        first = min(len(seq_a), len(seq_b))
    n = max(len(seq_a), len(seq_b))
    matches = sum(1 for x, y in zip(seq_a, seq_b) if x == y)
    return {
        "first_action_match": bool(seq_a and seq_b and seq_a[0] == seq_b[0]),
        "first_differing_action_index": first,
        "normalized_command_sequence_exact_match_fraction": (matches / n) if n else 1.0,
        "identical": first is None and len(seq_a) == len(seq_b),
        "len_a": len(seq_a),
        "len_b": len(seq_b),
    }


def _capture_patch(container_id: str, workdir: str) -> tuple[str, str]:
    res = exec_command(container_id, f"cd {workdir} && git diff")
    patch = res.stdout or ""
    return patch, _sha(patch)


def main() -> int:  # noqa: C901 - linear pipeline, kept in one place deliberately
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep-containers", action="store_true")
    ap.add_argument(
        "--run-id",
        help="Override the config run_id. Used ONLY to keep an earlier "
        "infrastructure-invalid run's artifacts intact when the protocol "
        "permits one same-configuration rerun. Changes no experimental "
        "parameter: task, prompt, scaffold, model and budgets come from the "
        "config either way.",
    )
    args = ap.parse_args()

    cfg = yaml.safe_load((REPO_ROOT / args.config).read_text(encoding="utf-8"))
    if args.run_id:
        cfg["run_id"] = args.run_id
    inst = cfg["instance"]
    mcfg = cfg["model"]
    run_id = cfg["run_id"]
    artifact_root = REPO_ROOT / cfg["output"]["artifact_root"] / run_id
    artifact_root.mkdir(parents=True, exist_ok=True)
    raw_root = REPO_ROOT / cfg["output"]["raw_root"] / run_id

    report: dict = {
        "kind": "phase0_5_real_agent_run",
        "run_id": run_id,
        "started_at": _utcnow(),
        "config_file": args.config,
        "model": mcfg["model_id"],
        "instance_id": inst["instance_id"],
        "actual_spend_usd": 0.0,
    }
    t_pipeline = time.monotonic()

    # ---- preflight ------------------------------------------------------
    load_agent_dotenv()
    load_windows_user_scope_env((CREDENTIAL_ENV, *ALT_ENV))
    if not __import__("os").environ.get(CREDENTIAL_ENV):
        print("STOP: Gemini credential unavailable")
        return 2
    if not docker_available():
        print("STOP: docker unavailable")
        return 2
    if not image_exists_locally(inst["image"]):
        print(f"STOP: image not present locally: {inst['image']}")
        return 2

    global_ledger = GlobalAttemptLedger.from_ledger(
        REPO_ROOT / mcfg["global_ledger"], initial_used=HISTORICAL_GLOBAL_PROVIDER_ATTEMPTS
    )
    model_budget = CallBudget.from_ledger(
        REPO_ROOT / mcfg["call_ledger"],
        max_calls=int(mcfg["max_physical_calls"]),
        initial_used=0,
        metadata={
            "model_id": mcfg["model_id"],
            "constant": "PHASE_0_5_36_FLASH_MAX_PHYSICAL_CALLS",
            "actual_spend_ceiling_usd": 0.0,
        },
    )
    budget = CompositeCallBudget(
        model_budget=model_budget, global_ledger=global_ledger, model_id=mcfg["model_id"]
    )
    report["ledger_at_start"] = {
        "model_specific_used": model_budget.used,
        "model_specific_remaining": model_budget.remaining,
        "global_provider_attempts": global_ledger.used,
    }

    problem_statement = json.loads(
        (REPO_ROOT / inst["spec_file"]).read_text(encoding="utf-8")
    )["problem_statement"]

    containers: list[str] = []
    snapshot_images: list[str] = []

    def _cleanup():
        if args.keep_containers:
            return
        for cid in containers:
            try:
                remove_container(cid)
            except Exception:
                pass

    # =====================================================================
    # PARENT TRAJECTORY
    # =====================================================================
    parent_session_id = f"parent-{uuid.uuid4().hex[:8]}"
    parent_container = start_container(inst["image"], workdir=inst["workdir"])
    containers.append(parent_container)

    recorder = TrajectoryRecorder(parent_session_id)
    provider_records: list = []
    checkpoint_state: dict = {}
    at_step = int(cfg["checkpoint"]["at_step"])

    model = _make_model(cfg, budget, provider_records, scope="parent")
    agent, instr, env = _make_agent(
        cfg,
        model,
        parent_container,
        recorder,
        step_limit=int(cfg["session"]["step_budget_cap"]),
        budget=budget,
    )

    def on_step(step):
        """ONLINE checkpoint rule: fires at a fixed fraction of the budget cap."""
        if len(instr.steps) != at_step or checkpoint_state:
            return
        t0 = time.monotonic()
        ref, img = commit_snapshot(
            parent_container, cfg["checkpoint"]["image_repository"]
        )
        snapshot_images.append(ref)
        checkpoint_state.update(
            {
                "snapshot_id": f"ckpt-{uuid.uuid4().hex[:8]}",
                "image_ref": ref,
                "image_id": img,
                "messages": json.loads(json.dumps(agent.messages, default=str)),
                "n_calls": agent.n_calls,
                "checkpoint_time_s": time.monotonic() - t0,
                "fs_changes": container_diff_summary(parent_container),
                "cumulative_model_calls": step.cumulative_model_calls,
                "cumulative_completion_tokens": step.cumulative_completion_tokens,
            }
        )
        print(f"[checkpoint] step {at_step} -> {ref} in {checkpoint_state['checkpoint_time_s']:.1f}s", flush=True)

    instr.on_step = on_step

    print(f"[parent] session={parent_session_id} container={parent_container[:12]}", flush=True)
    t_parent = time.monotonic()
    parent_exc: BaseException | None = None
    result: dict = {}
    try:
        result = agent.run(problem_statement)
    except (ProviderUnavailable, ProviderTimeout, NonRetryableProviderError,
            CallCapExceeded, SpendCapExceeded) as exc:
        parent_exc = exc
    except Exception as exc:  # noqa: BLE001 - record, never mask
        parent_exc = exc
    parent_wall_s = time.monotonic() - t_parent

    exit_status = (result or {}).get("exit_status", "")
    reason, valid_sample = _termination_reason(parent_exc, exit_status)
    parent_patch, parent_patch_hash = _capture_patch(parent_container, inst["workdir"])

    session = _make_session(cfg, parent_session_id)
    raw_dir = raw_root / parent_session_id
    with RawTrajectoryWriter(raw_dir) as writer:
        writer.write_session(session)
        for step in recorder.steps:
            writer.write_step(step)
        for rec in provider_records:
            writer.write_provider_call(rec)
        last = recorder.steps[-1] if recorder.steps else None
        outcome = SessionOutcome(
            session_id=parent_session_id,
            end_ts=_utcnow(),
            wall_time_s=parent_wall_s,
            termination_reason=reason,
            final_step_count=len(recorder.steps),
            total_prompt_tokens=last.cumulative_prompt_tokens if last else 0,
            total_completion_tokens=last.cumulative_completion_tokens if last else 0,
            total_model_calls=last.cumulative_model_calls if last else 0,
            total_tool_calls=last.cumulative_tool_calls if last else 0,
            total_failed_tool_calls=last.cumulative_failed_tool_calls if last else 0,
            estimated_cost_usd=0.0,
        )
        writer.write_outcome(outcome)

    report["parent"] = {
        "session_id": parent_session_id,
        "raw_dir": str(raw_dir.relative_to(REPO_ROOT)),
        "wall_time_s": parent_wall_s,
        "steps": len(recorder.steps),
        "exit_status": exit_status,
        "termination_reason": reason.value,
        "valid_scientific_sample": valid_sample,
        "exception": f"{type(parent_exc).__name__}: {parent_exc}" if parent_exc else None,
        "patch_hash": parent_patch_hash,
        "patch_bytes": len(parent_patch),
        "provider": _provider_totals(provider_records),
        "agent_cost_reported_usd": float(getattr(agent, "cost", 0.0) or 0.0),
    }
    (artifact_root / "parent_patch.diff").write_text(parent_patch, encoding="utf-8")
    print(f"[parent] steps={len(recorder.steps)} reason={reason.value} valid={valid_sample}", flush=True)

    # =====================================================================
    # INDEPENDENT EVALUATION (parent) - only for a valid sample
    # =====================================================================
    if valid_sample:
        t_eval = time.monotonic()
        ev = evaluate_container(
            container_id=parent_container,
            session_id=parent_session_id,
            instance_id=inst["instance_id"],
            test_command=cfg["evaluation"]["test_command"],
            benchmark_version=cfg["benchmark_version"],
            artifact_dir=artifact_root / "evaluator",
            timeout=float(cfg["evaluation"]["timeout_s"]),
            test_patch_path=REPO_ROOT / cfg["evaluation"]["test_patch_file"],
            test_files=cfg["evaluation"]["test_files"],
            base_commit=inst["base_commit"],
        )
        report["parent"]["evaluation"] = {
            "y_success": ev.success,
            "passed": ev.tests_passed,
            "failed": ev.tests_failed,
            "score": ev.score,
            "evaluator_time_s": time.monotonic() - t_eval,
            "raw_artifact_sha256": ev.raw_artifact_sha256,
        }
        print(f"[parent] Y_success={ev.success}", flush=True)
    else:
        report["parent"]["evaluation"] = {
            "y_success": None,
            "reason": "VALID_SCIENTIFIC_SAMPLE=false; no label assigned",
        }

    # =====================================================================
    # CHECKPOINT / CONTROLS
    # =====================================================================
    if not checkpoint_state:
        report["checkpoint"] = {
            "taken": False,
            "reason": f"trajectory ended before step {at_step}",
        }
        report["controls"] = []
    else:
        snap = EnvironmentSnapshotMetadata(
            snapshot_id=checkpoint_state["snapshot_id"],
            parent_session_id=parent_session_id,
            checkpoint_step=at_step,
            created_ts=_utcnow(),
            container_id=parent_container,
            image_ref=checkpoint_state["image_ref"],
            image_id=checkpoint_state["image_id"],
            filesystem_digest=_sha(str(checkpoint_state["fs_changes"])),
            message_history_hash=_messages_hash(checkpoint_state["messages"]),
            cumulative_model_calls=checkpoint_state["cumulative_model_calls"],
            cumulative_completion_tokens=checkpoint_state["cumulative_completion_tokens"],
        )
        (artifact_root / "snapshot.json").write_text(
            snap.model_dump_json(indent=2), encoding="utf-8"
        )
        report["checkpoint"] = {
            "taken": True,
            "rule": cfg["checkpoint"]["rule"],
            "at_step": at_step,
            "snapshot_id": snap.snapshot_id,
            "image_ref": snap.image_ref,
            "image_id": snap.image_id,
            "message_history_hash": snap.message_history_hash,
            "checkpoint_time_s": checkpoint_state["checkpoint_time_s"],
        }

        controls = list(cfg["fork"]["controls"])
        min_c = int(cfg["fork"].get("control_c_min_remaining_calls", 0))
        add_steps = int(cfg["fork"]["additional_steps"])
        arms: list[dict] = []
        for name in controls:
            if name == "CONTROL_C" and model_budget.remaining < min_c:
                arms.append({"arm": name, "skipped": "insufficient ledger allowance"})
                continue
            t_restore = time.monotonic()
            cid = start_container(snap.image_ref, workdir=inst["workdir"])
            containers.append(cid)
            restore_s = time.monotonic() - t_restore

            cont_id = f"cont-{name.lower()}-{uuid.uuid4().hex[:6]}"
            c_recorder = TrajectoryRecorder(cont_id)
            c_provider: list = []
            c_model = _make_model(cfg, budget, c_provider, scope=cont_id)
            c_agent, c_instr, _ = _make_agent(
                cfg, c_model, cid, c_recorder,
                step_limit=checkpoint_state["n_calls"] + add_steps,
                budget=budget,
            )
            # Restore identical continuation state: same messages, same counters.
            c_agent.messages = json.loads(json.dumps(checkpoint_state["messages"], default=str))
            c_agent.n_calls = checkpoint_state["n_calls"]
            c_agent.extra_template_vars |= {"task": problem_statement}

            # Mirror upstream `run()` semantics: a FormatError re-prompts and
            # the loop continues; any other InterruptAgentFlow is a normal,
            # scientifically valid ending (Submitted / LimitsExceeded / ...).
            t_fork = time.monotonic()
            c_exc: BaseException | None = None
            c_exit_status = ""
            for _ in range(add_steps):
                try:
                    c_agent.step()
                    c_agent.n_consecutive_format_errors = 0
                except (ProviderUnavailable, ProviderTimeout, NonRetryableProviderError,
                        CallCapExceeded, SpendCapExceeded) as exc:
                    c_exc = exc
                    break
                except FormatError as exc:
                    c_agent.cost += exc.messages[0].get("extra", {}).get("cost", 0.0)
                    c_agent.n_consecutive_format_errors += 1
                    c_agent.add_messages(*exc.messages)
                    if (0 < c_agent.config.max_consecutive_format_errors
                            <= c_agent.n_consecutive_format_errors):
                        c_exit_status = "RepeatedFormatError"
                        break
                except InterruptAgentFlow as exc:
                    c_agent.add_messages(*exc.messages)
                    c_exit_status = (
                        exc.messages[0].get("extra", {}).get("exit_status", "")
                        if exc.messages else type(exc).__name__
                    )
                    break
                except Exception as exc:  # noqa: BLE001 - record, never mask
                    c_exc = exc
                    break
            fork_s = time.monotonic() - t_fork

            c_reason, c_valid = _termination_reason(c_exc, c_exit_status)
            c_patch, c_patch_hash = _capture_patch(cid, inst["workdir"])

            c_session = _make_session(
                cfg, cont_id,
                parent_session_id=parent_session_id,
                forked_at_step=at_step,
            )
            c_raw = raw_root / cont_id
            with RawTrajectoryWriter(c_raw) as w:
                w.write_session(c_session)
                for step in c_recorder.steps:
                    w.write_step(step)
                for rec in c_provider:
                    w.write_provider_call(rec)
                c_last = c_recorder.steps[-1] if c_recorder.steps else None
                w.write_outcome(
                    SessionOutcome(
                        session_id=cont_id,
                        end_ts=_utcnow(),
                        wall_time_s=fork_s,
                        termination_reason=c_reason,
                        final_step_count=len(c_recorder.steps),
                        total_prompt_tokens=c_last.cumulative_prompt_tokens if c_last else 0,
                        total_completion_tokens=c_last.cumulative_completion_tokens if c_last else 0,
                        total_model_calls=c_last.cumulative_model_calls if c_last else 0,
                        total_tool_calls=c_last.cumulative_tool_calls if c_last else 0,
                        total_failed_tool_calls=c_last.cumulative_failed_tool_calls if c_last else 0,
                        estimated_cost_usd=0.0,
                    )
                )
                w.write_evaluation(
                    ContinuationRecord(
                        continuation_id=cont_id,
                        snapshot_id=snap.snapshot_id,
                        parent_session_id=parent_session_id,
                        checkpoint_step=at_step,
                        budget_additional_steps=add_steps,
                        replicate_index=len(arms),
                        arm="control",
                        started_ts=_utcnow(),
                    )
                )

            arm: dict = {
                "arm": name,
                "continuation_id": cont_id,
                "raw_dir": str(c_raw.relative_to(REPO_ROOT)),
                "restore_time_s": restore_s,
                "fork_time_s": fork_s,
                "steps": len(c_recorder.steps),
                "termination_reason": c_reason.value,
                "valid_scientific_sample": c_valid,
                "exception": f"{type(c_exc).__name__}: {c_exc}" if c_exc else None,
                "patch_hash": c_patch_hash,
                "patch_bytes": len(c_patch),
                "provider": _provider_totals(c_provider),
                "steps_detail": [
                    {
                        "step_id": s.step_id,
                        "command_head": s.command_head,
                        "normalized_command_hash": s.command_normalized_hash,
                        "exit_status": s.exit_status,
                    }
                    for s in c_recorder.steps
                ],
            }
            if c_valid:
                t_ce = time.monotonic()
                c_ev = evaluate_container(
                    container_id=cid,
                    session_id=cont_id,
                    instance_id=inst["instance_id"],
                    test_command=cfg["evaluation"]["test_command"],
                    benchmark_version=cfg["benchmark_version"],
                    artifact_dir=artifact_root / "evaluator",
                    timeout=float(cfg["evaluation"]["timeout_s"]),
                    test_patch_path=REPO_ROOT / cfg["evaluation"]["test_patch_file"],
                    test_files=cfg["evaluation"]["test_files"],
                    base_commit=inst["base_commit"],
                )
                arm["evaluation"] = {
                    "y_success": c_ev.success,
                    "passed": c_ev.tests_passed,
                    "failed": c_ev.tests_failed,
                    "evaluator_time_s": time.monotonic() - t_ce,
                }
            else:
                arm["evaluation"] = {
                    "y_success": None,
                    "reason": "VALID_SCIENTIFIC_SAMPLE=false; no label assigned",
                }
            arms.append(arm)
            print(
                f"[{name}] steps={len(c_recorder.steps)} valid={c_valid} "
                f"Y={arm['evaluation'].get('y_success')} remaining={model_budget.remaining}",
                flush=True,
            )
            # Store recorder for divergence comparison.
            arm["_steps"] = c_recorder.steps

        # ---- divergence between valid controls --------------------------
        valid_arms = [a for a in arms if a.get("valid_scientific_sample") and "_steps" in a]
        divergence = []
        for i in range(len(valid_arms)):
            for j in range(i + 1, len(valid_arms)):
                a, b = valid_arms[i], valid_arms[j]
                d = _divergence(a["_steps"], b["_steps"])
                d.update(
                    {
                        "pair": f"{a['arm']} vs {b['arm']}",
                        "logical_model_calls_a": a["provider"]["logical_model_calls"],
                        "logical_model_calls_b": b["provider"]["logical_model_calls"],
                        "physical_attempts_a": a["provider"]["provider_physical_attempts"],
                        "physical_attempts_b": b["provider"]["provider_physical_attempts"],
                        "patch_hash_equality": a["patch_hash"] == b["patch_hash"],
                        "evaluator_success_a": a["evaluation"].get("y_success"),
                        "evaluator_success_b": b["evaluation"].get("y_success"),
                        "outcome_flip": (
                            a["evaluation"].get("y_success")
                            != b["evaluation"].get("y_success")
                        ),
                    }
                )
                divergence.append(d)
        for a in arms:
            a.pop("_steps", None)
        report["controls"] = arms
        report["divergence"] = divergence
        report["valid_continuations"] = len(valid_arms)

    # =====================================================================
    report["ledger_at_end"] = {
        "model_specific_used": model_budget.used,
        "model_specific_remaining": model_budget.remaining,
        "global_provider_attempts": global_ledger.used,
        "max_physical_calls": int(mcfg["max_physical_calls"]),
    }
    report["pipeline_wall_time_s"] = time.monotonic() - t_pipeline
    report["completed_at"] = _utcnow()
    report["artifact_bytes"] = sum(
        p.stat().st_size for p in artifact_root.rglob("*") if p.is_file()
    )
    report["raw_bytes"] = sum(p.stat().st_size for p in raw_root.rglob("*") if p.is_file())

    (artifact_root / "phase05_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, default=str)[:4000])
    print(f"artifact={artifact_root / 'phase05_report.json'}")

    _cleanup()
    for ref in snapshot_images:
        if not args.keep_containers:
            subprocess.run(["docker", "rmi", "-f", ref], capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
