"""Online feature extraction (Stage 3 §6.2, Model A and Model B ladders).

Every function here accepts a `TrajectoryPrefix` and nothing else. It is not
possible to pass a full trajectory or an outcome record: the type system and the
prefix's own boundary checks prevent it.

Model A = trivial proxies (the baseline the real signal must beat, RQ3.3).
Model B = behavioural features.

NOTE: this module computes *features*, not predictions. No model is trained in
Phase 0 (that belongs to Phase 2).
"""

from __future__ import annotations

from collections import Counter

from trajectory.schema import ActionType, ErrorCategory, TrajectoryPrefix


def extract_model_a_features(prefix: TrajectoryPrefix) -> dict[str, float]:
    """Trivial proxies: session age, consumed compute, context length.

    Stage 3 RQ3.3: the behavioural signal must beat THIS to be interesting.
    """
    if len(prefix) == 0:
        return {
            "a_steps_taken": 0.0,
            "a_model_calls": 0.0,
            "a_cumulative_completion_tokens": 0.0,
            "a_cumulative_prompt_tokens": 0.0,
            "a_context_length_tokens": 0.0,
            "a_elapsed_s": 0.0,
            "a_budget_fraction_consumed": 0.0,
        }
    last = prefix.step(len(prefix) - 1)
    cap = prefix.session.step_budget_cap or 0
    return {
        "a_steps_taken": float(len(prefix)),
        "a_model_calls": float(last.cumulative_model_calls),
        "a_cumulative_completion_tokens": float(last.cumulative_completion_tokens),
        "a_cumulative_prompt_tokens": float(last.cumulative_prompt_tokens),
        "a_context_length_tokens": float(last.context_length_tokens),
        "a_elapsed_s": float(last.elapsed_s),
        # Budget fraction is computed against the PRE-DECLARED cap, never against
        # the realized trajectory length (Stage 3 §2.1, "the normalization trap").
        "a_budget_fraction_consumed": (float(len(prefix)) / cap) if cap else 0.0,
    }


def extract_model_b_features(prefix: TrajectoryPrefix) -> dict[str, float]:
    """Behavioural features (Class A only): failures, repeats, diversity, tests."""
    n = len(prefix)
    if n == 0:
        return {
            "b_tool_calls": 0.0,
            "b_failed_tool_calls": 0.0,
            "b_failure_rate": 0.0,
            "b_distinct_commands": 0.0,
            "b_action_diversity": 0.0,
            "b_max_command_repeat": 0.0,
            "b_repeat_ratio": 0.0,
            "b_max_error_repeat": 0.0,
            "b_distinct_error_categories": 0.0,
            "b_test_invocations": 0.0,
            "b_test_runs_parsed": 0.0,
            "b_test_runs_unparseable": 0.0,
            "b_last_tests_failed": 0.0,
            "b_repo_files_changed": 0.0,
            "b_repo_lines_added": 0.0,
            "b_repo_lines_deleted": 0.0,
            "b_consecutive_failures": 0.0,
        }

    cmd_counter: Counter[str] = Counter()
    err_counter: Counter[str] = Counter()
    failed = 0
    tool_calls = 0
    test_invocations = 0
    test_parsed = 0
    test_unparseable = 0
    last_tests_failed = 0.0
    repo_files_changed = 0
    repo_lines_added = 0
    repo_lines_deleted = 0
    consecutive_failures = 0
    running_consecutive = 0

    for step in prefix:
        if step.action_type == ActionType.BASH:
            tool_calls += 1
            cmd_counter[step.command_normalized_hash] += 1
        if step.error_category != ErrorCategory.NONE:
            failed += 1
            err_counter[step.error_category.value] += 1
            running_consecutive += 1
            consecutive_failures = max(consecutive_failures, running_consecutive)
        else:
            running_consecutive = 0
        if step.test_invocation:
            test_invocations += 1
            if step.test_status == "TEST_RAN_RESULT_PARSED":
                test_parsed += 1
                if step.tests_failed is not None:
                    last_tests_failed = float(step.tests_failed)
            elif step.test_status == "TEST_RAN_RESULT_UNPARSEABLE":
                test_unparseable += 1
        # D1: repository-scoped counts are cumulative snapshots, so take the
        # latest measured value rather than summing per-step deltas.
        if step.repo_changes_measured:
            repo_files_changed = (
                step.repo_files_modified + step.repo_files_added + step.repo_files_deleted
            )
            repo_lines_added = step.repo_lines_added
            repo_lines_deleted = step.repo_lines_deleted

    distinct_cmds = len(cmd_counter)
    max_repeat = max(cmd_counter.values()) if cmd_counter else 0
    max_err_repeat = max(err_counter.values()) if err_counter else 0

    return {
        "b_tool_calls": float(tool_calls),
        "b_failed_tool_calls": float(failed),
        "b_failure_rate": float(failed) / n,
        "b_distinct_commands": float(distinct_cmds),
        # action diversity: distinct commands per tool call (1.0 = never repeats)
        "b_action_diversity": (float(distinct_cmds) / tool_calls) if tool_calls else 0.0,
        "b_max_command_repeat": float(max_repeat),
        "b_repeat_ratio": (
            float(tool_calls - distinct_cmds) / tool_calls if tool_calls else 0.0
        ),
        "b_max_error_repeat": float(max_err_repeat),
        "b_distinct_error_categories": float(len(err_counter)),
        "b_test_invocations": float(test_invocations),
        "b_test_runs_parsed": float(test_parsed),
        "b_test_runs_unparseable": float(test_unparseable),
        "b_last_tests_failed": last_tests_failed,
        "b_repo_files_changed": float(repo_files_changed),
        "b_repo_lines_added": float(repo_lines_added),
        "b_repo_lines_deleted": float(repo_lines_deleted),
        "b_consecutive_failures": float(consecutive_failures),
    }


def extract_online_features(prefix: TrajectoryPrefix) -> dict[str, float]:
    """Full online feature vector (Model A + Model B). Class A signals only.

    Args:
        prefix: view of the first k steps. Cannot address steps at index >= k.

    Returns:
        Mapping of feature name to value. Deterministic given the prefix.

    Raises:
        TypeError: if anything other than a TrajectoryPrefix is passed. This
            guard is deliberate: passing a full trajectory or an outcome record
            is Class-C leakage and must fail loudly rather than duck-type.
    """
    if not isinstance(prefix, TrajectoryPrefix):
        raise TypeError(
            "extract_online_features accepts only a TrajectoryPrefix; got "
            f"{type(prefix).__name__}. Passing outcome or full-trajectory objects "
            "would be Class-C leakage (Stage 3 §2.1)."
        )
    feats = extract_model_a_features(prefix)
    feats.update(extract_model_b_features(prefix))
    return feats
