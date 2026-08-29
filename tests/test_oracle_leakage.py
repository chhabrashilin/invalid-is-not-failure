"""MANDATORY leakage tests (Phase 0 Step 13, Stage 3 §2.1).

These are the tests that protect the scientific validity of everything later.
If any of them fail, no measurement from this harness can be trusted.
"""

from __future__ import annotations

import pytest

from trajectory.features import extract_online_features
from trajectory.schema import (
    ORACLE_FIELD_NAMES,
    ActionType,
    EvaluationRecord,
    PrefixBoundaryError,
    SessionMeta,
    SessionOutcome,
    StepRecord,
    TrajectoryPrefix,
)

ONLINE_SAFE_MODELS = [SessionMeta, StepRecord]


def test_online_models_contain_no_oracle_fields():
    """No online-safe model may declare a field from the oracle registry."""
    for model in ONLINE_SAFE_MODELS:
        overlap = set(model.model_fields) & ORACLE_FIELD_NAMES
        assert not overlap, f"{model.__name__} exposes oracle fields: {overlap}"


def test_online_models_reject_extra_fields(session_meta):
    """Oracle data cannot be smuggled in via an extra key."""
    payload = session_meta.model_dump()
    payload["y_success"] = 1
    with pytest.raises(Exception):
        SessionMeta.model_validate(payload)


def test_prefix_cannot_address_future_steps(session_meta, fixture_recorder):
    prefix = TrajectoryPrefix(session_meta, fixture_recorder.steps, k=3)
    assert len(prefix) == 3
    for bad in (3, 4, 99, -1):
        with pytest.raises(PrefixBoundaryError):
            prefix.step(bad)


def test_prefix_does_not_retain_future_steps_in_memory(session_meta, fixture_recorder):
    """Future steps must be absent, not merely unread."""
    prefix = TrajectoryPrefix(session_meta, fixture_recorder.steps, k=2)
    assert len(prefix.steps) == 2
    assert len(list(iter(prefix))) == 2
    retained = {s.step_id for s in prefix.steps}
    assert retained == {0, 1}


def test_prefix_exposes_no_outcome_attribute(fixture_prefix):
    for name in ORACLE_FIELD_NAMES:
        assert not hasattr(fixture_prefix, name), f"prefix exposes {name}"
    assert not hasattr(fixture_prefix, "evaluation")


def test_adversarial_future_steps_cannot_influence_features(session_meta, fixture_recorder):
    """THE adversarial test required by Phase 0 Step 13.

    Append future steps stuffed with obviously predictive junk, then confirm the
    extracted prefix features are bit-identical.
    """
    baseline = extract_online_features(
        TrajectoryPrefix(session_meta, fixture_recorder.steps, k=3)
    )

    poisoned = list(fixture_recorder.steps)
    for j in range(5):
        poisoned.append(
            StepRecord(
                step_id=len(poisoned),
                session_id="sess-fixture",
                ts="2099-01-01T00:00:00+00:00",
                elapsed_s=99999.0,
                model_call_index=len(poisoned),
                prompt_tokens=10**6,
                completion_tokens=10**6,
                context_length_tokens=10**6,
                cumulative_prompt_tokens=10**7,
                cumulative_completion_tokens=10**7,
                cumulative_model_calls=10**5,
                cumulative_tool_calls=10**5,
                cumulative_failed_tool_calls=10**5,
                action_type=ActionType.BASH,
                command_text_hash="f" * 64,
                command_normalized_hash="f" * 64,
                command_head="THE_ANSWER_IS_SUCCESS",
                files_changed_count=10**4,
                diff_line_count=10**4,
                test_invocation=True,
                tests_passed=10**4,
                tests_failed=0,
            )
        )

    poisoned_features = extract_online_features(
        TrajectoryPrefix(session_meta, poisoned, k=3)
    )
    assert poisoned_features == baseline, "future steps leaked into prefix features"


def test_features_ignore_outcome_object(fixture_prefix, fixture_outcome):
    """extract_online_features accepts only a prefix; an outcome cannot be passed."""
    feats = extract_online_features(fixture_prefix)
    assert isinstance(feats, dict) and feats
    with pytest.raises(TypeError):
        extract_online_features(fixture_outcome)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        extract_online_features(list(fixture_prefix.steps))  # type: ignore[arg-type]


def test_evaluation_record_is_not_online_safe():
    """EvaluationRecord must not be constructible into a prefix path."""
    assert "success" in EvaluationRecord.model_fields
    assert "success" in ORACLE_FIELD_NAMES
    assert "success" not in StepRecord.model_fields
    assert "success" not in SessionMeta.model_fields


def test_session_outcome_is_separate_from_session_meta():
    shared = set(SessionOutcome.model_fields) & set(SessionMeta.model_fields)
    assert shared == {"session_id"}, f"unexpected overlap: {shared}"
