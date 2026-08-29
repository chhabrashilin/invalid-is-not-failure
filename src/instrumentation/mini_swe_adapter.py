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
from minisweagent.exceptions import FormatError
from minisweagent.models.litellm_model import LitellmModel

from evaluation.test_detect import detect_and_parse
from instrumentation.provider_retry import (
    CallBudget,
    CallCapExceeded,
    CompositeCallBudget,
    NonRetryableProviderError,
    ProviderRequestExecutor,
    ProviderTimeout,
    ProviderUnavailable,
)
from instrumentation.recorder import TrajectoryRecorder, estimate_tokens
from instrumentation.repo_state import RepoChanges, measure_repo_changes
from trajectory.schema import ActionType, ProviderCallRecord, StepRecord

MINI_SWE_AGENT_PINNED_VERSION = "2.4.6"


class SpendCapExceeded(RuntimeError):
    """Raised when the programmatic hard spend cap is reached."""


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
    #: Shared physical API-attempt ledger. One object is passed to the parent
    #: run and every fork so retries consume the same global ceiling.
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
        # Real provider models reserve inside the request layer so every
        # physical retry is counted. Deterministic/test models have one physical
        # attempt per logical query and are reserved here.
        if (
            self.instr.call_budget is not None
            and not getattr(self.model, "accounts_physical_attempts", False)
        ):
            self.instr.call_budget.check_and_reserve("agent-nonprovider")
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


class Phase05GeminiModel(LitellmModel):
    """mini-SWE-agent model with 503-only retry below trajectory semantics.

    Upstream 2.4.6 retries nearly every non-auth exception. We override the
    single physical request hook and make terminal wrappers abort upstream's
    outer retry loop. Prompt preparation, action parsing, cost accounting, and
    message construction remain the pinned upstream implementation.
    """

    accounts_physical_attempts = True
    abort_exceptions = [
        *LitellmModel.abort_exceptions,
        ProviderUnavailable,
        ProviderTimeout,
        NonRetryableProviderError,
        CallCapExceeded,
    ]

    def __init__(
        self,
        *,
        call_budget: CallBudget | CompositeCallBudget,
        provider_records: list[ProviderCallRecord] | None = None,
        provider_sleep_fn=time.sleep,
        provider_scope: str = "trajectory",
        provider_retry_delays: tuple[float, ...] = (5.0, 15.0, 30.0),
        provider_request_timeout_s: float = 90.0,
        provider_retry_timeouts: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.provider_executor = ProviderRequestExecutor(
            call_budget=call_budget,
            records=provider_records,
            sleep_fn=provider_sleep_fn,
            scope=provider_scope,
            retry_delays=provider_retry_delays,
            retry_timeouts=provider_retry_timeouts,
        )
        self.provider_request_timeout_s = provider_request_timeout_s
        self._last_provider_record: ProviderCallRecord | None = None

    def _query(self, messages: list[dict[str, str]], **kwargs):
        # Disable LiteLLM's own retry mechanism. This executor is the sole retry
        # owner, otherwise hidden SDK retries would evade physical accounting.
        request_kwargs = {
            **kwargs,
            "num_retries": 0,
            "timeout": self.provider_request_timeout_s,
        }
        response, record = self.provider_executor.call(
            lambda: super(Phase05GeminiModel, self)._query(messages, **request_kwargs)
        )
        self._last_provider_record = record
        return response

    def query(self, messages: list[dict[str, str]], **kwargs) -> dict:
        try:
            message = super().query(messages, **kwargs)
        except FormatError as exc:
            if self.provider_executor.records:
                exc.messages[0].setdefault("extra", {})["provider"] = (
                    self.provider_executor.records[-1].model_dump(mode="json")
                )
            raise
        if self._last_provider_record is not None:
            message.setdefault("extra", {})["provider"] = (
                self._last_provider_record.model_dump(mode="json")
            )
        return message
