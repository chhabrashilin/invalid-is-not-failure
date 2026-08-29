"""Regression tests for the Phase 0 measurement defects D1-D4, plus the
evaluator bug that Phase 0 discovered (Phase 0.5 Steps 2-5, 15).

Each defect gets tests that would have FAILED before the fix.
"""

from __future__ import annotations

import pytest

from checkpoint.docker_env import PIPEFAIL_PREFIX
# Aliased on import: pytest tries to collect module-level names starting with
# "Test", and these are enums with constructors.
from evaluation.test_detect import TestFramework as TF
from evaluation.test_detect import TestStatus as TS
from evaluation.test_detect import (
    classify_test_command,
    detect_and_parse,
    parse_test_output,
)
from instrumentation.repo_state import (
    DEFAULT_EXCLUDE_PATTERNS,
    RepoChanges,
    parse_numstat,
    parse_porcelain,
)
from trajectory.schema import (
    ExecutionBackend,
    MockBackendRejected,
    categorize_error,
    require_real_backend,
)

# =========================================================================
# D1 -- repository-scoped change tracking
# =========================================================================

PORCELAIN_REALISTIC = """\
 M astropy/modeling/separable.py
?? scratch_notes.txt
 D astropy/modeling/obsolete.py
 M .pytest_cache/v/cache/lastfailed
?? __pycache__/separable.cpython-39.pyc
 M astropy/modeling/tests/test_separable.py
"""


def test_d1_porcelain_excludes_cache_and_test_files():
    """The Phase 0 bug: caches counted as agent changes (537 'files changed')."""
    mod, add, dele = parse_porcelain(
        PORCELAIN_REALISTIC,
        DEFAULT_EXCLUDE_PATTERNS,
        exclude_paths=("astropy/modeling/tests/test_separable.py",),
    )
    # separable.py modified; scratch_notes.txt added; obsolete.py deleted.
    # pytest cache, __pycache__ and the instance test file are all excluded.
    assert (mod, add, dele) == (1, 1, 1)


def test_d1_test_patch_can_never_be_attributed_to_the_agent():
    """CONTAMINATION RULE: evaluator-touched test files are excluded."""
    porcelain = " M astropy/modeling/tests/test_separable.py\n"
    mod, add, dele = parse_porcelain(
        porcelain, DEFAULT_EXCLUDE_PATTERNS,
        exclude_paths=("astropy/modeling/tests/test_separable.py",),
    )
    assert (mod, add, dele) == (0, 0, 0)


def test_d1_rename_counted_once_as_modification():
    """A rename must not be double-counted as both an add and a delete."""
    mod, add, dele = parse_porcelain('R  old.py -> new.py\n', DEFAULT_EXCLUDE_PATTERNS)
    assert (mod, add, dele) == (1, 0, 0)


def test_d1_numstat_counts_lines_and_skips_binary_and_caches():
    numstat = (
        "12\t3\tastropy/modeling/separable.py\n"
        "-\t-\tdocs/logo.png\n"
        "99\t99\t.pytest_cache/v/cache/lastfailed\n"
        "5\t0\tastropy/modeling/tests/test_separable.py\n"
    )
    added, deleted = parse_numstat(
        numstat, DEFAULT_EXCLUDE_PATTERNS,
        exclude_paths=("astropy/modeling/tests/test_separable.py",),
    )
    assert (added, deleted) == (12, 3)


def test_d1_failed_measurement_is_not_silently_zero():
    """A failed git call must be distinguishable from 'no changes'."""
    rc = RepoChanges(measured=False, note="git status failed")
    assert rc.measured is False
    assert rc.files_changed_total == 0  # value is zero...
    # ...but `measured` records that the zero is not a real observation.
    assert RepoChanges(measured=True).measured is True


# =========================================================================
# D2 -- exit-status preservation through pipelines
# =========================================================================


def test_d2_pipefail_prefix_is_applied():
    assert PIPEFAIL_PREFIX.strip() == "set -o pipefail;"


@pytest.mark.parametrize(
    "code,stderr,expected_nonzero",
    [(0, "", False), (1, "assert failed", True), (127, "command not found", True)],
)
def test_d2_error_category_tracks_exit_status(code, stderr, expected_nonzero):
    cat = categorize_error(code, stderr)
    assert (cat.value != "none") == expected_nonzero


def test_d2_timeout_has_its_own_category():
    assert categorize_error(None, "timeout").value == "timeout"
    assert categorize_error(124, "").value == "timeout"


def test_d2_command_not_found_classified():
    assert categorize_error(127, "bash: foo: command not found").value == "command_not_found"


#: Reuse the already-pulled instance image: it has bash, and no extra pull is
#: needed. If it is absent the live check is skipped rather than faked.
LIVE_IMAGE = "swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest"


def _live_image_available() -> bool:
    from checkpoint.docker_env import docker_available, image_exists_locally

    return docker_available() and image_exists_locally(LIVE_IMAGE)


@pytest.mark.skipif(not _live_image_available(), reason="docker/image unavailable")
def test_d2_live_pipeline_preserves_failing_status():
    """THE Phase 0 defect, reproduced live: `false | tail` must be nonzero.

    Before the fix this returned 0 because the pipeline reports tail's status,
    so a FAILING pytest run was recorded as a success.
    """
    from checkpoint.docker_env import exec_command, remove_container, start_container

    cid = start_container(LIVE_IMAGE)
    try:
        with_pipefail = exec_command(cid, "false | tail -5", pipefail=True)
        without = exec_command(cid, "false | tail -5", pipefail=False)
        assert with_pipefail.exit_status != 0, "pipefail failed to preserve status"
        assert without.exit_status == 0, "control: without pipefail status is masked"
        ok = exec_command(cid, "true | tail -5", pipefail=True)
        assert ok.exit_status == 0
    finally:
        remove_container(cid)


# =========================================================================
# D3 -- test invocation detection
# =========================================================================


@pytest.mark.parametrize(
    "command,expected",
    [
        ("pytest -q", TF.PYTEST),
        ("python -m pytest tests/", TF.PYTEST),
        ("python3 -m unittest discover", TF.UNITTEST),
        ("tox -e py39", TF.TOX),
        ("npm test", TF.NPM),
        ("npm run test", TF.NPM),
        ("yarn test", TF.YARN),
        ("pnpm test", TF.PNPM),
        ("cargo test --all", TF.CARGO),
        ("go test ./...", TF.GO),
        ("mvn -q test", TF.MAVEN),
        ("./gradlew test", TF.GRADLE),
        ("make test", TF.MAKE),
        ("cd /testbed && python -m pytest -q foo.py", TF.PYTEST),
        ("source activate env && pytest -x", TF.PYTEST),
        # negatives -- these are NOT test invocations
        ("grep -r pytest docs/", TF.NONE),
        ("ls tests/", TF.NONE),
        ("cat test_separable.py", TF.NONE),
        ("echo 'run npm test later'", TF.NONE),
        ("git log --grep='go test'", TF.NONE),
    ],
)
def test_d3_command_classification(command, expected):
    assert classify_test_command(command) == expected


PYTEST_FAIL = "= 2 failed, 3 passed, 1 skipped in 0.42s ="
PYTEST_PASS = "..                                            [100%]\n2 passed in 0.14s"
PYTEST_NO_TESTS = "Internet access disabled\n\nno tests ran in 0.23s"
PYTEST_ERROR = "1 error in 0.10s"
PYTEST_GARBAGE = "Segmentation fault (core dumped)"


def test_d3_parses_mixed_summary():
    out = parse_test_output(TF.PYTEST, PYTEST_FAIL, "", 1)
    assert out.status == TS.RAN_PARSED
    assert (out.passed, out.failed, out.skipped) == (3, 2, 1)


def test_d3_parses_all_pass():
    out = parse_test_output(TF.PYTEST, PYTEST_PASS, "", 0)
    assert out.status == TS.RAN_PARSED and out.passed == 2


def test_d3_no_tests_ran_is_parsed_as_zeros_not_unparseable():
    """This is the exact run-001 evaluator situation."""
    out = parse_test_output(TF.PYTEST, PYTEST_NO_TESTS, "", 4)
    assert out.status == TS.RAN_PARSED
    assert (out.passed, out.failed) == (0, 0)
    assert out.invoked is True


def test_d3_unparseable_is_not_silently_no_test():
    """THE D3 defect: unparseable output must NOT collapse to 'no test ran'."""
    out = parse_test_output(TF.PYTEST, PYTEST_GARBAGE, "", 139)
    assert out.status == TS.RAN_UNPARSEABLE
    assert out.invoked is True
    assert out.status != TS.NOT_RUN


def test_d3_non_test_command_is_not_run():
    out = detect_and_parse("ls -la", "total 8", "", 0)
    assert out.status == TS.NOT_RUN and out.invoked is False


def test_d3_errors_counted():
    out = parse_test_output(TF.PYTEST, PYTEST_ERROR, "", 1)
    assert out.status == TS.RAN_PARSED and out.errored == 1


def test_d3_unittest_parsing():
    text = "Ran 5 tests in 0.01s\n\nFAILED (failures=2, errors=1)"
    out = parse_test_output(TF.UNITTEST, text, "", 1)
    assert out.status == TS.RAN_PARSED
    assert (out.passed, out.failed, out.errored) == (2, 2, 1)


def test_d3_recognised_but_unparsed_framework_is_honest():
    out = parse_test_output(TF.CARGO, "some cargo output", "", 0)
    assert out.status == TS.RAN_UNPARSEABLE and out.invoked is True


# =========================================================================
# D4 -- mock backend must never enter scientific collection
# =========================================================================


def test_d4_mock_backend_rejected(session_meta):
    with pytest.raises(MockBackendRejected):
        require_real_backend(session_meta)  # fixture defaults to mock


def test_d4_real_backend_accepted(session_meta):
    real = session_meta.model_copy(
        update={
            "execution_backend": ExecutionBackend.MINI_SWE_AGENT,
            "model_id": "some-real-model",
            "agent_library_version": "2.4.6",
        }
    )
    require_real_backend(real)  # must not raise


def test_d4_real_backend_with_mock_model_id_still_rejected(session_meta):
    sneaky = session_meta.model_copy(
        update={"execution_backend": ExecutionBackend.MINI_SWE_AGENT,
                "model_id": "mock:scripted-v1"}
    )
    with pytest.raises(MockBackendRejected):
        require_real_backend(sneaky)


# =========================================================================
# Evaluator regression -- the run-001 bug must never return silently
# =========================================================================


def test_swebench_parametrized_tests_require_test_patch():
    """REGRESSION: SWE-bench FAIL_TO_PASS ids do not exist before test_patch.

    Phase 0 run 001 ran the FAIL_TO_PASS node ids against an unpatched repo.
    pytest reported "no tests ran" (exit 4) and the harness recorded
    success=False with null counts -- a silently meaningless verdict that would
    have labelled every Phase 1 session a failure.

    The guard: `evaluate_container` must accept a test_patch, and a verdict
    derived from a "no tests ran" result must never be reported as a legitimate
    failure. Here we assert the detector recognises that state explicitly.
    """
    import inspect

    from evaluation.evaluator import apply_test_patch, evaluate_container

    sig = inspect.signature(evaluate_container)
    for required in ("test_patch_path", "test_files", "base_commit"):
        assert required in sig.parameters, (
            f"evaluate_container lost the {required!r} parameter; the run-001 "
            "test_patch bug can silently return"
        )
    assert callable(apply_test_patch)

    # "no tests ran" must be an identifiable state, not an ordinary failure.
    out = parse_test_output(TF.PYTEST, PYTEST_NO_TESTS, "", 4)
    assert out.passed == 0 and out.failed == 0, (
        "a 'no tests ran' result must parse to zero/zero so it can be "
        "distinguished from a genuine test failure"
    )
