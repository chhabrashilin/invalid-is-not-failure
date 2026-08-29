"""mini-swe-agent 2.4.6 instrumentation adapter (Phase 0.5 defect D4).

INTEGRATION APPROACH
--------------------
mini-swe-agent is NOT forked. `DefaultAgent.query()` carries the upstream
docstring "Query the model and return model messages. **Override to add hooks.**"
-- so subclassing and overriding `query` / `execute_actions` is the sanctioned
extension point. Everything else (prompt templates, action parsing, limits,
message handling, `run()` control flow) remains upstream behaviour.

WHAT IS INSTRUMENTED
  * `query()`        -> model call: latency, token usage, cost, message content
  * `execute_actions()` -> tool result: exit status, output, repo changes, tests

WHAT IS UNCHANGED
  * prompt templates and rendering
  * action parsing / FormatError handling
  * step / cost / wall-time limits (we *tighten* cost_limit, never loosen it)
  * message list construction and `run()` loop

UPSTREAM VERSION PINNED: mini-swe-agent == 2.4.6 (see pyproject dependency-group
`agent`). If that version changes, re-verify the two hook signatures.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from minisweagent.agents.default import DefaultAgent

from evaluation.test_detect import detect_and_parse
from instrumentation.recorder import TrajectoryRecorder, estimate_tokens
from instrumentation.repo_state import RepoChanges, measure_repo_changes
from trajectory.schema import ActionType, StepRecord

MINI_SWE_AGENT_PINNED_VERSION = "2.4.6"


class SpendCapExceeded(RuntimeError):
    """Raised when the programmatic hard spend cap is reached."""


class CallCapExceeded(RuntimeError):
    """Raised when the Phase 0.5 model-call ceiling is reached.

    On a FREE TIER the dollar cap is the wrong instrument: litellm computes a
    non-zero cost for `gemini/gemini-3.7-flash` from its paid-tier price map
    ($0.75/$3.75 per 1M as of litellm 1.98.0), so a literal `cost_limit=0.00`
    would abort at the first call. The binding, honest control for a $0
    authorisation is therefore a hard ceiling on the NUMBER OF MODEL CALLS,
    shared across the parent trajectory and every fork.
    """


@dataclass
class CallBudget:
    """Hard ceiling on total model calls across every session in a milestone."""

    max_calls: int
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.used)

    def check_and_reserve(self) -> None:
        if self.used >= self.max_calls:
            raise CallCapExceeded(
                f"Phase 0.5 model-call ceiling reached: {self.used}/{self.max_calls} "
                "calls used across all sessions; refusing further model calls"
            )
        self.used += 1


@dataclass
class InstrumentationContext:
    """Everything the adapter needs that upstream does not provide."""

    recorder: TrajectoryRecorder
    container_id: str | None = None
    workdir: str = "/testbed"
    base_commit: str | None = None
    exclude_paths: tuple[str, ...] = ()
    track_repo_changes: bool = True
    #: Hard USD ceiling. Enforced programmatically, never by human attention.
    #: Leave at 0.0 on a free tier and rely on `call_budget` instead (see
    #: CallCapExceeded for why a literal $0 cost cap is unusable).
    spend_cap_usd: float = 0.0
    #: Shared model-call ledger. One object is passed to the parent run and to
    #: every fork so the ceiling spans the whole Phase 0.5 milestone.
    call_budget: "CallBudget | None" = None
    on_step: Any = None  # optional callback(StepRecord)
    steps: list[StepRecord] = field(default_factory=list)


class InstrumentedAgent(DefaultAgent):
    """DefaultAgent with measurement hooks and a hard spend cap.

    The spend cap is enforced in two independent places:
      1. upstream's own ``config.cost_limit`` (set from ``spend_cap_usd``), and
      2. an explicit check in :meth:`query` that raises before the call is made.

    Belt and braces is deliberate: an unattended harness must not be able to
    overspend because one mechanism was misconfigured.
    """

    def __init__(self, model, env, *, instrumentation: InstrumentationContext, **kwargs):
        # Tighten (never loosen) upstream's cost limit to our cap.
        if instrumentation.spend_cap_usd > 0:
            existing = kwargs.get("cost_limit", 0.0) or 0.0
            kwargs["cost_limit"] = (
                min(existing, instrumentation.spend_cap_usd)
                if existing > 0
                else instrumentation.spend_cap_usd
            )
        super().__init__(model, env, **kwargs)
        self.instr = instrumentation
        self._pending: dict | None = None
        self._last_query_ms = 0.0

    # ---- hook 1: model call ------------------------------------------------
    def query(self) -> dict:
        cap = self.instr.spend_cap_usd
        if cap > 0 and self.cost >= cap:
            raise SpendCapExceeded(
                f"cumulative cost {self.cost:.4f} USD reached the Phase 0.5 cap "
                f"of {cap:.4f} USD; refusing further model calls"
            )
        if self.instr.call_budget is not None:
            self.instr.call_budget.check_and_reserve()
        t0 = time.monotonic()
        message = super().query()
        self._last_query_ms = (time.monotonic() - t0) * 1000.0
        self._pending = message
        return message

    # ---- hook 2: tool execution -------------------------------------------
    def execute_actions(self, message: dict) -> list[dict]:
        outputs = super().execute_actions(message)
        try:
            self._record(message, outputs)
        except Exception as exc:  # never let instrumentation break the agent
            self.instr.recorder  # noqa: B018 - keep attribute access explicit
            print(f"[instrumentation] failed to record step: {exc!r}")
        return outputs

    # ---- recording ---------------------------------------------------------
    def _record(self, message: dict, outputs: list[dict]) -> None:
        extra = message.get("extra", {}) or {}
        actions = extra.get("actions", []) or []
        command = (actions[0].get("command", "") if actions else "") or ""

        out = outputs[0] if outputs else {}
        content = out.get("content", "") if isinstance(out, dict) else str(out)
        exit_status = None
        if isinstance(out, dict):
            exit_status = out.get("returncode", out.get("exit_status"))
        if exit_status is None:
            exit_status = (out.get("extra", {}) or {}).get("returncode") if isinstance(out, dict) else None

        usage = extra.get("usage", {}) or {}
        prompt_tokens = int(
            usage.get("prompt_tokens")
            or usage.get("input_tokens")
            or estimate_tokens("".join(str(m.get("content", "")) for m in self.messages))
        )
        completion_tokens = int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or estimate_tokens(str(message.get("content", "")))
        )
        context_tokens = estimate_tokens(
            "".join(str(m.get("content", "")) for m in self.messages)
        )

        repo_changes: RepoChanges | None = None
        if (
            self.instr.track_repo_changes
            and self.instr.container_id
            and self.instr.base_commit
        ):
            repo_changes = measure_repo_changes(
                self.instr.container_id,
                self.instr.workdir,
                self.instr.base_commit,
                exclude_paths=self.instr.exclude_paths,
            )

        test_outcome = detect_and_parse(command, content, "", exit_status)

        step = self.instr.recorder.record_step(
            action_type=ActionType.BASH if command else ActionType.NOOP,
            command=command,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            context_length_tokens=context_tokens,
            stdout=content,
            stderr="",
            exit_status=exit_status,
            model_latency_ms=self._last_query_ms,
            estimated_cost_usd=float(extra.get("cost", 0.0) or 0.0),
            test_outcome=test_outcome,
            repo_changes=repo_changes,
        )
        self.instr.steps.append(step)
        if self.instr.on_step:
            self.instr.on_step(step)


def agent_library_version() -> str:
    """Installed mini-swe-agent version, for provenance in SessionMeta."""
    import importlib.metadata as md

    return md.version("mini-swe-agent")
