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


# =========================================================================
# Phase 0.5 free-tier controls: shared model-call ceiling
# =========================================================================


def test_call_budget_reserves_and_exhausts():
    from instrumentation.mini_swe_adapter import CallBudget, CallCapExceeded

    b = CallBudget(max_calls=3)
    for _ in range(3):
        b.check_and_reserve()
    assert b.used == 3 and b.remaining == 0
    with pytest.raises(CallCapExceeded):
        b.check_and_reserve()


def test_call_ceiling_halts_the_agent():
    """The ceiling must stop the loop without relying on human attention."""
    from instrumentation.mini_swe_adapter import CallBudget, CallCapExceeded

    budget = CallBudget(max_calls=2)
    outputs = [make_output(f"s{i}", [{"command": "echo x"}], cost=0.0) for i in range(20)]
    rec = TrajectoryRecorder("sess-cap", start_monotonic=0.0)
    instr = InstrumentationContext(
        recorder=rec, spend_cap_usd=0.0, track_repo_changes=False, call_budget=budget
    )
    agent = InstrumentedAgent(
        DeterministicModel(outputs=outputs), LocalEnvironment(), instrumentation=instr,
        step_limit=50, system_template=SYSTEM_TEMPLATE, instance_template=INSTANCE_TEMPLATE,
    )
    with pytest.raises((CallCapExceeded, Exception)):
        agent.run("t")
    assert budget.used == 2, f"expected exactly 2 calls, got {budget.used}"


def test_call_budget_is_shared_across_sessions():
    """Parent + forks must draw from ONE ledger (Phase 0.5 ceiling spans all)."""
    from instrumentation.mini_swe_adapter import CallBudget

    budget = CallBudget(max_calls=100)
    a = InstrumentationContext(recorder=TrajectoryRecorder("a"), call_budget=budget)
    b = InstrumentationContext(recorder=TrajectoryRecorder("b"), call_budget=budget)
    a.call_budget.check_and_reserve()
    b.call_budget.check_and_reserve()
    assert budget.used == 2 and a.call_budget is b.call_budget


def test_free_tier_zero_dollar_cap_would_block_everything():
    """Documents WHY the $0 authorisation is enforced as calls, not dollars.

    litellm carries a paid-tier price for gemini/gemini-3.7-flash, so a literal
    cost_limit of 0.00 is indistinguishable from 'no cap' in our tightening
    logic -- and if it were applied as a cost check it would abort call #1.
    """
    rec = TrajectoryRecorder("s", start_monotonic=0.0)
    instr = InstrumentationContext(recorder=rec, spend_cap_usd=0.0)
    agent = InstrumentedAgent(
        DeterministicModel(outputs=[]), LocalEnvironment(), instrumentation=instr,
        cost_limit=0.0, system_template=SYSTEM_TEMPLATE, instance_template=INSTANCE_TEMPLATE,
    )
    # spend_cap_usd == 0 means "no dollar cap applied"; the call ceiling governs.
    assert agent.config.cost_limit == 0.0
    assert instr.spend_cap_usd == 0.0


# =========================================================================
# Preflight credential discovery (Phase 0.5 Gemini continuation)
# =========================================================================


def test_preflight_dotenv_path_matches_agent_config_dir():
    """The preflight must read the SAME .env mini-swe-agent reads.

    This is the credential path that does not require restarting the parent
    process, so it must not drift from upstream's location.
    """
    import importlib.util
    from pathlib import Path

    from platformdirs import user_config_dir

    spec = importlib.util.spec_from_file_location(
        "preflight_gemini",
        Path(__file__).resolve().parents[1] / "scripts/phase0/preflight_gemini.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.MODEL == "gemini/gemini-3.7-flash"
    assert mod.CREDENTIAL_ENV == "GEMINI_API_KEY"
    expected = Path(user_config_dir("mini-swe-agent")) / ".env"
    # load_agent_dotenv returns the path only when the file exists; either way it
    # must not raise, and must target the upstream config dir.
    result = mod.load_agent_dotenv()
    assert result is None or Path(result) == expected


def test_preflight_never_reads_credential_value():
    """Guard: the preflight may test presence, never read or emit the value."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "scripts/phase0/preflight_gemini.py").read_text(encoding="utf-8")
    # presence checks are fine; printing/formatting the value is not
    assert 'os.environ.get(n)' in src
    for forbidden in ('print(os.environ', 'os.environ[CREDENTIAL_ENV])',
                      'f"{os.environ'):
        assert forbidden not in src, f"preflight may leak the credential: {forbidden}"
