"""Container lifecycle + checkpoint/restore for agent sessions.

Implements Phase 0 Steps 9-10 and Stage 3 §7.2. The `docker commit` approach is
the baseline snapshot mechanism; Stage 3 records that Shepherd (arXiv:2605.10913)
and Crab (arXiv:2604.28138) report faster alternatives, and that
arXiv:2510.05556 warns container commits may be "too slow" at scale. Phase 0
only needs to establish that snapshot/restore is *possible*; throughput
optimisation is out of scope.

The Docker CLI is driven via subprocess rather than the SDK so that every
operation corresponds to a command that can be copied into the runbook and
re-run by hand.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from dataclasses import dataclass


class DockerError(RuntimeError):
    """A docker CLI invocation failed."""


@dataclass
class ExecResult:
    exit_status: int | None
    stdout: str
    stderr: str
    duration_ms: float


def _run(args: list[str], timeout: float = 600.0) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - timing dependent
        raise DockerError(f"timeout running {' '.join(args)}") from exc


def docker_available() -> bool:
    """True if the Docker daemon is reachable."""
    try:
        return _run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=60).returncode == 0
    except Exception:  # pragma: no cover
        return False


def image_exists_locally(image: str) -> bool:
    return _run(["docker", "image", "inspect", image], timeout=120).returncode == 0


def pull_image(image: str, timeout: float = 3600.0) -> None:
    proc = _run(["docker", "pull", image], timeout=timeout)
    if proc.returncode != 0:
        raise DockerError(f"docker pull {image} failed: {proc.stderr.strip()[:500]}")


def image_id(image: str) -> str:
    proc = _run(["docker", "image", "inspect", "--format", "{{.Id}}", image])
    if proc.returncode != 0:
        raise DockerError(f"cannot inspect image {image}: {proc.stderr.strip()[:300]}")
    return proc.stdout.strip()


def start_container(image: str, name: str | None = None, workdir: str | None = None) -> str:
    """Start a long-lived container running `sleep infinity`. Returns container id."""
    args = ["docker", "run", "-d", "--rm=false"]
    if name:
        args += ["--name", name]
    if workdir:
        args += ["-w", workdir]
    args += [image, "sleep", "infinity"]
    proc = _run(args)
    if proc.returncode != 0:
        raise DockerError(f"docker run failed: {proc.stderr.strip()[:500]}")
    return proc.stdout.strip()


#: Prefix applied to every agent command (Phase 0.5 defect D2).
#: Without `pipefail`, `pytest ... | tail -5` reports tail's status (0) and a
#: FAILING test run is recorded as a success. Real agents pipe constantly, so
#: this silently biases every failure-rate feature toward zero.
PIPEFAIL_PREFIX = "set -o pipefail; "


def exec_command(
    container_id: str, command: str, timeout: float = 300.0, pipefail: bool = True
) -> ExecResult:
    """Run a bash command inside the container, capturing exit status and streams.

    Args:
        pipefail: when True (default) the command runs under `set -o pipefail`
            so the status of the leftmost failing pipeline stage is preserved.
    """
    t0 = time.monotonic()
    wrapped = (PIPEFAIL_PREFIX + command) if pipefail else command
    try:
        proc = _run(
            ["docker", "exec", container_id, "bash", "-lc", wrapped], timeout=timeout
        )
    except DockerError:
        return ExecResult(None, "", "timeout", (time.monotonic() - t0) * 1000.0)
    return ExecResult(
        exit_status=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_ms=(time.monotonic() - t0) * 1000.0,
    )


def commit_snapshot(container_id: str, repository: str, tag: str | None = None) -> tuple[str, str]:
    """`docker commit` the container. Returns (image_ref, image_id)."""
    tag = tag or uuid.uuid4().hex[:12]
    ref = f"{repository}:{tag}"
    proc = _run(["docker", "commit", container_id, ref], timeout=1800)
    if proc.returncode != 0:
        raise DockerError(f"docker commit failed: {proc.stderr.strip()[:500]}")
    return ref, proc.stdout.strip()


def remove_container(container_id: str) -> None:
    _run(["docker", "rm", "-f", container_id], timeout=300)


def remove_image(image_ref: str) -> None:
    _run(["docker", "rmi", "-f", image_ref], timeout=600)


def container_diff_summary(container_id: str) -> int:
    """Number of filesystem changes vs the base image (`docker diff` line count)."""
    proc = _run(["docker", "diff", container_id], timeout=300)
    if proc.returncode != 0:
        return 0
    return len([ln for ln in proc.stdout.splitlines() if ln.strip()])
