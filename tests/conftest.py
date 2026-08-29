"""Shared fixtures: a deterministic synthetic trajectory (Phase 0 Step 6).

The fixture encodes the sequence required by the Phase 0 spec:
    inspect -> edit -> test(fail) -> edit -> test(pass)
Correctness, not realism, is the point.
"""

from __future__ import annotations

import pytest

from instrumentation.recorder import TrajectoryRecorder
from trajectory.schema import (
    ActionType,
    SessionMeta,
    SessionOutcome,
    TerminationReason,
    TrajectoryPrefix,
)

FIXTURE_STEPS = [
    # (command, stdout, stderr, exit_status, tests_passed, tests_failed)
    ("ls -la", "total 8\nsrc\n", "", 0, None, None),
    ("python -c \"open('f.py','w').write('x=1')\"", "", "", 0, None, None),
    ("pytest -q", "1 failed, 2 passed", "", 1, 2, 1),
    ("python -c \"open('f.py','w').write('x=2')\"", "", "", 0, None, None),
    ("pytest -q", "3 passed", "", 0, 3, 0),
]


@pytest.fixture
def session_meta() -> SessionMeta:
    return SessionMeta(
        session_id="sess-fixture",
        task_id="fixture__task-1",
        repo="fixture/repo",
        scaffold="phase0-minimal-loop",
        scaffold_version="phase0-0.1.0",
        model_id="mock:scripted-v1",
        run_id="test-run",
        git_commit="0" * 40,
        git_dirty=False,
        benchmark_version="fixture-v0",
        harness_version="phase0-0.1.0",
        step_budget_cap=10,
        start_ts="2026-08-29T00:00:00+00:00",
    )


@pytest.fixture
def fixture_recorder() -> TrajectoryRecorder:
    rec = TrajectoryRecorder("sess-fixture", start_monotonic=0.0)
    for i, (cmd, out, err, code, tp, tf) in enumerate(FIXTURE_STEPS):
        rec.record_step(
            action_type=ActionType.BASH,
            command=cmd,
            prompt_tokens=10 + i,
            completion_tokens=5,
            context_length_tokens=100 + 10 * i,
            stdout=out,
            stderr=err,
            exit_status=code,
            tests_passed=tp,
            tests_failed=tf,
            files_changed_count=1 if "open(" in cmd else 0,
            elapsed_s=float(i),
        )
    return rec


@pytest.fixture
def fixture_prefix(session_meta, fixture_recorder) -> TrajectoryPrefix:
    return TrajectoryPrefix(session_meta, fixture_recorder.steps, k=3)


@pytest.fixture
def fixture_outcome() -> SessionOutcome:
    return SessionOutcome(
        session_id="sess-fixture",
        end_ts="2026-08-29T00:05:00+00:00",
        wall_time_s=300.0,
        termination_reason=TerminationReason.SUBMITTED,
        final_step_count=5,
        total_prompt_tokens=60,
        total_completion_tokens=25,
        total_model_calls=5,
        total_tool_calls=5,
        total_failed_tool_calls=1,
        estimated_cost_usd=0.0,
    )
