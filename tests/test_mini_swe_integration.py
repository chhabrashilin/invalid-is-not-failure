"""mini-swe-agent 2.4.6 integration tests (Phase 0.5 Step 5).

Uses upstream's own `DeterministicModel` and `LocalEnvironment`, so the REAL
agent class, prompt templates, action parsing and control flow are exercised
with **no API key and no spend**. What is *not* covered here is real-provider
nondeterminism, which needs credentials (see docs/phase0_5_report.md).
"""

from __future__ import annotations

import pytest

mini = pytest.importorskip("minisweagent", reason="mini-swe-agent not installed")

from minisweagent.agents.default import DefaultAgent  # noqa: E402
from minisweagent.environments.local import LocalEnvironment  # noqa: E402
from minisweagent.models.test_models import DeterministicModel, make_output  # noqa: E402

from instrumentation.mini_swe_adapter import (  # noqa: E402
    MINI_SWE_AGENT_PINNED_VERSION,
    InstrumentationContext,
    InstrumentedAgent,
    SpendCapExceeded,
    agent_library_version,
)
from instrumentation.recorder import TrajectoryRecorder  # noqa: E402
from trajectory.schema import ExecutionBackend, require_real_backend  # noqa: E402


def test_pinned_version_matches_installed():
    """If upstream changes, the two hook signatures must be re-verified."""
    assert agent_library_version() == MINI_SWE_AGENT_PINNED_VERSION


def test_hook_points_still_exist_upstream():
    """Guard against a silent upstream API change breaking instrumentation."""
    assert hasattr(DefaultAgent, "query")
    assert hasattr(DefaultAgent, "execute_actions")
    assert "Override to add hooks" in (DefaultAgent.query.__doc__ or ""), (
        "upstream removed the documented hook comment; re-audit the adapter"
    )


#: Minimal prompt templates. Upstream requires them; their content is irrelevant
#: to instrumentation, and using placeholders keeps the test independent of any
#: shipped config file.
SYSTEM_TEMPLATE = "You are a test agent."
INSTANCE_TEMPLATE = "Task: {{task}}"


def _agent(outputs, *, cap: float = 1.0, recorder: TrajectoryRecorder | None = None):
    rec = recorder or TrajectoryRecorder("sess-mini", start_monotonic=0.0)
    instr = InstrumentationContext(
        recorder=rec, spend_cap_usd=cap, track_repo_changes=False
    )
    agent = InstrumentedAgent(
        DeterministicModel(outputs=outputs),
        LocalEnvironment(),
        instrumentation=instr,
        step_limit=10,
        system_template=SYSTEM_TEMPLATE,
        instance_template=INSTANCE_TEMPLATE,
    )
    return agent, instr, rec


def test_real_agent_runs_and_is_instrumented():
    """The real DefaultAgent control flow produces our StepRecords."""
    outputs = [
        make_output("looking around", [{"command": "echo hello-from-agent"}], cost=0.0),
        make_output(
            "done",
            [{"command": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"}],
            cost=0.0,
        ),
    ]
    agent, instr, rec = _agent(outputs)
    try:
        agent.run("smoke task")
    except Exception:
        pass  # termination path varies; we assert on what was recorded

    assert len(instr.steps) >= 1, "no steps recorded from the real agent"
    first = instr.steps[0]
    assert "echo hello-from-agent" in first.command_head
    assert first.cumulative_model_calls >= 1
    assert first.exit_status == 0
    assert rec.steps[0] is first


def test_instrumentation_records_nonzero_exit_from_real_env():
    outputs = [make_output("bad", [{"command": "exit 3"}], cost=0.0)]
    agent, instr, _ = _agent(outputs)
    try:
        agent.run("t")
    except Exception:
        pass
    assert instr.steps, "no step recorded"
    assert instr.steps[0].exit_status == 3
    assert instr.steps[0].error_category.value != "none"


def test_spend_cap_blocks_further_calls():
    """PROGRAMMATIC hard cap: must stop without relying on human attention."""
    outputs = [make_output(f"step{i}", [{"command": "echo x"}], cost=0.5) for i in range(10)]
    agent, instr, _ = _agent(outputs, cap=0.9)
    with pytest.raises((SpendCapExceeded, Exception)):
        agent.run("t")
    assert agent.cost <= 1.5, f"cost {agent.cost} ran past the cap"


def test_spend_cap_is_tightened_never_loosened():
    rec = TrajectoryRecorder("s", start_monotonic=0.0)
    instr = InstrumentationContext(recorder=rec, spend_cap_usd=0.25)
    agent = InstrumentedAgent(
        DeterministicModel(outputs=[]), LocalEnvironment(),
        instrumentation=instr, cost_limit=10.0,
        system_template=SYSTEM_TEMPLATE, instance_template=INSTANCE_TEMPLATE,
    )
    assert agent.config.cost_limit == 0.25


def test_mini_swe_session_passes_backend_guard(session_meta):
    real = session_meta.model_copy(
        update={
            "execution_backend": ExecutionBackend.MINI_SWE_AGENT,
            "model_id": "some-real-model",
            "agent_library_version": agent_library_version(),
        }
    )
    require_real_backend(real)
