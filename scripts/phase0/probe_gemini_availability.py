"""Phase 0.5 availability gate for gemini/gemini-3.7-flash.

This sends only the fixed prompt ``Reply with OK.``. It starts from the audited
five physical attempts already consumed before commit 0be22fe and persists every
new physical request in the global 100-attempt ledger before sending it.
"""

from __future__ import annotations

import argparse
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
    NonRetryableProviderError,
    ProviderRequestExecutor,
    ProviderUnavailable,
)
from trajectory.schema import ProviderFinalStatus  # noqa: E402

from preflight_gemini import (  # noqa: E402
    ALT_ENV,
    CREDENTIAL_ENV,
    MODEL,
    load_agent_dotenv,
    load_windows_user_scope_env,
)

LEDGER = REPO_ROOT / "artifacts/phase0_5/call_ledger.json"
OUTPUT_DIR = REPO_ROOT / "artifacts/phase0_5/availability"
PRIOR_PHYSICAL_ATTEMPTS = 5
MAX_PHYSICAL_ATTEMPTS = 100
MIN_REAL_TRAJECTORY_RESERVE = 70


def _metrics(records, budget: CallBudget) -> dict:
    successful = [r for r in records if r.provider_final_status == ProviderFinalStatus.SUCCESS]
    logical = len(records)
    first_successes = sum(r.provider_attempt_count == 1 for r in successful)
    attempts = sum(r.provider_attempt_count for r in records)
    latencies = [
        r.successful_latency_ms
        for r in successful
        if r.successful_latency_ms is not None
    ]
    other = {}
    for record in records:
        status = record.provider_final_status.value
        if status not in ("SUCCESS", "PROVIDER_UNAVAILABLE"):
            other[status] = other.get(status, 0) + 1
    return {
        "logical_probes_attempted": logical,
        "probes_eventually_successful": len(successful),
        "physical_api_attempts": attempts,
        "first_attempt_success_rate": first_successes / logical if logical else 0.0,
        "eventual_success_rate": len(successful) / logical if logical else 0.0,
        "provider_503_count": sum(r.provider_503_count for r in records),
        "provider_429_count": sum(
            r.provider_final_status == ProviderFinalStatus.RATE_LIMITED for r in records
        ),
        "other_error_types": other,
        "median_successful_latency_ms": statistics.median(latencies) if latencies else None,
        "maximum_successful_latency_ms": max(latencies) if latencies else None,
        "global_physical_attempts_used": budget.used,
        "global_physical_attempts_remaining": budget.remaining,
    }


def _passes(metrics: dict) -> bool:
    permanent = metrics["provider_429_count"] or metrics["other_error_types"]
    return bool(
        metrics["probes_eventually_successful"] >= 5
        and metrics["eventual_success_rate"] >= 0.80
        and not permanent
        and metrics["global_physical_attempts_remaining"] >= MIN_REAL_TRAJECTORY_RESERVE
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-probes", type=int, default=10)
    ap.add_argument("--probe-spacing", type=float, default=15.0)
    args = ap.parse_args()
    if not 1 <= args.max_probes <= 10:
        raise SystemExit("--max-probes must be between 1 and 10")

    load_agent_dotenv()
    load_windows_user_scope_env((CREDENTIAL_ENV, *ALT_ENV))
    if not any(os.environ.get(n) for n in (CREDENTIAL_ENV, *ALT_ENV)):
        print("STOP: Gemini credential unavailable; zero requests made.")
        return 2

    import litellm

    budget = CallBudget.from_ledger(
        LEDGER, max_calls=MAX_PHYSICAL_ATTEMPTS, initial_used=PRIOR_PHYSICAL_ATTEMPTS
    )
    records = []
    executor = ProviderRequestExecutor(
        call_budget=budget, records=records, scope="availability-probe"
    )
    permanent_error = False

    for probe_index in range(args.max_probes):
        if probe_index:
            time.sleep(args.probe_spacing)
        try:
            executor.call(
                lambda: litellm.completion(
                    model=MODEL,
                    messages=[{"role": "user", "content": "Reply with OK."}],
                    max_tokens=5,
                    num_retries=0,
                    timeout=420,
                )
            )
        except ProviderUnavailable:
            pass
        except NonRetryableProviderError:
            permanent_error = True

        metrics = _metrics(records, budget)
        print(
            f"probe {probe_index + 1}: {records[-1].provider_final_status.value}; "
            f"logical={len(records)} physical={metrics['physical_api_attempts']} "
            f"remaining={budget.remaining}",
            flush=True,
        )
        if permanent_error or budget.remaining < MIN_REAL_TRAJECTORY_RESERVE:
            break
        # Stop at the first defensible passing gate to preserve trajectory slots.
        if _passes(metrics):
            break

    metrics = _metrics(records, budget)
    decision = "PROCEED" if _passes(metrics) else "STOP"
    payload = {
        "kind": "phase0_5_availability_gate",
        "model": MODEL,
        "fixed_prompt": "Reply with OK.",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "gate_decision": decision,
        "records": [r.model_dump(mode="json") for r in records],
        "interpretation": "infrastructure availability gate; not a model performance benchmark",
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = OUTPUT_DIR / f"gate-{stamp}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"artifact={out}")
    return 0 if decision == "PROCEED" else 10


if __name__ == "__main__":
    raise SystemExit(main())
