"""Immutable raw-trajectory storage (Stage 3 §13, Phase 0 Step 14).

Rules enforced here:
  * raw artifacts are written once and then made read-only;
  * a manifest.json records SHA-256 of every raw artifact;
  * `verify_manifest` re-checks hashes so tampering is detectable;
  * loading a prefix NEVER reads outcome.json or evaluation.json.

If logging is wrong, the correct response is to discard the run and re-run after
fixing the code -- never to edit a raw file.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel

from trajectory.schema import SessionMeta, StepRecord, TrajectoryPrefix

RAW_STEPS = "steps.jsonl"
RAW_SESSION = "session.json"
RAW_OUTCOME = "outcome.json"          # Class C -- never read by prefix loading
RAW_EVALUATION = "evaluation.json"    # Class C -- never read by prefix loading
MANIFEST = "manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _freeze(path: Path) -> None:
    """Make a file read-only. Best-effort: raises nothing on exotic filesystems."""
    try:
        mode = path.stat().st_mode
        path.chmod(mode & ~stat.S_IWRITE & ~stat.S_IWGRP & ~stat.S_IWOTH)
    except OSError:  # pragma: no cover - platform dependent
        pass


def _thaw(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | stat.S_IWRITE)
    except OSError:  # pragma: no cover
        pass


class RawTrajectoryWriter:
    """Append-only writer for one session's raw records.

    Use as a context manager. On close, artifacts are hashed, a manifest is
    written, and the artifacts are marked read-only.
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        if self.run_dir.exists() and any(self.run_dir.iterdir()):
            raise FileExistsError(
                f"{self.run_dir} already contains data; raw runs are immutable. "
                "Use a new run_id instead of overwriting."
            )
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._steps_fh = None
        self._n_steps = 0
        self._closed = False

    def __enter__(self) -> "RawTrajectoryWriter":
        self._steps_fh = (self.run_dir / RAW_STEPS).open("a", encoding="utf-8")
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def write_session(self, session: SessionMeta) -> None:
        self._write_json(RAW_SESSION, session)

    def write_step(self, step: StepRecord) -> None:
        assert self._steps_fh is not None, "writer not opened"
        if step.step_id != self._n_steps:
            raise ValueError(
                f"step_id {step.step_id} out of order; expected {self._n_steps}"
            )
        self._steps_fh.write(step.model_dump_json() + "\n")
        self._steps_fh.flush()
        self._n_steps += 1

    def write_outcome(self, outcome: BaseModel) -> None:
        """Class-C record. Written to a SEPARATE file that prefix loading ignores."""
        self._write_json(RAW_OUTCOME, outcome)

    def write_evaluation(self, evaluation: BaseModel) -> None:
        """Class-C record from the external evaluator."""
        self._write_json(RAW_EVALUATION, evaluation)

    def _write_json(self, name: str, model: BaseModel) -> None:
        path = self.run_dir / name
        if path.exists():
            raise FileExistsError(f"{path} already written; raw artifacts are immutable")
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")

    def close(self) -> dict[str, str]:
        if self._closed:
            return {}
        if self._steps_fh is not None:
            self._steps_fh.close()
            self._steps_fh = None
        manifest = write_manifest(self.run_dir)
        self._closed = True
        return manifest


def write_manifest(run_dir: Path) -> dict[str, str]:
    """Hash every raw artifact, write manifest.json, then freeze the artifacts."""
    run_dir = Path(run_dir)
    hashes: dict[str, str] = {}
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != MANIFEST:
            hashes[path.name] = sha256_file(path)
    (run_dir / MANIFEST).write_text(
        json.dumps({"artifacts": hashes}, indent=2, sort_keys=True), encoding="utf-8"
    )
    for name in hashes:
        _freeze(run_dir / name)
    _freeze(run_dir / MANIFEST)
    return hashes


def verify_manifest(run_dir: Path) -> tuple[bool, list[str]]:
    """Re-hash artifacts and compare against the manifest.

    Returns:
        (ok, problems). `problems` lists mismatched or missing artifact names.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / MANIFEST
    if not manifest_path.exists():
        return False, [f"{MANIFEST} missing"]
    recorded = json.loads(manifest_path.read_text(encoding="utf-8"))["artifacts"]
    problems: list[str] = []
    for name, expected in recorded.items():
        path = run_dir / name
        if not path.exists():
            problems.append(f"{name}: missing")
        elif sha256_file(path) != expected:
            problems.append(f"{name}: hash mismatch")
    return (not problems), problems


def unfreeze_run(run_dir: Path) -> None:
    """Restore write permission. For test cleanup ONLY -- never in a pipeline."""
    for path in Path(run_dir).iterdir():
        if path.is_file():
            _thaw(path)


# --------------------------------------------------------------------------
# Loading -- deliberately incapable of reading Class-C files
# --------------------------------------------------------------------------


def load_session(run_dir: Path) -> SessionMeta:
    return SessionMeta.model_validate_json(
        (Path(run_dir) / RAW_SESSION).read_text(encoding="utf-8")
    )


def _iter_step_lines(run_dir: Path, limit: int | None) -> Iterable[str]:
    with (Path(run_dir) / RAW_STEPS).open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                return
            if line.strip():
                yield line


def load_prefix(run_dir: Path, k: int) -> TrajectoryPrefix:
    """Load the first `k` steps of a run as a prefix view.

    Reads at most `k` lines of steps.jsonl and never opens outcome.json or
    evaluation.json. Future steps are not read into memory at all.
    """
    session = load_session(run_dir)
    steps = [StepRecord.model_validate_json(line) for line in _iter_step_lines(run_dir, k)]
    if len(steps) < k:
        raise IndexError(f"run has only {len(steps)} steps; cannot form prefix of {k}")
    return TrajectoryPrefix(session=session, steps=steps, k=k)


def load_all_steps(run_dir: Path) -> list[StepRecord]:
    """Analysis-only: load every step. Not for online feature extraction."""
    return [StepRecord.model_validate_json(line) for line in _iter_step_lines(run_dir, None)]


def load_outcome_raw(run_dir: Path) -> dict[str, Any]:
    """Analysis-only Class-C loader. Never call from feature code."""
    return json.loads((Path(run_dir) / RAW_OUTCOME).read_text(encoding="utf-8"))
