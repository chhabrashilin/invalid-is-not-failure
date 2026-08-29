"""Repository-scoped change measurement (Phase 0.5 defect D1).

Phase 0 measured "files changed" with `docker diff`, which counts the whole
container filesystem: conda packages, pytest caches, __pycache__, temp files.
On the real instance this produced `files_changed = 537` at step 3 when the
agent had edited nothing. That number is scientifically meaningless.

This module measures what the *agent* changed **inside the benchmark repository
working tree**, relative to the task's base commit, using git itself.

CONTAMINATION RULE (critical)
-----------------------------
The evaluator applies SWE-bench's `test_patch` before scoring. If agent-change
accounting ran after that, the evaluator's own edits would be attributed to the
agent. Therefore:

  * `measure_repo_changes` must be called BEFORE `apply_test_patch`, and
  * paths listed in `exclude_paths` (the instance's test files) are excluded
    from the counts regardless, as a second line of defence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from checkpoint.docker_env import exec_command

#: Path fragments that are never agent source changes.
DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    ".git/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".tox/",
    ".coverage",
    "*.pyc",
    "*.pyo",
    ".hypothesis/",
    "node_modules/",
    ".eggs/",
    "*.egg-info/",
)


@dataclass(frozen=True)
class RepoChanges:
    """Agent-attributable working-tree changes, relative to the base commit."""

    files_modified: int = 0
    files_added: int = 0
    files_deleted: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    measured: bool = True
    note: str = ""

    @property
    def files_changed_total(self) -> int:
        return self.files_modified + self.files_added + self.files_deleted

    def to_dict(self) -> dict:
        return asdict(self)


def _excluded(path: str, patterns: tuple[str, ...]) -> bool:
    for pat in patterns:
        if pat.startswith("*"):
            if path.endswith(pat.lstrip("*")):
                return True
        elif pat.endswith("/"):
            if path.startswith(pat) or f"/{pat}" in path:
                return True
        elif pat in path:
            return True
    return False


def parse_porcelain(text: str, exclude: tuple[str, ...],
                    exclude_paths: tuple[str, ...] = ()) -> tuple[int, int, int]:
    """Parse `git status --porcelain` into (modified, added, deleted).

    Pure function so it can be unit-tested without a container.
    Untracked entries ("??") count as added.
    """
    modified = added = deleted = 0
    for line in text.splitlines():
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:].strip().strip('"')
        if " -> " in path:  # rename: attribute to the destination
            path = path.split(" -> ", 1)[1]
        if _excluded(path, exclude) or path in exclude_paths:
            continue
        if "R" in code:
            # A rename is counted as a modification: the content existed before
            # and exists after. Counting it as add+delete would double-count.
            modified += 1
        elif code == "??" or "A" in code:
            added += 1
        elif "D" in code:
            deleted += 1
        else:
            modified += 1
    return modified, added, deleted


def parse_numstat(text: str, exclude: tuple[str, ...],
                  exclude_paths: tuple[str, ...] = ()) -> tuple[int, int]:
    """Parse `git diff --numstat` into (lines_added, lines_deleted).

    Binary files report '-' for both counts and are skipped.
    """
    add = dele = 0
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a, d, path = parts[0], parts[1], parts[2].strip()
        if _excluded(path, exclude) or path in exclude_paths:
            continue
        if a == "-" or d == "-":
            continue
        try:
            add += int(a)
            dele += int(d)
        except ValueError:
            continue
    return add, dele


def measure_repo_changes(
    container_id: str,
    workdir: str,
    base_commit: str,
    exclude_paths: tuple[str, ...] = (),
    exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUDE_PATTERNS,
    timeout: float = 120.0,
) -> RepoChanges:
    """Measure agent-attributable repository changes inside the container.

    MUST be called before the evaluator applies `test_patch`.

    Args:
        exclude_paths: instance test files, excluded so the evaluator's patch
            can never be attributed to the agent.
    """
    status = exec_command(
        container_id, f"cd {workdir} && git status --porcelain", timeout=timeout
    )
    if status.exit_status != 0:
        return RepoChanges(
            measured=False,
            note=f"git status failed (exit={status.exit_status}): {status.stderr[:200]}",
        )

    numstat = exec_command(
        container_id,
        f"cd {workdir} && git diff --numstat {base_commit}",
        timeout=timeout,
    )
    untracked_numstat = exec_command(
        container_id,
        # include untracked files in line counts via an intent-to-add dry run
        f"cd {workdir} && git add -An . >/dev/null 2>&1; git diff --numstat {base_commit}",
        timeout=timeout,
    )

    modified, added, deleted = parse_porcelain(
        status.stdout, exclude_patterns, exclude_paths
    )
    source = untracked_numstat if untracked_numstat.exit_status == 0 else numstat
    lines_added, lines_deleted = parse_numstat(
        source.stdout, exclude_patterns, exclude_paths
    )
    return RepoChanges(
        files_modified=modified,
        files_added=added,
        files_deleted=deleted,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        measured=True,
    )
