"""Regression tests for Phase 0.5 provider/trajectory separation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from instrumentation.provider_retry import (
    CallBudget,
    CompositeCallBudget,
    GlobalAttemptLedger,
    NonRetryableProviderError,
    ProviderRequestExecutor,
    ProviderTimeout,
    ProviderUnavailable,
)
from instrumentation.recorder import TrajectoryRecorder
from trajectory.features import extract_model_b_features
from trajectory.schema import (
    ActionType,
    ProviderFinalStatus,
    ScientificRunDisposition,
    SessionMeta,
    TerminationReason,
    TrajectoryPrefix,
)


class ProviderError(RuntimeError):
    def __init__(self, status_code: int):
        super().__init__(f"provider HTTP {status_code}")
        self.status_code = status_code


def _session() -> SessionMeta:
    return SessionMeta(
        session_id="s",
        task_id="t",
        scaffold="mini-swe-agent",
        scaffold_version="2.4.6",
        model_id="gemini/gemini-3.7-flash",
        run_id="r",
        git_commit="0" * 40,
        git_dirty=False,
        benchmark_version="SWE-bench_Verified",
        harness_version="phase0.5",
        step_budget_cap=10,
        start_ts="2026-08-29T00:00:00+00:00",
    )


def test_503_retry_occurs_below_trajectory_semantics_and_recovers():
    calls = 0
    sleeps = []

    def request():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ProviderError(503)
        return "OK"

    records = []
    executor = ProviderRequestExecutor(
        call_budget=CallBudget(100), records=records, sleep_fn=sleeps.append
    )
    response, record = executor.call(request)
    assert response == "OK"
    assert executor.logical_calls == 1
    assert calls == record.provider_attempt_count == 3
    assert record.provider_503_count == 2
    assert record.provider_retry_delay_total == 45.0
    assert sleeps == [15.0, 30.0]


def test_recovered_503_does_not_increment_behavioral_failure_features():
    rec = TrajectoryRecorder("s", start_monotonic=0.0)
    rec.record_step(
        action_type=ActionType.BASH,
        command="echo ok",
        prompt_tokens=1,
        completion_tokens=1,
        context_length_tokens=2,
        stdout="ok",
        exit_status=0,
        elapsed_s=1.0,
    )
    features = extract_model_b_features(TrajectoryPrefix(_session(), rec.steps, 1))
    assert features["b_failed_tool_calls"] == 0.0
    assert features["b_failure_rate"] == 0.0
    # Provider events are structurally absent from semantic StepRecord fields.
    assert "provider_503_count" not in type(rec.steps[0]).model_fields


def test_exhausted_503_retries_produce_provider_unavailable():
    executor = ProviderRequestExecutor(
        call_budget=CallBudget(100), sleep_fn=lambda _: None
    )
    with pytest.raises(ProviderUnavailable) as caught:
        executor.call(lambda: (_ for _ in ()).throw(ProviderError(503)))
    record = caught.value.record
    assert record.provider_final_status == ProviderFinalStatus.PROVIDER_UNAVAILABLE
    assert record.provider_attempt_count == 4
    assert record.provider_503_count == 4
    assert record.provider_retry_delay_total == 105.0


def test_provider_unavailable_receives_no_y_success_label():
    disposition = ScientificRunDisposition(
        session_id="s",
        termination_reason=TerminationReason.PROVIDER_UNAVAILABLE,
        valid_for_success_modelling=False,
        y_success=None,
    )
    assert disposition.y_success is None
    with pytest.raises(ValidationError):
        ScientificRunDisposition(
            session_id="s",
            termination_reason=TerminationReason.PROVIDER_UNAVAILABLE,
            valid_for_success_modelling=True,
            y_success=False,
        )


def test_provider_timeout_retries_below_semantics_and_recovers():
    calls = 0
    sleeps = []

    def request():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("physical request timed out")
        return "OK"

    executor = ProviderRequestExecutor(
        call_budget=CallBudget(100),
        retry_delays=(5.0, 15.0, 30.0),
        retry_timeouts=True,
        sleep_fn=sleeps.append,
    )
    response, record = executor.call(request)
    assert response == "OK"
    assert record.provider_attempt_count == 2
    assert record.provider_timeout_count == 1
    assert record.provider_503_count == 0
    assert record.provider_retry_delay_total == 5.0
    assert sleeps == [5.0]


def test_exhausted_timeouts_produce_unlabelled_provider_timeout():
    executor = ProviderRequestExecutor(
        call_budget=CallBudget(100),
        retry_delays=(5.0, 15.0, 30.0),
        retry_timeouts=True,
        sleep_fn=lambda _: None,
    )
    with pytest.raises(ProviderTimeout) as caught:
        executor.call(lambda: (_ for _ in ()).throw(TimeoutError("timed out")))
    record = caught.value.record
    assert record.provider_final_status == ProviderFinalStatus.PROVIDER_TIMEOUT
    assert record.provider_attempt_count == 4
    assert record.provider_timeout_count == 4
    assert record.provider_retry_delay_total == 50.0

    disposition = ScientificRunDisposition(
        session_id="timeout-run",
        termination_reason=TerminationReason.PROVIDER_TIMEOUT,
        valid_for_success_modelling=False,
        y_success=None,
    )
    assert disposition.y_success is None
    with pytest.raises(ValidationError):
        ScientificRunDisposition(
            session_id="timeout-run",
            termination_reason=TerminationReason.PROVIDER_TIMEOUT,
            valid_for_success_modelling=True,
            y_success=False,
        )


def test_429_is_surfaced_without_retry():
    budget = CallBudget(100)
    executor = ProviderRequestExecutor(call_budget=budget, sleep_fn=lambda _: None)
    with pytest.raises(NonRetryableProviderError) as caught:
        executor.call(lambda: (_ for _ in ()).throw(ProviderError(429)))
    assert budget.used == 1
    assert caught.value.record.provider_final_status == ProviderFinalStatus.RATE_LIMITED


def test_provider_attempt_count_is_separate_from_logical_calls():
    attempts = iter([ProviderError(503), ProviderError(503), "OK"])

    def request():
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    executor = ProviderRequestExecutor(
        call_budget=CallBudget(100), sleep_fn=lambda _: None
    )
    executor.call(request)
    assert executor.logical_calls == 1
    assert executor.records[0].provider_attempt_count == 3


def test_global_ceiling_counts_physical_attempts_not_logical_calls():
    budget = CallBudget(max_calls=3)
    executor = ProviderRequestExecutor(call_budget=budget, sleep_fn=lambda _: None)
    with pytest.raises(Exception):
        executor.call(lambda: (_ for _ in ()).throw(ProviderError(503)))
    assert executor.logical_calls == 1
    assert budget.used == 3
    assert executor.records[-1].provider_final_status == ProviderFinalStatus.CALL_CAP_EXCEEDED


def test_composite_budget_updates_global_and_model_ledgers(tmp_path):
    model_path = tmp_path / "model.json"
    global_path = tmp_path / "global.json"
    model_budget = CallBudget.from_ledger(
        model_path,
        max_calls=100,
        initial_used=0,
        metadata={"model_id": "gemini/gemini-2.5-flash"},
    )
    global_ledger = GlobalAttemptLedger.from_ledger(global_path, initial_used=12)
    composite = CompositeCallBudget(
        model_budget=model_budget,
        global_ledger=global_ledger,
        model_id="gemini/gemini-2.5-flash",
    )
    executor = ProviderRequestExecutor(call_budget=composite)
    executor.call(lambda: "OK")
    assert model_budget.used == 1 and model_budget.remaining == 99
    assert global_ledger.used == 13
    assert global_ledger.events[-1]["model_id"] == "gemini/gemini-2.5-flash"


def test_phase05_model_disables_hidden_litellm_retries(monkeypatch):
    from minisweagent.models.litellm_model import LitellmModel

    from instrumentation.mini_swe_adapter import Phase05GeminiModel

    seen_kwargs = []

    def one_physical_request(self, messages, **kwargs):
        seen_kwargs.append(kwargs)
        return "response"

    monkeypatch.setattr(LitellmModel, "_query", one_physical_request)
    model = Phase05GeminiModel(
        model_name="gemini/gemini-3.7-flash",
        call_budget=CallBudget(100),
        provider_sleep_fn=lambda _: None,
    )
    assert model._query([]) == "response"
    assert seen_kwargs == [{"num_retries": 0, "timeout": 90.0}]
    assert model.provider_executor.records[0].provider_attempt_count == 1
