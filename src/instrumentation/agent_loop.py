"""Minimal instrumented agent loop (Phase 0 Step 7).

This is deliberately the *narrowest auditable point*: a loop that asks a model
for a bash command, runs it in the container, and records one StepRecord. It is
not a reimplementation of mini-SWE-agent -- it mirrors mini-SWE-agent's shape
(linear message history, bash-only actions, no tool-calling interface) so that
the instrumentation contract can be validated before that dependency is added.

Phase 0 does not claim this loop solves tasks. It claims the *recording* is
correct and the environment lifecycle works.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from checkpoint.docker_env import exec_command
from evaluation.test_detect import detect_and_parse
from instrumentation.recorder import TrajectoryRecorder, estimate_tokens
from instrumentation.repo_state import measure_repo_changes
from trajectory.schema import ActionType, StepRecord


class LMProtocol(Protocol):
    """Anything that can produce the next command."""

    @property
    def model_id(self) -> str: ...

    def next_response(self, messages: list[dict] | None = None) -> Any: ...


@dataclass
class LoopState:
    """Mutable loop state, kept explicit rather than in globals (Phase 0 Step 9)."""

    messages: list[dict] = field(default_factory=list)
    submitted: bool = False


def run_steps(
    *,
    container_id: str,
    lm: LMProtocol,
    recorder: TrajectoryRecorder,
    state: LoopState,
    max_steps: int,
    exec_timeout: float = 300.0,
    workdir: str = "/testbed",
    base_commit: str | None = None,
    exclude_paths: tuple[str, ...] = (),
    track_repo_changes: bool = True,
) -> list[StepRecord]:
    """Run up to `max_steps` agent steps, recording each one.

    Returns the StepRecords produced by this call (not the whole session), so a
    caller can run the loop in segments around a checkpoint.
    """
    produced: list[StepRecord] = []

    for _ in range(max_steps):
        if state.submitted:
            break

        response = lm.next_response(state.messages)
        state.messages.append({"role": "assistant", "content": response.raw_text})

        if response.is_submit or not response.command.strip():
            state.submitted = True
            recorder.record_step(
                action_type=ActionType.SUBMIT,
                command="",
                prompt_tokens=estimate_tokens("".join(m["content"] for m in state.messages)),
                completion_tokens=estimate_tokens(response.raw_text),
                context_length_tokens=estimate_tokens(
                    "".join(m["content"] for m in state.messages)
                ),
                exit_status=0,
            )
            produced.append(recorder.steps[-1])
            break

        result = exec_command(container_id, response.command, timeout=exec_timeout)
        observation = f"exit={result.exit_status}\n{result.stdout[-4000:]}"
        state.messages.append({"role": "user", "content": observation})

        # D1: repository-scoped change measurement, taken BEFORE the evaluator
        # ever applies test_patch, and excluding the instance test files so the
        # evaluator's own edits can never be attributed to the agent.
        repo_changes = None
        if track_repo_changes and base_commit:
            repo_changes = measure_repo_changes(
                container_id, workdir, base_commit, exclude_paths=exclude_paths
            )

        # D3: structural test detection with three-valued status. An unparseable
        # test run is recorded as an invocation, never as "no test ran".
        test_outcome = detect_and_parse(
            response.command, result.stdout, result.stderr, result.exit_status
        )

        context_text = "".join(m["content"] for m in state.messages)
        step = recorder.record_step(
            action_type=ActionType.BASH,
            command=response.command,
            prompt_tokens=estimate_tokens(context_text),
            completion_tokens=estimate_tokens(response.raw_text),
            context_length_tokens=estimate_tokens(context_text),
            stdout=result.stdout,
            stderr=result.stderr,
            exit_status=result.exit_status,
            model_latency_ms=getattr(response, "latency_ms", 0.0),
            test_outcome=test_outcome,
            repo_changes=repo_changes,
        )
        produced.append(step)

    return produced


def message_history_hash(state: LoopState) -> str:
    """Stable hash of the message history, for checkpoint identity."""
    import hashlib
    import json

    payload = json.dumps(state.messages, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()
