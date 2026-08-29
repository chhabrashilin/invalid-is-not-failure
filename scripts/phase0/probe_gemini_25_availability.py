"""Predeclared Gemini 2.5 Flash availability gate for Phase 0.5.

No SWE-bench content is sent. Every physical request updates both the global
provider-attempt provenance and the independent Gemini-2.5-specific ceiling.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from instrumentation.provider_retry import (  # noqa: E402
    CallBudget,
    CompositeCallBudget,
    GlobalAttemptLedger,
    NonRetryableProviderError,
    ProviderRequestExecutor,
    ProviderTimeout,
    ProviderUnavailable,
)
from trajectory.schema import ProviderFinalStatus  # noqa: E402

from preflight_gemini import (  # noqa: E402
    ALT_ENV,
    CREDENTIAL_ENV,
    load_agent_dotenv,
    load_windows_user_scope_env,
)

MODEL = "gemini/gemini-2.5-flash"
FIXED_PROMPT = "Reply with OK."
MAX_LOGICAL_PROBES = 5
RETRY_DELAYS_S = (5.0, 15.0, 30.0)
PHYSICAL_REQUEST_TIMEOUT_S = 90.0
LOGICAL_PROBE_SPACING_S = 15.0
MODEL_SPECIFIC_MAX_PHYSICAL_CALLS = 100
MIN_REMAINING_FOR_TRAJECTORY = 70
HISTORICAL_GLOBAL_PROVIDER_ATTEMPTS = 12

GLOBAL_LEDGER_PATH = REPO_ROOT / "artifacts/phase0_5/global_provider_attempts.json"
MODEL_LEDGER_PATH = REPO_ROOT / "artifacts/phase0_5/gemini_2_5_flash_call_ledger.json"
OUTPUT_DIR = REPO_ROOT / "artifacts/phase0_5/availability"

OFFICIAL_SOURCES = [
    {
        "url": "https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash",
        "supports": [
            "model code gemini-2.5-flash",
            "stable version",
            "low-latency/high-volume/thinking/agentic workload description",
        ],
    },
    {
        "url": "https://ai.google.dev/gemini-api/docs/deprecations",
        "supports": ["stable release June 17 2025", "no shutdown date announced"],
    },
    {
        "url": "https://ai.google.dev/gemini-api/docs/pricing",
        "supports": ["Free Tier input free of charge", "Free Tier output free of charge"],
    },
]


def _usage(response) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    return {
        "input_tokens": int(
            getattr(usage, "prompt_tokens", 0)
            or getattr(usage, "input_tokens", 0)
            or 0
        ),
        "output_tokens": int(
            getattr(usage, "completion_tokens", 0)
            or getattr(usage, "output_tokens", 0)
            or 0
        ),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def _metrics(records, probe_usage, *, attempts_used: int, remaining: int) -> dict:
    successful = [r for r in records if r.provider_final_status == ProviderFinalStatus.SUCCESS]
    logical_attempted = max((r.logical_call_index for r in records), default=-1) + 1
    first_successes = sum(r.provider_attempt_count == 1 for r in successful)
    latencies = [
        r.successful_latency_ms
        for r in successful
        if r.successful_latency_ms is not None
    ]
    status_counts = {}
    for record in records:
        key = record.provider_final_status.value
        status_counts[key] = status_counts.get(key, 0) + 1
    input_tokens = sum(item["input_tokens"] for item in probe_usage)
    output_tokens = sum(item["output_tokens"] for item in probe_usage)
    total_tokens = sum(item["total_tokens"] for item in probe_usage)
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    other_statuses = {
        key: value
        for key, value in status_counts.items()
        if key
        not in {
            ProviderFinalStatus.SUCCESS.value,
            ProviderFinalStatus.PROVIDER_UNAVAILABLE.value,
            ProviderFinalStatus.PROVIDER_TIMEOUT.value,
            ProviderFinalStatus.RATE_LIMITED.value,
        }
    }
    return {
        "logical_probes": logical_attempted,
        "logical_probes_completed": len(records),
        "eventually_successful": len(successful),
        "first_attempt_successes": first_successes,
        "physical_attempts": attempts_used,
        "first_attempt_success_rate": (
            first_successes / logical_attempted if logical_attempted else 0.0
        ),
        "eventual_success_rate": (
            len(successful) / logical_attempted if logical_attempted else 0.0
        ),
        "provider_503_count": sum(r.provider_503_count for r in records),
        "provider_timeout_count": sum(r.provider_timeout_count for r in records),
        "provider_429_count": status_counts.get(ProviderFinalStatus.RATE_LIMITED.value, 0),
        "other_error_count": sum(other_statuses.values()),
        "other_error_types": other_statuses,
        "median_successful_latency_ms": statistics.median(latencies) if latencies else None,
        "maximum_successful_latency_ms": max(latencies) if latencies else None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "actual_spend_usd": 0.0,
        "model_specific_attempts_used": attempts_used,
        "model_specific_attempts_remaining": remaining,
    }


def _passes(metrics: dict) -> bool:
    forbidden = metrics["provider_429_count"] or metrics["other_error_count"]
    return bool(
        metrics["logical_probes_completed"] == MAX_LOGICAL_PROBES
        and metrics["eventually_successful"] >= 4
        and metrics["first_attempt_successes"] >= 3
        and not forbidden
        and metrics["provider_timeout_count"] <= 1
        and metrics["model_specific_attempts_remaining"] >= MIN_REMAINING_FOR_TRAJECTORY
    )


def main() -> int:
    started = datetime.now(timezone.utc)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"gemini-25-gate-{started.strftime('%Y%m%dT%H%M%S%fZ')}.json"

    load_agent_dotenv()
    adopted = load_windows_user_scope_env((CREDENTIAL_ENV, *ALT_ENV))
    present = [n for n in (CREDENTIAL_ENV, *ALT_ENV) if os.environ.get(n)]
    if not present:
        print("STOP: Gemini credential unavailable; zero requests made.")
        return 2

    import importlib.metadata as md
    import litellm

    resolved, provider = litellm.get_llm_provider(MODEL)[:2]
    if (resolved, provider) != ("gemini-2.5-flash", "gemini"):
        print(f"STOP: unexpected LiteLLM resolution {(resolved, provider)!r}")
        return 3

    global_ledger = GlobalAttemptLedger.from_ledger(
        GLOBAL_LEDGER_PATH, initial_used=HISTORICAL_GLOBAL_PROVIDER_ATTEMPTS
    )
    model_budget = CallBudget.from_ledger(
        MODEL_LEDGER_PATH,
        max_calls=MODEL_SPECIFIC_MAX_PHYSICAL_CALLS,
        initial_used=0,
        metadata={
            "model_id": MODEL,
            "constant": "PHASE_0_5_25_FLASH_MAX_PHYSICAL_CALLS",
            "actual_spend_ceiling_usd": 0.0,
        },
    )
    starting_model_attempts = model_budget.used
    budget = CompositeCallBudget(
        model_budget=model_budget,
        global_ledger=global_ledger,
        model_id=MODEL,
    )
    records = []
    probe_usage = []
    executor = ProviderRequestExecutor(
        call_budget=budget,
        records=records,
        retry_delays=RETRY_DELAYS_S,
        retry_timeouts=True,
        scope="gemini-2.5-availability-probe",
    )
    interrupted = False

    print(
        f"model={MODEL} timeout={PHYSICAL_REQUEST_TIMEOUT_S:.0f}s "
        f"retry_delays={RETRY_DELAYS_S} spacing={LOGICAL_PROBE_SPACING_S:.0f}s",
        flush=True,
    )

    try:
        for probe_index in range(MAX_LOGICAL_PROBES):
            if probe_index:
                time.sleep(LOGICAL_PROBE_SPACING_S)
            try:
                response, record = executor.call(
                    lambda: litellm.completion(
                        model=MODEL,
                        messages=[{"role": "user", "content": FIXED_PROMPT}],
                        max_tokens=5,
                        num_retries=0,
                        timeout=PHYSICAL_REQUEST_TIMEOUT_S,
                    )
                )
                probe_usage.append(_usage(response))
            except (ProviderUnavailable, ProviderTimeout, NonRetryableProviderError):
                record = records[-1]
                probe_usage.append({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

            attempts_used = model_budget.used - starting_model_attempts
            metrics = _metrics(
                records,
                probe_usage,
                attempts_used=attempts_used,
                remaining=model_budget.remaining,
            )
            print(
                f"probe {probe_index + 1}: {record.provider_final_status.value}; "
                f"attempts={record.provider_attempt_count} "
                f"503={record.provider_503_count} timeout={record.provider_timeout_count} "
                f"model_remaining={model_budget.remaining}",
                flush=True,
            )

            permanent_statuses = {
                ProviderFinalStatus.RATE_LIMITED,
                ProviderFinalStatus.AUTH_ERROR,
                ProviderFinalStatus.BILLING_ERROR,
                ProviderFinalStatus.INVALID_MODEL,
                ProviderFinalStatus.INVALID_REQUEST,
                ProviderFinalStatus.OTHER_ERROR,
            }
            if record.provider_final_status in permanent_statuses:
                break
            if metrics["provider_timeout_count"] > 1:
                break
            completed = len(records)
            remaining_probes = MAX_LOGICAL_PROBES - completed
            if metrics["eventually_successful"] + remaining_probes < 4:
                break
            if metrics["first_attempt_successes"] + remaining_probes < 3:
                break
            if model_budget.remaining < MIN_REMAINING_FOR_TRAJECTORY:
                break
    except KeyboardInterrupt:
        interrupted = True
    finally:
        attempts_used = model_budget.used - starting_model_attempts
        metrics = _metrics(
            records,
            probe_usage,
            attempts_used=attempts_used,
            remaining=model_budget.remaining,
        )
        decision = "PROCEED" if _passes(metrics) and not interrupted else "STOP"
        payload = {
            "kind": "phase0_5_gemini_2_5_flash_availability_gate",
            "model": MODEL,
            "fixed_prompt": FIXED_PROMPT,
            "started_at": started.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "retrieval_date": "2026-08-29",
            "official_sources": OFFICIAL_SOURCES,
            "litellm_version": md.version("litellm"),
            "litellm_resolution": {"model": resolved, "provider": provider},
            "credential_env_names_present": present,
            "windows_user_scope_name_adopted": adopted,
            "policy": {
                "logical_probe_limit": MAX_LOGICAL_PROBES,
                "retry_delays_s": RETRY_DELAYS_S,
                "physical_request_timeout_s": PHYSICAL_REQUEST_TIMEOUT_S,
                "logical_probe_spacing_s": LOGICAL_PROBE_SPACING_S,
                "retry_only": ["HTTP_503", "PROVIDER_TIMEOUT"],
                "hidden_litellm_retries": 0,
                "model_specific_physical_call_ceiling": MODEL_SPECIFIC_MAX_PHYSICAL_CALLS,
            },
            "metrics": metrics,
            "gate_decision": decision,
            "interrupted": interrupted,
            "records": [r.model_dump(mode="json") for r in records],
            "probe_token_usage": probe_usage,
            "global_provider_attempts": global_ledger.used,
            "interpretation": "infrastructure availability gate; not a model performance benchmark",
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2), flush=True)
        print(f"artifact={out}", flush=True)

    return 0 if decision == "PROCEED" else 10


if __name__ == "__main__":
    raise SystemExit(main())
