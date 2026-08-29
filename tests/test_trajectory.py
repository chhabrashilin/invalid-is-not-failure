"""Schema, accounting, ordering, storage and config tests (Phase 0 Step 16)."""

from __future__ import annotations

import json

import pytest
import yaml

from evaluation.evaluator import parse_pytest_output
from instrumentation.mock_lm import MOCK_MODEL_PREFIX, ScriptedMockLM, StochasticMockLM
from instrumentation.recorder import TrajectoryRecorder
from trajectory.features import extract_online_features
from trajectory.schema import (
    ActionType,
    EnvironmentSnapshotMetadata,
    ErrorCategory,
    SessionMeta,
    StepRecord,
    TrajectoryPrefix,
    categorize_error,
    normalize_command,
)
from trajectory.store import (
    RawTrajectoryWriter,
    load_prefix,
    load_session,
    unfreeze_run,
    verify_manifest,
)


# --- 1. serialization round trip -------------------------------------------

def test_step_serialization_roundtrip(fixture_recorder):
    for step in fixture_recorder.steps:
        restored = StepRecord.model_validate_json(step.model_dump_json())
        assert restored == step


def test_session_serialization_roundtrip(session_meta):
    assert SessionMeta.model_validate_json(session_meta.model_dump_json()) == session_meta


# --- 2. deterministic fixture ----------------------------------------------

def test_fixture_is_deterministic(session_meta):
    def build():
        rec = TrajectoryRecorder("sess-fixture", start_monotonic=0.0)
        rec.record_step(
            action_type=ActionType.BASH, command="ls -la", prompt_tokens=10,
            completion_tokens=5, context_length_tokens=100, stdout="x",
            exit_status=0, elapsed_s=0.0,
        )
        return rec.steps[0]

    a, b = build(), build()
    assert a.model_dump(exclude={"ts"}) == b.model_dump(exclude={"ts"})


def test_scripted_mock_lm_is_deterministic():
    cmds = ["a", "b", "c"]
    one = [ScriptedMockLM(cmds).next_response().command for _ in range(3)]
    lm = ScriptedMockLM(cmds)
    two = [lm.next_response().command for _ in range(3)]
    assert two == cmds
    assert one == ["a", "a", "a"]  # fresh instance each time restarts the script


def test_stochastic_mock_same_seed_identical():
    cands = [["x1", "x2"], ["y1", "y2"], ["z1", "z2"]]
    a = [StochasticMockLM(cands, seed=7).next_response().command for _ in range(1)]
    lm1, lm2 = StochasticMockLM(cands, seed=7), StochasticMockLM(cands, seed=7)
    s1 = [lm1.next_response().command for _ in range(3)]
    s2 = [lm2.next_response().command for _ in range(3)]
    assert s1 == s2
    assert a  # sanity


def test_mock_model_ids_are_flagged():
    assert ScriptedMockLM([]).model_id.startswith(MOCK_MODEL_PREFIX)
    assert StochasticMockLM([], 1).model_id.startswith(MOCK_MODEL_PREFIX)


# --- 3. event ordering ------------------------------------------------------

def test_step_ids_are_contiguous_and_ordered(fixture_recorder):
    ids = [s.step_id for s in fixture_recorder.steps]
    assert ids == list(range(len(ids)))


def test_writer_rejects_out_of_order_steps(tmp_path, session_meta, fixture_recorder):
    with RawTrajectoryWriter(tmp_path / "run") as w:
        w.write_session(session_meta)
        w.write_step(fixture_recorder.steps[0])
        with pytest.raises(ValueError):
            w.write_step(fixture_recorder.steps[2])
    unfreeze_run(tmp_path / "run")


# --- 4. cumulative accounting ----------------------------------------------

def test_cumulative_counters_are_monotone(fixture_recorder):
    steps = fixture_recorder.steps
    for a, b in zip(steps, steps[1:]):
        assert b.cumulative_prompt_tokens >= a.cumulative_prompt_tokens
        assert b.cumulative_completion_tokens >= a.cumulative_completion_tokens
        assert b.cumulative_model_calls > a.cumulative_model_calls
        assert b.cumulative_tool_calls >= a.cumulative_tool_calls
        assert b.cumulative_failed_tool_calls >= a.cumulative_failed_tool_calls


def test_cumulative_totals_match_manual_sum(fixture_recorder):
    steps = fixture_recorder.steps
    assert steps[-1].cumulative_prompt_tokens == sum(s.prompt_tokens for s in steps)
    assert steps[-1].cumulative_completion_tokens == sum(s.completion_tokens for s in steps)
    assert steps[-1].cumulative_model_calls == len(steps)


def test_failed_tool_calls_counted(fixture_recorder):
    # fixture step 3 is `pytest -q` exiting 1 -> exactly one failure
    assert fixture_recorder.steps[-1].cumulative_failed_tool_calls == 1


# --- 5. repeated-command / error categorisation ----------------------------

def test_repeated_command_counts_prior_occurrences(fixture_recorder):
    # "pytest -q" appears at index 2 and 4
    ks = {s.step_id: s.repeated_command_k for s in fixture_recorder.steps}
    assert ks[2] == 0
    assert ks[4] == 1


def test_normalize_command_collapses_whitespace():
    assert normalize_command("ls   -la  ") == normalize_command("ls -la")


@pytest.mark.parametrize(
    "code,stderr,expected",
    [
        (0, "", ErrorCategory.NONE),
        (127, "bash: foo: command not found", ErrorCategory.COMMAND_NOT_FOUND),
        (1, "No such file or directory", ErrorCategory.FILE_NOT_FOUND),
        (126, "permission denied", ErrorCategory.PERMISSION),
        (1, "SyntaxError: invalid syntax", ErrorCategory.SYNTAX),
        (124, "", ErrorCategory.TIMEOUT),
        (None, "timeout", ErrorCategory.TIMEOUT),
        (2, "boom", ErrorCategory.NONZERO_EXIT),
    ],
)
def test_error_categorisation(code, stderr, expected):
    assert categorize_error(code, stderr) == expected


# --- 6. prefix-only extraction ---------------------------------------------

def test_features_depend_only_on_prefix_length(session_meta, fixture_recorder):
    f3 = extract_online_features(TrajectoryPrefix(session_meta, fixture_recorder.steps, 3))
    f5 = extract_online_features(TrajectoryPrefix(session_meta, fixture_recorder.steps, 5))
    assert f3["a_steps_taken"] == 3.0
    assert f5["a_steps_taken"] == 5.0
    assert f5["b_max_command_repeat"] >= f3["b_max_command_repeat"]


def test_budget_fraction_uses_declared_cap_not_realized_length(session_meta, fixture_recorder):
    prefix = TrajectoryPrefix(session_meta, fixture_recorder.steps, 3)
    feats = extract_online_features(prefix)
    assert feats["a_budget_fraction_consumed"] == pytest.approx(3 / session_meta.step_budget_cap)


def test_empty_prefix_features_are_defined(session_meta, fixture_recorder):
    feats = extract_online_features(TrajectoryPrefix(session_meta, fixture_recorder.steps, 0))
    assert feats["a_steps_taken"] == 0.0 and feats["b_tool_calls"] == 0.0


# --- 7. snapshot metadata ---------------------------------------------------

def test_snapshot_metadata_validates():
    snap = EnvironmentSnapshotMetadata(
        snapshot_id="snap-1", parent_session_id="sess-fixture", checkpoint_step=3,
        created_ts="2026-08-29T00:00:00+00:00", container_id="c1",
        image_ref="phase0/ckpt:abc", image_id="sha256:deadbeef",
        filesystem_digest="sha256:deadbeef", message_history_hash="0" * 64,
        cumulative_model_calls=3, cumulative_completion_tokens=15,
    )
    assert EnvironmentSnapshotMetadata.model_validate_json(snap.model_dump_json()) == snap


def test_snapshot_rejects_negative_checkpoint():
    with pytest.raises(Exception):
        EnvironmentSnapshotMetadata(
            snapshot_id="s", parent_session_id="p", checkpoint_step=-1,
            created_ts="t", container_id="c", image_ref="r", image_id="i",
            filesystem_digest="d", message_history_hash="h",
            cumulative_model_calls=0, cumulative_completion_tokens=0,
        )


# --- 8/9. continuation identity and parent immutability --------------------

def test_continuation_gets_new_identity_and_parent_link(session_meta):
    child = session_meta.model_copy(
        update={"session_id": "cont-1", "parent_session_id": session_meta.session_id,
                "forked_at_step": 3}
    )
    assert child.session_id != session_meta.session_id
    assert child.parent_session_id == session_meta.session_id
    assert child.forked_at_step == 3
    assert session_meta.parent_session_id is None  # parent unchanged


def test_raw_run_directory_cannot_be_reused(tmp_path, session_meta):
    run = tmp_path / "run"
    with RawTrajectoryWriter(run) as w:
        w.write_session(session_meta)
    unfreeze_run(run)
    with pytest.raises(FileExistsError):
        RawTrajectoryWriter(run)


def test_session_file_cannot_be_rewritten(tmp_path, session_meta):
    run = tmp_path / "run"
    w = RawTrajectoryWriter(run)
    w.__enter__()
    w.write_session(session_meta)
    with pytest.raises(FileExistsError):
        w.write_session(session_meta)
    w.close()
    unfreeze_run(run)


# --- 10. raw artifact hashing ----------------------------------------------

def test_manifest_hashes_and_detects_tampering(tmp_path, session_meta, fixture_recorder,
                                               fixture_outcome):
    run = tmp_path / "run"
    with RawTrajectoryWriter(run) as w:
        w.write_session(session_meta)
        for s in fixture_recorder.steps:
            w.write_step(s)
        w.write_outcome(fixture_outcome)
    ok, problems = verify_manifest(run)
    assert ok, problems

    unfreeze_run(run)
    (run / "steps.jsonl").write_text("tampered\n", encoding="utf-8")
    ok2, problems2 = verify_manifest(run)
    assert not ok2 and any("steps.jsonl" in p for p in problems2)


def test_raw_files_are_read_only_after_close(tmp_path, session_meta):
    run = tmp_path / "run"
    with RawTrajectoryWriter(run) as w:
        w.write_session(session_meta)
    import os
    assert not os.access(run / "session.json", os.W_OK)
    unfreeze_run(run)


# --- 11. evaluator separation ----------------------------------------------

def test_load_prefix_never_reads_outcome_files(tmp_path, session_meta, fixture_recorder,
                                               fixture_outcome, monkeypatch):
    run = tmp_path / "run"
    with RawTrajectoryWriter(run) as w:
        w.write_session(session_meta)
        for s in fixture_recorder.steps:
            w.write_step(s)
        w.write_outcome(fixture_outcome)

    opened: list[str] = []
    real_open = type(run).open

    def spy_open(self, *a, **k):
        opened.append(self.name)
        return real_open(self, *a, **k)

    monkeypatch.setattr(type(run), "open", spy_open)
    prefix = load_prefix(run, 2)
    assert len(prefix) == 2
    assert "outcome.json" not in opened
    assert "evaluation.json" not in opened
    unfreeze_run(run)


def test_load_prefix_refuses_beyond_available(tmp_path, session_meta, fixture_recorder):
    run = tmp_path / "run"
    with RawTrajectoryWriter(run) as w:
        w.write_session(session_meta)
        for s in fixture_recorder.steps[:2]:
            w.write_step(s)
    with pytest.raises(IndexError):
        load_prefix(run, 5)
    unfreeze_run(run)


@pytest.mark.parametrize(
    "text,passed,failed",
    [
        ("3 passed in 1.2s", 3, None),
        ("= 1 failed, 2 passed in 0.4s =", 2, 1),
        ("2 errors in 0.1s", None, None),
        ("no summary here", None, None),
    ],
)
def test_pytest_parser(text, passed, failed):
    r = parse_pytest_output(text)
    assert r.passed == passed
    assert r.failed == failed


# --- 12. config serialization ----------------------------------------------

def test_phase0_config_is_valid_yaml_and_complete():
    from pathlib import Path
    cfg = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs/phase0/smoke.yaml").read_text(
            encoding="utf-8"
        )
    )
    for key in ("run_id", "instance", "evaluation", "session", "checkpoint",
                "mock_lm", "fork", "output"):
        assert key in cfg, f"missing config key {key}"
    assert cfg["checkpoint"]["at_step"] < cfg["session"]["step_budget_cap"]
    assert json.dumps(cfg)  # config must be JSON-serialisable for provenance


def test_selected_instance_record_matches_config():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sel = json.loads((root / "configs/phase0/selected_instance.json").read_text())
    cfg = yaml.safe_load((root / "configs/phase0/smoke.yaml").read_text(encoding="utf-8"))
    assert sel["selected_instance_id"] == cfg["instance"]["instance_id"]
    assert sel["rule_declared_before_execution"] is True
