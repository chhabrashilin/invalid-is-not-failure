"""Test-invocation detection and result parsing (Phase 0.5 defect D3).

Phase 0 detected testing with a brittle substring check (`"pytest" in cmd or
" test" in cmd`), which produced `test_invocation=False` even when tests had
actually run, and silently conflated "no test ran" with "test ran but output was
unparseable". Those are different states and must never be merged: the first
says nothing about progress, the second is a parser gap we need to see.

This module replaces that with an auditable classifier plus per-framework
parsers, and a three-valued status.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum


class TestStatus(str, Enum):
    """Three-valued outcome. Never collapse UNPARSEABLE into NOT_RUN."""

    NOT_RUN = "TEST_NOT_RUN"
    RAN_PARSED = "TEST_RAN_RESULT_PARSED"
    RAN_UNPARSEABLE = "TEST_RAN_RESULT_UNPARSEABLE"


class TestFramework(str, Enum):
    NONE = "none"
    PYTEST = "pytest"
    UNITTEST = "unittest"
    TOX = "tox"
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    CARGO = "cargo"
    GO = "go"
    MAVEN = "maven"
    GRADLE = "gradle"
    MAKE = "make"


@dataclass(frozen=True)
class TestOutcome:
    status: TestStatus
    framework: TestFramework
    exit_status: int | None = None
    passed: int | None = None
    failed: int | None = None
    errored: int | None = None
    skipped: int | None = None

    @property
    def invoked(self) -> bool:
        return self.status != TestStatus.NOT_RUN


# --------------------------------------------------------------------------
# Command classification
# --------------------------------------------------------------------------

# Shell operators that separate commands within one line.
_SPLIT = re.compile(r"\|\||&&|[;|]")


def _segments(command: str) -> list[list[str]]:
    """Split a shell line into token lists, one per sub-command.

    Uses shlex so quoted arguments do not split. Failures degrade to a naive
    whitespace split rather than raising -- an agent can emit anything.
    """
    out: list[list[str]] = []
    for raw in _SPLIT.split(command):
        raw = raw.strip()
        if not raw:
            continue
        try:
            toks = shlex.split(raw)
        except ValueError:
            toks = raw.split()
        # drop leading env assignments (FOO=bar cmd) and `sudo`
        while toks and ("=" in toks[0] and not toks[0].startswith("-") or toks[0] == "sudo"):
            toks = toks[1:]
        if toks:
            out.append(toks)
    return out


def classify_test_command(command: str) -> TestFramework:
    """Identify the test framework a command invokes, if any.

    Matches on the command *structure* (argv position), not on a substring
    appearing anywhere in the line, so `grep pytest notes.txt` is correctly
    classified as NOT a test invocation.
    """
    for toks in _segments(command):
        head = toks[0].rsplit("/", 1)[-1]
        rest = toks[1:]

        if head in ("pytest", "py.test"):
            return TestFramework.PYTEST
        if head in ("python", "python3", "python3.11", "python3.12"):
            if len(rest) >= 2 and rest[0] == "-m":
                mod = rest[1]
                if mod in ("pytest", "py.test"):
                    return TestFramework.PYTEST
                if mod == "unittest":
                    return TestFramework.UNITTEST
                if mod == "tox":
                    return TestFramework.TOX
        if head == "tox":
            return TestFramework.TOX
        if head in ("npm", "yarn", "pnpm"):
            fw = {"npm": TestFramework.NPM, "yarn": TestFramework.YARN,
                  "pnpm": TestFramework.PNPM}[head]
            # npm test | npm run test | yarn test | pnpm test
            if rest[:1] == ["test"] or rest[:2] == ["run", "test"]:
                return fw
        if head == "cargo" and rest[:1] == ["test"]:
            return TestFramework.CARGO
        if head == "go" and rest[:1] == ["test"]:
            return TestFramework.GO
        if head == "mvn" and "test" in rest:
            return TestFramework.MAVEN
        if head in ("gradle", "./gradlew", "gradlew") and "test" in rest:
            return TestFramework.GRADLE
        if head == "make" and rest[:1] == ["test"]:
            return TestFramework.MAKE
    return TestFramework.NONE


# --------------------------------------------------------------------------
# Output parsing
# --------------------------------------------------------------------------

_PYTEST_COUNT = {
    "passed": re.compile(r"(\d+)\s+passed"),
    "failed": re.compile(r"(\d+)\s+failed"),
    "errored": re.compile(r"(\d+)\s+error(?:s)?\b"),
    "skipped": re.compile(r"(\d+)\s+skipped"),
}
_PYTEST_NO_TESTS = re.compile(r"no tests ran", re.IGNORECASE)
_PYTEST_COLLECTED_ZERO = re.compile(r"collected 0 items")

_UNITTEST_RAN = re.compile(r"^Ran (\d+) tests?", re.MULTILINE)
_UNITTEST_FAIL = re.compile(r"FAILED\s*\((.*?)\)")
_UNITTEST_OK = re.compile(r"^OK\b", re.MULTILINE)


def _last_int(pattern: re.Pattern[str], text: str) -> int | None:
    hits = pattern.findall(text)
    return int(hits[-1]) if hits else None


def parse_test_output(
    framework: TestFramework, stdout: str, stderr: str, exit_status: int | None
) -> TestOutcome:
    """Parse framework output into counts, or mark it explicitly unparseable."""
    if framework == TestFramework.NONE:
        return TestOutcome(TestStatus.NOT_RUN, framework, exit_status)

    text = f"{stdout}\n{stderr}"

    if framework == TestFramework.PYTEST:
        counts = {k: _last_int(p, text) for k, p in _PYTEST_COUNT.items()}
        if any(v is not None for v in counts.values()):
            return TestOutcome(
                TestStatus.RAN_PARSED, framework, exit_status,
                passed=counts["passed"], failed=counts["failed"],
                errored=counts["errored"], skipped=counts["skipped"],
            )
        if _PYTEST_NO_TESTS.search(text) or _PYTEST_COLLECTED_ZERO.search(text):
            # pytest ran but selected nothing: zero of everything is the truth,
            # and it is parsed, not unparseable.
            return TestOutcome(
                TestStatus.RAN_PARSED, framework, exit_status,
                passed=0, failed=0, errored=0, skipped=0,
            )
        return TestOutcome(TestStatus.RAN_UNPARSEABLE, framework, exit_status)

    if framework == TestFramework.UNITTEST:
        ran = _last_int(_UNITTEST_RAN, text)
        if ran is None:
            return TestOutcome(TestStatus.RAN_UNPARSEABLE, framework, exit_status)
        fail_blob = _UNITTEST_FAIL.search(text)
        failed = errored = 0
        if fail_blob:
            failed = _last_int(re.compile(r"failures=(\d+)"), fail_blob.group(1)) or 0
            errored = _last_int(re.compile(r"errors=(\d+)"), fail_blob.group(1)) or 0
        return TestOutcome(
            TestStatus.RAN_PARSED, framework, exit_status,
            passed=max(0, ran - failed - errored), failed=failed, errored=errored,
        )

    # Frameworks we recognise but do not yet parse: record honestly.
    return TestOutcome(TestStatus.RAN_UNPARSEABLE, framework, exit_status)


def detect_and_parse(command: str, stdout: str, stderr: str,
                     exit_status: int | None) -> TestOutcome:
    """Convenience wrapper: classify the command, then parse its output."""
    return parse_test_output(classify_test_command(command), stdout, stderr, exit_status)
