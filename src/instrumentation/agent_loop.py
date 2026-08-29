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

from checkpoint.docker_env import container_diff_summary, exec_command
from evaluation.evaluator import parse_pytest_output
from instrumentation.recorder import TrajectoryRecorder, estimate_tokens
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
    prev_diff_count: int = 0
    submitted: bool = False


def _looks_like_test_command(command: str) -> bool:
    lowered = command.lower()
    return "pytest" in lowered or "python -m unittest" in lowered or " test" in lowered


def run_steps(
    *,
    container_id: str,
    lm: LMProtocol,
    recorder: TrajectoryRecorder,
    state: LoopState,
    max_steps: int,
    exec_timeout: float = 300.0,
    track_fs_diff: bool = True,
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

        files_changed = 0
        if track_fs_diff:
            current = container_diff_summary(container_id)
            files_changed = max(0, current - state.prev_diff_count)
            state.prev_diff_count = current

        parsed = (
            parse_pytest_output(result.stdout + "\n" + result.stderr)
            if _looks_like_test_command(response.command)
            else None
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
            model_latency_ms=0.0,  # mocked LM: no real inference latency to report
            files_changed_count=files_changed,
            tests_passed=parsed.passed if parsed else None,
            tests_failed=(
                ((parsed.failed or 0) + (parsed.errors or 0))
                if parsed and parsed.any_parsed
                else None
            ),
        )
        produced.append(step)

    return produced


def message_history_hash(state: LoopState) -> str:
    """Stable hash of the message history, for checkpoint identity."""
    import hashlib
    import json

    payload = json.dumps(state.messages, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()
