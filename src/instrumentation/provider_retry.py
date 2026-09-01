"""Provider-request retry and accounting below trajectory semantics.

Phase 0.5 treats a Gemini HTTP 503 as an infrastructure event, not an agent
action or reasoning failure. One logical model call may make several physical
API attempts, but only a successful response is returned to trajectory code.

Only HTTP 503 is retried. In particular, 429, authentication/authorization,
billing, invalid-model, and unknown errors surface immediately.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from trajectory.schema import ProviderCallRecord, ProviderFinalStatus

T = TypeVar("T")


class CallCapExceeded(RuntimeError):
    """Raised before a physical request would exceed the global ceiling."""


class ProviderUnavailable(RuntimeError):
    """All permitted physical attempts for one logical call returned 503."""

    def __init__(self, record: ProviderCallRecord):
        super().__init__(
            "Gemini remained unavailable after "
            f"{record.provider_attempt_count} physical API attempts"
        )
        self.record = record


class ProviderTimeout(RuntimeError):
    """All permitted attempts ended with a provider request timeout."""

    def __init__(self, record: ProviderCallRecord):
        super().__init__(
            "Gemini request timed out after "
            f"{record.provider_attempt_count} physical API attempts"
        )
        self.record = record


class NonRetryableProviderError(RuntimeError):
    """A provider error that the Phase 0.5 protocol forbids retrying."""

    def __init__(self, record: ProviderCallRecord):
        super().__init__(
            f"non-retryable provider error: {record.provider_final_status.value} "
            f"({record.error_type or 'unknown'})"
        )
        self.record = record


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


#: Ordered redaction rules applied to any provider text before it is persisted.
#: Each entry is (pattern, replacement); the credential is dropped, the label
#: that identifies it is kept so the message stays readable.
_SECRET_PATTERNS = (
    # Authorization header: redact the whole value, scheme included.
    (re.compile(r"(?i)(authorization\s*[=:]\s*).*"), r"\g<1><REDACTED>"),
    (re.compile(r"(?i)(bearer\s+)\S+"), r"\g<1><REDACTED>"),
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)\S+"), r"\g<1><REDACTED>"),
    # `?key=<API_KEY>` query parameter used by the Gemini Developer API.
    (re.compile(r"(?i)(key=)[A-Za-z0-9_\-]{8,}"), r"\g<1><REDACTED>"),
    # Bare Google API key, wherever it appears.
    (re.compile(r"AIza[A-Za-z0-9_\-]{10,}"), "<REDACTED>"),
)

#: Maximum persisted length of a provider error body.
PROVIDER_MESSAGE_HEAD_LIMIT = 1200


def redact_provider_message(text: str, *, limit: int = PROVIDER_MESSAGE_HEAD_LIMIT) -> str:
    """Bounded, secret-free head of a provider error body.

    Provider errors echo the request URL, which on the Gemini Developer API
    carries `?key=<API_KEY>`. Persisting the body verbatim would write the
    credential into the raw trajectory, so every known secret shape is stripped
    before truncation.
    """
    cleaned = text
    for pattern, replacement in _SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned[:limit]


def provider_status_code(exc: BaseException) -> int | None:
    """Best-effort status extraction without depending on one SDK exception type."""
    for attr in ("status_code", "http_status", "code"):
        value = getattr(exc, attr, None)
        try:
            if value is not None and int(value) in range(100, 600):
                return int(value)
        except (TypeError, ValueError):
            pass
    match = re.search(r"(?<!\d)(400|401|402|403|404|408|429|503)(?!\d)", str(exc))
    return int(match.group(1)) if match else None


def classify_provider_error(exc: BaseException) -> tuple[ProviderFinalStatus, int | None]:
    """Classify an exception for retry/validity decisions; never include secrets."""
    code = provider_status_code(exc)
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if (
        isinstance(exc, TimeoutError)
        or code == 408
        or "timeout" in name
        or "timed out" in message
    ):
        return ProviderFinalStatus.PROVIDER_TIMEOUT, code or 408
    if code == 503 or "service_unavailable" in message:
        return ProviderFinalStatus.PROVIDER_UNAVAILABLE, 503
    if code == 429 or "ratelimit" in name or "rate limit" in message:
        return ProviderFinalStatus.RATE_LIMITED, 429
    if code in (401, 403) or "authentication" in name or "permissiondenied" in name:
        return ProviderFinalStatus.AUTH_ERROR, code
    if code == 402 or "billing" in message or "payment required" in message:
        return ProviderFinalStatus.BILLING_ERROR, code
    if code == 404 or "notfound" in name or "invalid model" in message:
        return ProviderFinalStatus.INVALID_MODEL, code
    if code == 400 or "badrequest" in name or "invalid request" in message:
        return ProviderFinalStatus.INVALID_REQUEST, code
    return ProviderFinalStatus.OTHER_ERROR, code


@dataclass
class CallBudget:
    """Global ceiling on physical API attempts, optionally persisted to disk."""

    max_calls: int
    used: int = 0
    ledger_path: Path | None = None
    prior_attempts_at_continuation: int | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.used)

    @classmethod
    def from_ledger(
        cls,
        path: Path,
        *,
        max_calls: int,
        initial_used: int,
        metadata: dict[str, Any] | None = None,
    ) -> "CallBudget":
        """Load a ledger, or create it once with the explicitly audited prior use."""
        path = Path(path)
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            recorded_max = int(payload["max_physical_api_attempts"])
            if recorded_max != max_calls:
                raise ValueError(
                    f"ledger ceiling changed from {recorded_max} to {max_calls}"
                )
            return cls(
                max_calls=max_calls,
                used=int(payload["physical_api_attempts_used"]),
                ledger_path=path,
                prior_attempts_at_continuation=int(
                    payload.get("prior_attempts_at_continuation", initial_used)
                ),
                events=list(payload.get("events", [])),
                metadata=dict(payload.get("metadata", metadata or {})),
            )
        budget = cls(
            max_calls=max_calls,
            used=initial_used,
            ledger_path=path,
            prior_attempts_at_continuation=initial_used,
            metadata=dict(metadata or {}),
        )
        budget._persist()
        return budget

    def _persist(self) -> None:
        if self.ledger_path is None:
            return
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "phase": "0.5",
            "accounting_unit": "physical_api_attempt",
            "max_physical_api_attempts": self.max_calls,
            "physical_api_attempts_used": self.used,
            "physical_api_attempts_remaining": self.remaining,
            "prior_attempts_at_continuation": self.prior_attempts_at_continuation,
            "events": self.events,
            "metadata": self.metadata,
            "updated_at": _utcnow(),
        }
        tmp = self.ledger_path.with_suffix(self.ledger_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.ledger_path)

    def check_and_reserve(self, scope: str = "unspecified") -> None:
        """Atomically reserve one physical request and persist before sending it."""
        with self._lock:
            if self.used >= self.max_calls:
                raise CallCapExceeded(
                    f"Phase 0.5 physical API-attempt ceiling reached: "
                    f"{self.used}/{self.max_calls}; refusing another request"
                )
            self.used += 1
            self.events.append({"ordinal": self.used, "scope": scope, "ts": _utcnow()})
            self._persist()


@dataclass
class GlobalAttemptLedger:
    """Uncapped provenance counter spanning every Phase 0.5 provider/model."""

    used: int
    ledger_path: Path
    events: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @classmethod
    def from_ledger(cls, path: Path, *, initial_used: int) -> "GlobalAttemptLedger":
        path = Path(path)
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                used=int(payload["global_provider_attempts"]),
                ledger_path=path,
                events=list(payload.get("events", [])),
            )
        ledger = cls(used=initial_used, ledger_path=path)
        ledger._persist()
        return ledger

    def _persist(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "phase": "0.5",
            "accounting_unit": "physical_api_attempt",
            "global_provider_attempts": self.used,
            "historical_attempts_before_gemini_2_5_flash": 12,
            "events": self.events,
            "updated_at": _utcnow(),
        }
        tmp = self.ledger_path.with_suffix(self.ledger_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.ledger_path)

    def record_attempt(self, *, scope: str, model_id: str) -> None:
        with self._lock:
            self.used += 1
            self.events.append(
                {
                    "ordinal": self.used,
                    "scope": scope,
                    "model_id": model_id,
                    "ts": _utcnow(),
                }
            )
            self._persist()


@dataclass
class CompositeCallBudget:
    """Reserve one attempt in both a model ceiling and the global provenance."""

    model_budget: CallBudget
    global_ledger: GlobalAttemptLedger
    model_id: str

    @property
    def max_calls(self) -> int:
        return self.model_budget.max_calls

    @property
    def used(self) -> int:
        return self.model_budget.used

    @property
    def remaining(self) -> int:
        return self.model_budget.remaining

    def check_and_reserve(self, scope: str = "unspecified") -> None:
        self.model_budget.check_and_reserve(scope)
        self.global_ledger.record_attempt(scope=scope, model_id=self.model_id)


class ProviderRequestExecutor:
    """Execute logical requests under the exact Phase 0.5 transient policy."""

    def __init__(
        self,
        *,
        call_budget: CallBudget | CompositeCallBudget,
        records: list[ProviderCallRecord] | None = None,
        retry_delays: tuple[float, ...] = (15.0, 30.0, 60.0),
        sleep_fn: Callable[[float], None] = time.sleep,
        scope: str = "trajectory",
        retry_timeouts: bool = False,
    ) -> None:
        self.call_budget = call_budget
        self.records = records if records is not None else []
        self.retry_delays = retry_delays
        self.sleep_fn = sleep_fn
        self.scope = scope
        self.retry_timeouts = retry_timeouts
        self.logical_calls = 0

    def call(self, request: Callable[[], T]) -> tuple[T, ProviderCallRecord]:
        """Return one successful response or raise a classified terminal error."""
        logical_index = self.logical_calls
        self.logical_calls += 1
        started_ts = _utcnow()
        t0 = time.monotonic()
        attempts = 0
        n_503 = 0
        n_timeout = 0
        retry_delay = 0.0

        for attempt_index in range(len(self.retry_delays) + 1):
            try:
                self.call_budget.check_and_reserve(self.scope)
            except CallCapExceeded:
                record = ProviderCallRecord(
                    logical_call_index=logical_index,
                    provider_attempt_count=attempts,
                    provider_503_count=n_503,
                    provider_timeout_count=n_timeout,
                    provider_retry_delay_total=retry_delay,
                    provider_final_status=ProviderFinalStatus.CALL_CAP_EXCEEDED,
                    started_ts=started_ts,
                    finished_ts=_utcnow(),
                    total_latency_ms=(time.monotonic() - t0) * 1000.0,
                    error_type="CallCapExceeded",
                )
                self.records.append(record)
                raise

            attempts += 1
            physical_t0 = time.monotonic()
            try:
                response = request()
            except Exception as exc:
                status, status_code = classify_provider_error(exc)
                if status == ProviderFinalStatus.PROVIDER_UNAVAILABLE:
                    n_503 += 1
                elif status == ProviderFinalStatus.PROVIDER_TIMEOUT:
                    n_timeout += 1
                retryable = status == ProviderFinalStatus.PROVIDER_UNAVAILABLE or (
                    status == ProviderFinalStatus.PROVIDER_TIMEOUT and self.retry_timeouts
                )
                if retryable:
                    if attempt_index < len(self.retry_delays):
                        delay = self.retry_delays[attempt_index]
                        retry_delay += delay
                        self.sleep_fn(delay)
                        continue
                    record = ProviderCallRecord(
                        logical_call_index=logical_index,
                        provider_attempt_count=attempts,
                        provider_503_count=n_503,
                        provider_timeout_count=n_timeout,
                        provider_retry_delay_total=retry_delay,
                        provider_final_status=status,
                        started_ts=started_ts,
                        finished_ts=_utcnow(),
                        total_latency_ms=(time.monotonic() - t0) * 1000.0,
                        status_code=status_code,
                        error_type=type(exc).__name__,
                        error_message_head=redact_provider_message(str(exc)),
                    )
                    self.records.append(record)
                    if status == ProviderFinalStatus.PROVIDER_TIMEOUT:
                        raise ProviderTimeout(record) from exc
                    raise ProviderUnavailable(record) from exc

                record = ProviderCallRecord(
                    logical_call_index=logical_index,
                    provider_attempt_count=attempts,
                    provider_503_count=n_503,
                    provider_timeout_count=n_timeout,
                    provider_retry_delay_total=retry_delay,
                    provider_final_status=status,
                    started_ts=started_ts,
                    finished_ts=_utcnow(),
                    total_latency_ms=(time.monotonic() - t0) * 1000.0,
                    status_code=status_code,
                    error_type=type(exc).__name__,
                    error_message_head=redact_provider_message(str(exc)),
                )
                self.records.append(record)
                raise NonRetryableProviderError(record) from exc

            record = ProviderCallRecord(
                logical_call_index=logical_index,
                provider_attempt_count=attempts,
                provider_503_count=n_503,
                provider_timeout_count=n_timeout,
                provider_retry_delay_total=retry_delay,
                provider_final_status=ProviderFinalStatus.SUCCESS,
                started_ts=started_ts,
                finished_ts=_utcnow(),
                successful_latency_ms=(time.monotonic() - physical_t0) * 1000.0,
                total_latency_ms=(time.monotonic() - t0) * 1000.0,
                status_code=200,
            )
            self.records.append(record)
            return response, record

        raise AssertionError("unreachable provider retry state")
