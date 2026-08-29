"""Step recorder: builds StepRecords with cumulative resource accounting.

Stage 3 §11 (RESOURCE UNITS): counters are kept in tokens, tool calls and
wall-clock. No conversion to GPU-hours is performed -- there is no GPU on this
machine and a fabricated hardware equivalence would be a fictitious measurement.

Security (Phase 0 Step 7): commands and outputs are stored as hashes plus a
bounded-length head. Environment variables, credentials and full filesystem
dumps are never recorded.
"""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timezone

from evaluation.test_detect import TestOutcome, TestStatus
from instrumentation.repo_state import RepoChanges
from trajectory.schema import (
    ActionType,
    ErrorCategory,
    StepRecord,
    categorize_error,
    normalize_command,
    sha256_text,
)

#: Maximum characters of a command retained in cleartext for debugging.
COMMAND_HEAD_CHARS = 120


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_tokens(text: str) -> int:
    """Crude token estimate for mocked runs (~4 chars/token).

    Phase 0 only. Where a provider reports real usage, that MUST be used
    instead; this exists so the accounting path can be exercised without a
    paid API. Records produced this way are flagged via the session's model_id.
    """
    return max(1, len(text) // 4)


class TrajectoryRecorder:
    """Accumulates step records for one session.

    The recorder is the single place cumulative counters are maintained, so the
    invariant "counters are monotone non-decreasing" is testable in one spot.
    """

    def __init__(self, session_id: str, start_monotonic: float | None = None) -> None:
        self.session_id = session_id
        self._t0 = start_monotonic if start_monotonic is not None else time.monotonic()
        self._step_id = 0
        self._cum_prompt = 0
        self._cum_completion = 0
        self._cum_model_calls = 0
        self._cum_tool_calls = 0
        self._cum_failed_tool_calls = 0
        self._cum_cost = 0.0
        self._cmd_counts: Counter[str] = Counter()
        self._err_counts: Counter[str] = Counter()
        self.steps: list[StepRecord] = []

    @property
    def n_steps(self) -> int:
        return self._step_id

    @property
    def cumulative_model_calls(self) -> int:
        return self._cum_model_calls

    @property
    def cumulative_completion_tokens(self) -> int:
        return self._cum_completion

    def record_step(
        self,
        *,
        action_type: ActionType,
        command: str,
        prompt_tokens: int,
        completion_tokens: int,
        context_length_tokens: int,
        stdout: str = "",
        stderr: str = "",
        exit_status: int | None = None,
        model_latency_ms: float = 0.0,
        estimated_cost_usd: float = 0.0,
        test_outcome: TestOutcome | None = None,
        repo_changes: RepoChanges | None = None,
        elapsed_s: float | None = None,
    ) -> StepRecord:
        """Record one completed step and return the immutable record."""
        norm = normalize_command(command)
        norm_hash = sha256_text(norm)

        # repeats are counted over the PRIOR prefix, so the value is the number of
        # earlier occurrences (0 on first use). Online-safe by construction.
        repeated_command_k = self._cmd_counts[norm_hash]
        self._cmd_counts[norm_hash] += 1

        stderr_head = stderr[:2000]
        error_category = categorize_error(exit_status, stderr_head)
        repeated_error_k = self._err_counts[error_category.value]
        if error_category != ErrorCategory.NONE:
            self._err_counts[error_category.value] += 1
            self._cum_failed_tool_calls += 1
        else:
            repeated_error_k = 0

        self._cum_prompt += prompt_tokens
        self._cum_completion += completion_tokens
        self._cum_model_calls += 1
        self._cum_cost += estimated_cost_usd
        if action_type == ActionType.BASH:
            self._cum_tool_calls += 1

        # D3: three-valued test detection. An unparseable test run is recorded
        # as an invocation, NOT as "no test ran".
        to = test_outcome
        rc = repo_changes

        step = StepRecord(
            step_id=self._step_id,
            session_id=self.session_id,
            ts=_utcnow(),
            elapsed_s=(
                elapsed_s if elapsed_s is not None else max(0.0, time.monotonic() - self._t0)
            ),
            model_call_index=self._cum_model_calls - 1,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            context_length_tokens=context_length_tokens,
            cumulative_prompt_tokens=self._cum_prompt,
            cumulative_completion_tokens=self._cum_completion,
            cumulative_model_calls=self._cum_model_calls,
            cumulative_tool_calls=self._cum_tool_calls,
            cumulative_failed_tool_calls=self._cum_failed_tool_calls,
            estimated_cost_usd=self._cum_cost,
            action_type=action_type,
            command_text_hash=sha256_text(command),
            command_normalized_hash=norm_hash,
            command_head=command[:COMMAND_HEAD_CHARS],
            tool_output_bytes=len(stdout.encode("utf-8", errors="replace")),
            tool_output_hash=sha256_text(stdout),
            stderr_head_hash=sha256_text(stderr_head),
            exit_status=exit_status,
            error_category=error_category,
            repeated_command_k=repeated_command_k,
            repeated_error_k=repeated_error_k,
            test_status=(to.status.value if to else TestStatus.NOT_RUN.value),
            test_framework=(to.framework.value if to else "none"),
            test_exit_status=(to.exit_status if to else None),
            test_invocation=bool(to and to.invoked),
            tests_passed=(to.passed if to else None),
            tests_failed=(to.failed if to else None),
            tests_errored=(to.errored if to else None),
            repo_files_modified=(rc.files_modified if rc else 0),
            repo_files_added=(rc.files_added if rc else 0),
            repo_files_deleted=(rc.files_deleted if rc else 0),
            repo_lines_added=(rc.lines_added if rc else 0),
            repo_lines_deleted=(rc.lines_deleted if rc else 0),
            repo_changes_measured=bool(rc and rc.measured),
            model_latency_ms=model_latency_ms,
        )
        self.steps.append(step)
        self._step_id += 1
        return step
