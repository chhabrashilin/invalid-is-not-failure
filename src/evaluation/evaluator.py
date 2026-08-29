"""External outcome evaluator (Stage 3 §12, Phase 0 Step 12).

SCIENTIFIC INVARIANT: the trajectory logger must NOT determine success. This
module runs independently, produces its own raw artifact, and emits an
`EvaluationRecord` (a Class-C / post-hoc type). Nothing in this module is
reachable from `extract_online_features`.

For Phase 0 the evaluator executes the instance's real test command inside the
container and parses the pytest summary. It deliberately does NOT consult the
agent's own claims about what it did.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from checkpoint.docker_env import exec_command
from trajectory.schema import EvaluationRecord

EVALUATOR_NAME = "phase0-pytest-parser"
EVALUATOR_VERSION = "0.1.0"

# pytest summary lines, e.g. "= 3 failed, 12 passed, 1 skipped in 4.21s ="
_PASSED = re.compile(r"(\d+)\s+passed")
_FAILED = re.compile(r"(\d+)\s+failed")
_ERRORS = re.compile(r"(\d+)\s+error")


@dataclass
class ParsedTestResult:
    passed: int | None
    failed: int | None
    errors: int | None

    @property
    def any_parsed(self) -> bool:
        return not (self.passed is None and self.failed is None and self.errors is None)


def parse_pytest_output(text: str) -> ParsedTestResult:
    """Parse a pytest summary. Pure function; unit-tested against fixtures."""

    def _find(pattern: re.Pattern[str]) -> int | None:
        matches = pattern.findall(text)
        return int(matches[-1]) if matches else None

    return ParsedTestResult(
        passed=_find(_PASSED), failed=_find(_FAILED), errors=_find(_ERRORS)
    )


def apply_test_patch(
    container_id: str, patch_host_path: Path, test_files: list[str], base_commit: str
) -> tuple[bool, str]:
    """Apply the instance's SWE-bench `test_patch` before evaluating.

    REQUIRED BY THE BENCHMARK PROTOCOL. The FAIL_TO_PASS node ids are
    parametrisations that only exist *after* the test patch is applied; without
    this step pytest reports "no tests ran" (exit 4) and the verdict is
    meaningless. Phase 0 caught exactly this bug.

    The test files are first reset to `base_commit` so the agent cannot
    influence the tests it is judged by -- the agent is allowed to edit source,
    never the hidden test suite.

    Returns:
        (ok, log) where `ok` is True if the patch applied cleanly.
    """
    log_parts: list[str] = []
    reset = exec_command(
        container_id, f"cd /testbed && git checkout {base_commit} -- {' '.join(test_files)}"
    )
    log_parts.append(f"$ git checkout {base_commit} -- <tests>\nexit={reset.exit_status}\n{reset.stderr[:500]}")

    patch_text = patch_host_path.read_text(encoding="utf-8")
    # write the patch into the container via a heredoc to avoid `docker cp`
    heredoc = (
        "cat > /tmp/test_patch.diff <<'PHASE0_PATCH_EOF'\n" + patch_text + "\nPHASE0_PATCH_EOF"
    )
    write = exec_command(container_id, heredoc)
    log_parts.append(f"$ write /tmp/test_patch.diff\nexit={write.exit_status}\n{write.stderr[:500]}")

    apply_res = exec_command(container_id, "cd /testbed && git apply -v /tmp/test_patch.diff")
    log_parts.append(
        f"$ git apply -v /tmp/test_patch.diff\nexit={apply_res.exit_status}\n"
        f"{apply_res.stdout[:1000]}\n{apply_res.stderr[:1000]}"
    )
    return apply_res.exit_status == 0, "\n".join(log_parts)


def evaluate_container(
    *,
    container_id: str,
    session_id: str,
    instance_id: str,
    test_command: str,
    benchmark_version: str,
    artifact_dir: Path,
    timeout: float = 1800.0,
    test_patch_path: Path | None = None,
    test_files: list[str] | None = None,
    base_commit: str | None = None,
) -> EvaluationRecord:
    """Run the evaluation command in the container and record the verdict.

    Args:
        container_id: container holding the post-agent filesystem state.
        test_command: the benchmark's test invocation (not chosen by the agent).
        artifact_dir: where the raw evaluator output is written.
        test_patch_path: SWE-bench `test_patch` to apply before evaluating.
        test_files: paths reset to `base_commit` before patching.
        base_commit: instance base commit.

    Returns:
        An `EvaluationRecord`. Success requires at least one passing test and
        zero failures/errors -- a conservative rule, documented rather than tuned.
    """
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    patch_log = ""
    if test_patch_path is not None:
        ok, patch_log = apply_test_patch(
            container_id, Path(test_patch_path), test_files or [], base_commit or "HEAD"
        )
        patch_log = f"--- test_patch application (ok={ok}) ---\n{patch_log}\n"

    result = exec_command(container_id, test_command, timeout=timeout)
    raw = (
        patch_log
        + f"$ {test_command}\n"
        f"--- exit_status: {result.exit_status}\n"
        f"--- duration_ms: {result.duration_ms:.1f}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}\n"
    )
    artifact_path = artifact_dir / f"evaluator_raw_{session_id}.txt"
    artifact_path.write_text(raw, encoding="utf-8")
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()

    parsed = parse_pytest_output(result.stdout + "\n" + result.stderr)
    failed = (parsed.failed or 0) + (parsed.errors or 0)
    passed = parsed.passed or 0
    success = bool(result.exit_status == 0 and passed > 0 and failed == 0)
    total = passed + failed
    score = (passed / total) if total else 0.0

    return EvaluationRecord(
        session_id=session_id,
        instance_id=instance_id,
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        benchmark_version=benchmark_version,
        evaluated_ts=datetime.now(timezone.utc).isoformat(),
        success=success,
        score=score,
        tests_passed=parsed.passed,
        tests_failed=failed if parsed.any_parsed else None,
        raw_artifact_path=str(artifact_path),
        raw_artifact_sha256=digest,
    )
