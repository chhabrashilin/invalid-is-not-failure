"""Typed trajectory schema for agent measurement (Stage 3 design, docs/stage3_measurement_design.md §4).

SCIENTIFIC INVARIANT (Stage 3 §2.1, inherited from Stage 1 invariant I1)
------------------------------------------------------------------------
Class-C ("oracle" / post-hoc) information must be *structurally* unreachable from
anything an online predictor sees -- not merely "not used by convention".

This module enforces that by splitting the record types:

  ONLINE-SAFE (Class A)          POST-HOC ONLY (Class C)
  ---------------------          -----------------------
  SessionMeta                    SessionOutcome
  StepRecord                     EvaluationRecord
  TrajectoryPrefix               (decisive-error annotations, final lengths)

`TrajectoryPrefix` holds a *copy* of the first k steps and has no reference to
the remaining steps or to any outcome object, so future information is not
merely ignored -- it is absent from memory.
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, NonNegativeInt

# --------------------------------------------------------------------------
# Oracle field registry -- used by tests to assert no leakage into online types
# --------------------------------------------------------------------------

#: Names that may NEVER appear on an online-safe model. Tested in
#: tests/test_oracle_leakage.py. Add to this set, never remove from it.
ORACLE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "y_success",
        "success",
        "resolved",
        "evaluator_score",
        "final_step_count",
        "final_token_count",
        "total_steps",
        "decisive_error_step",
        "failure_lock_in_step",
        "gold_patch",
        "future_steps",
        "outcome",
    }
)


TestStatusLiteral = Literal[
    "TEST_NOT_RUN", "TEST_RAN_RESULT_PARSED", "TEST_RAN_RESULT_UNPARSEABLE"
]


class _OnlineSafe(BaseModel):
    """Base for any model an online predictor may observe.

    `extra="forbid"` prevents an oracle field being smuggled in via a dict.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class _PostHoc(BaseModel):
    """Base for analysis-only models. Never passed to feature extraction."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------


class ActionType(str, Enum):
    BASH = "bash"
    SUBMIT = "submit"
    NOOP = "noop"
    PARSE_ERROR = "parse_error"


class ErrorCategory(str, Enum):
    """Deterministic categorisation of a tool result. Online-safe."""

    NONE = "none"
    COMMAND_NOT_FOUND = "command_not_found"
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION = "permission"
    SYNTAX = "syntax"
    TEST_FAILURE = "test_failure"
    TIMEOUT = "timeout"
    NONZERO_EXIT = "nonzero_exit"


class ExecutionBackend(str, Enum):
    """Which agent implementation produced the trajectory (Phase 0.5 D4).

    Phase 1 scientific collection MUST reject MOCK. Enforced by
    `require_real_backend`.
    """

    MOCK = "mock"
    MINI_SWE_AGENT = "mini_swe_agent"


class TerminationReason(str, Enum):
    SUBMITTED = "submitted"
    STEP_LIMIT = "step_limit"
    COST_LIMIT = "cost_limit"
    TIMEOUT = "timeout"
    CRASH = "crash"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def normalize_command(command: str) -> str:
    """Normalise a shell command for repeat detection.

    Collapses whitespace and strips, so ``ls  -la`` and ``ls -la`` are the same
    command. Deliberately conservative: no argument reordering, no aliasing.
    """
    return _WS.sub(" ", command.strip())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def categorize_error(exit_status: int | None, stderr_head: str) -> ErrorCategory:
    """Map a tool result to an error category. Pure function of the tool result.

    Uses only information available at the moment the command returns, so it is
    online-safe. Order matters: the first matching rule wins.
    """
    if exit_status is None:
        return ErrorCategory.TIMEOUT
    low = stderr_head.lower()
    if "command not found" in low or exit_status == 127:
        return ErrorCategory.COMMAND_NOT_FOUND
    if "no such file or directory" in low:
        return ErrorCategory.FILE_NOT_FOUND
    if "permission denied" in low or exit_status == 126:
        return ErrorCategory.PERMISSION
    if "syntaxerror" in low or "indentationerror" in low:
        return ErrorCategory.SYNTAX
    if "failed" in low and ("test" in low or "assert" in low):
        return ErrorCategory.TEST_FAILURE
    if exit_status == 124:
        return ErrorCategory.TIMEOUT
    if exit_status != 0:
        return ErrorCategory.NONZERO_EXIT
    return ErrorCategory.NONE


# --------------------------------------------------------------------------
# ONLINE-SAFE records
# --------------------------------------------------------------------------


class SessionMeta(_OnlineSafe):
    """Identity and configuration of a session. Contains NO outcome information.

    Everything here is known at session *start*, which is what makes it safe.
    """

    session_id: str
    task_id: str
    repo: str | None = None
    scaffold: str
    scaffold_version: str
    execution_backend: ExecutionBackend = ExecutionBackend.MOCK
    agent_library_version: str | None = None
    model_id: str
    decoding_params: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None
    run_id: str
    git_commit: str
    git_dirty: bool
    benchmark_version: str
    harness_version: str
    container_image: str | None = None
    container_image_digest: str | None = None
    step_budget_cap: NonNegativeInt = Field(
        description="Pre-declared budget cap. Checkpoints are indexed against THIS, "
        "never against the realized trajectory length (which is Class C)."
    )
    token_budget_cap: NonNegativeInt = 0
    start_ts: str
    parent_session_id: str | None = None
    forked_at_step: NonNegativeInt | None = None


class StepRecord(_OnlineSafe):
    """One agent step. Online-safe: every field is knowable when the step ends."""

    step_id: NonNegativeInt
    session_id: str
    ts: str
    elapsed_s: NonNegativeFloat
    model_call_index: NonNegativeInt

    # resource accounting (Stage 3 §11: RESOURCE UNITS = tokens; no GPU-hour fiction)
    prompt_tokens: NonNegativeInt
    completion_tokens: NonNegativeInt
    context_length_tokens: NonNegativeInt
    cumulative_prompt_tokens: NonNegativeInt
    cumulative_completion_tokens: NonNegativeInt
    cumulative_model_calls: NonNegativeInt
    cumulative_tool_calls: NonNegativeInt
    cumulative_failed_tool_calls: NonNegativeInt
    estimated_cost_usd: NonNegativeFloat = 0.0

    # action
    action_type: ActionType
    command_text_hash: str
    command_normalized_hash: str
    command_head: str = Field(default="", description="Bounded-length head, no secrets")

    # tool result
    tool_output_bytes: NonNegativeInt = 0
    tool_output_hash: str = ""
    stderr_head_hash: str = ""
    exit_status: int | None = None
    error_category: ErrorCategory = ErrorCategory.NONE

    # derived behavioural features (Stage 3 §4.2)
    repeated_command_k: NonNegativeInt = 0
    repeated_error_k: NonNegativeInt = 0
    # --- test detection (D3): three-valued, never collapse UNPARSEABLE to NOT_RUN
    test_status: TestStatusLiteral = "TEST_NOT_RUN"
    test_framework: str = "none"
    test_exit_status: int | None = None
    test_invocation: bool = False
    tests_passed: int | None = None
    tests_failed: int | None = None
    tests_errored: int | None = None

    # --- repository-scoped change accounting (D1), measured via git inside the
    # repo BEFORE the evaluator applies test_patch. `repo_changes_measured`
    # records whether the measurement actually succeeded, so a failed
    # measurement is never silently read as "zero changes".
    repo_files_modified: NonNegativeInt = 0
    repo_files_added: NonNegativeInt = 0
    repo_files_deleted: NonNegativeInt = 0
    repo_lines_added: NonNegativeInt = 0
    repo_lines_deleted: NonNegativeInt = 0
    repo_changes_measured: bool = False

    model_latency_ms: NonNegativeFloat = 0.0


class EnvironmentSnapshotMetadata(_OnlineSafe):
    """Record of a checkpoint taken mid-trajectory (Stage 3 §7.2)."""

    snapshot_id: str
    parent_session_id: str
    checkpoint_step: NonNegativeInt
    created_ts: str
    container_id: str
    image_ref: str
    image_id: str
    filesystem_digest: str
    message_history_hash: str
    cumulative_model_calls: NonNegativeInt
    cumulative_completion_tokens: NonNegativeInt


class ContinuationRecord(_OnlineSafe):
    """A forked continuation launched from a snapshot (Stage 3 §7.2)."""

    continuation_id: str
    snapshot_id: str
    parent_session_id: str
    checkpoint_step: NonNegativeInt
    budget_additional_steps: NonNegativeInt
    replicate_index: NonNegativeInt
    arm: str = Field(description="'control' (same condition) or a treatment label")
    started_ts: str


# --------------------------------------------------------------------------
# POST-HOC records -- never shown to online feature extraction
# --------------------------------------------------------------------------


class EvaluationRecord(_PostHoc):
    """Produced by the external evaluator, independently of the trajectory logger.

    Stage 3 §12: the logger must not determine success itself, to avoid circular
    labelling.
    """

    session_id: str
    instance_id: str
    evaluator_name: str
    evaluator_version: str
    benchmark_version: str
    evaluated_ts: str
    success: bool
    score: float
    tests_passed: int | None = None
    tests_failed: int | None = None
    raw_artifact_path: str
    raw_artifact_sha256: str


class SessionOutcome(_PostHoc):
    """Class-C aggregates. Analysis only."""

    session_id: str
    end_ts: str
    wall_time_s: NonNegativeFloat
    termination_reason: TerminationReason
    final_step_count: NonNegativeInt
    total_prompt_tokens: NonNegativeInt
    total_completion_tokens: NonNegativeInt
    total_model_calls: NonNegativeInt
    total_tool_calls: NonNegativeInt
    total_failed_tool_calls: NonNegativeInt
    estimated_cost_usd: NonNegativeFloat


# --------------------------------------------------------------------------
# The ONLY view feature extraction may receive
# --------------------------------------------------------------------------


class PrefixBoundaryError(IndexError):
    """Raised when code attempts to look past the checkpoint. This is a bug."""


class TrajectoryPrefix:
    """An immutable view of the first `k` steps of a session.

    Holds a *copy* of the prefix steps only. The remaining steps and every
    post-hoc record are absent, so future information cannot be read even by
    accident.
    """

    __slots__ = ("_session", "_steps", "_k")

    def __init__(self, session: SessionMeta, steps: list[StepRecord], k: int) -> None:
        if k < 0:
            raise ValueError("k must be non-negative")
        if k > len(steps):
            raise PrefixBoundaryError(
                f"cannot build a prefix of {k} steps from {len(steps)} available"
            )
        self._session = session
        self._steps: tuple[StepRecord, ...] = tuple(steps[:k])  # defensive copy
        self._k = k

    @property
    def session(self) -> SessionMeta:
        return self._session

    @property
    def k(self) -> int:
        return self._k

    @property
    def steps(self) -> tuple[StepRecord, ...]:
        return self._steps

    def step(self, i: int) -> StepRecord:
        if i < 0 or i >= self._k:
            raise PrefixBoundaryError(
                f"step {i} is outside the prefix boundary (k={self._k}); "
                "reading past the checkpoint is Class-C leakage"
            )
        return self._steps[i]

    def __len__(self) -> int:
        return self._k

    def __iter__(self):
        return iter(self._steps)

    def __repr__(self) -> str:
        return f"TrajectoryPrefix(session={self._session.session_id!r}, k={self._k})"


class MockBackendRejected(RuntimeError):
    """Raised when a mock trajectory is offered to scientific collection."""


def require_real_backend(session: SessionMeta) -> None:
    """Reject mock trajectories (Phase 0.5 D4).

    Phase 1 must never mix deterministic mock runs into a scientific dataset.
    Call this at load time in any Phase 1 pipeline.
    """
    if session.execution_backend != ExecutionBackend.MINI_SWE_AGENT:
        raise MockBackendRejected(
            f"session {session.session_id} used backend "
            f"'{session.execution_backend.value}'; Phase 1 requires "
            f"'{ExecutionBackend.MINI_SWE_AGENT.value}'"
        )
    if session.model_id.startswith("mock:"):
        raise MockBackendRejected(
            f"session {session.session_id} has mock model_id {session.model_id!r}"
        )
