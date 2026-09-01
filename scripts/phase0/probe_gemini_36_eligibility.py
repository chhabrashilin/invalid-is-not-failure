"""STEP 1 - single live eligibility probe for gemini/gemini-3.6-flash.

The previous milestone established that ListModels presence and advertised
generateContent support do NOT imply generateContent eligibility for the calling
account. Only a live minimal generateContent request settles it, so this script
makes exactly ONE physical attempt and never retries.

No SWE-bench content is sent. No fallback model or provider is configured. The
API key is never logged or persisted.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "phase0"))

from instrumentation.provider_retry import (  # noqa: E402
    CallBudget,
    CompositeCallBudget,
    GlobalAttemptLedger,
    classify_provider_error,
)
from trajectory.schema import ProviderFinalStatus  # noqa: E402

from preflight_gemini import (  # noqa: E402
    ALT_ENV,
    CREDENTIAL_ENV,
    load_agent_dotenv,
    load_windows_user_scope_env,
)

MODEL = "gemini/gemini-3.6-flash"
FIXED_PROMPT = "Reply with OK."
PHYSICAL_REQUEST_TIMEOUT_S = 90.0
MODEL_SPECIFIC_MAX_PHYSICAL_CALLS = 100
HISTORICAL_GLOBAL_PROVIDER_ATTEMPTS = 12

GLOBAL_LEDGER_PATH = REPO_ROOT / "artifacts/phase0_5/global_provider_attempts.json"
MODEL_LEDGER_PATH = REPO_ROOT / "artifacts/phase0_5/gemini_3_6_flash_call_ledger.json"
OUT_DIR = REPO_ROOT / "artifacts/phase0_5/availability"

# Statuses that permanently disqualify the model. The protocol forbids retrying
# any of these and forbids automatically substituting another Gemini model.
PERMANENT_STOP = {
    ProviderFinalStatus.INVALID_MODEL,
    ProviderFinalStatus.AUTH_ERROR,
    ProviderFinalStatus.RATE_LIMITED,
    ProviderFinalStatus.BILLING_ERROR,
    ProviderFinalStatus.INVALID_REQUEST,
    ProviderFinalStatus.OTHER_ERROR,
}
# Transient statuses that MAY proceed to the availability gate.
TRANSIENT_OK = {
    ProviderFinalStatus.PROVIDER_UNAVAILABLE,
    ProviderFinalStatus.PROVIDER_TIMEOUT,
}


def main() -> int:
    load_agent_dotenv()
    adopted = load_windows_user_scope_env((CREDENTIAL_ENV, *ALT_ENV))
    key = os.environ.get(CREDENTIAL_ENV)
    if not key:
        print("STOP: Gemini credential unavailable; zero requests made.")
        return 2

    def redact(text: str) -> str:
        return text.replace(key, "<REDACTED_GEMINI_API_KEY>")

    import importlib.metadata as md
    import litellm

    resolved, provider = litellm.get_llm_provider(MODEL)[:2]
    if (resolved, provider) != ("gemini-3.6-flash", "gemini"):
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
            "constant": "PHASE_0_5_36_FLASH_MAX_PHYSICAL_CALLS",
            "actual_spend_ceiling_usd": 0.0,
            "note": (
                "Independent of the immutable Gemini 3.7 and Gemini 2.5 ledgers. "
                "Historical attempts do not count against this allowance."
            ),
        },
    )
    budget = CompositeCallBudget(
        model_budget=model_budget, global_ledger=global_ledger, model_id=MODEL
    )
    budget.check_and_reserve(scope="gemini-3.6-eligibility-probe")

    started = datetime.now(timezone.utc)
    payload: dict = {
        "kind": "phase0_5_gemini_3_6_flash_eligibility_probe",
        "step": "STEP 1 - single live generateContent eligibility probe",
        "model": MODEL,
        "fixed_prompt": FIXED_PROMPT,
        "started_at": started.isoformat(),
        "retrieval_date": "2026-08-30",
        "policy": {
            "physical_attempts_permitted": 1,
            "retries": 0,
            "retry_on": [],
            "physical_request_timeout_s": PHYSICAL_REQUEST_TIMEOUT_S,
            "hidden_litellm_retries": 0,
            "fallback_model_or_provider": None,
            "swebench_content_sent": False,
        },
        "litellm_version": md.version("litellm"),
        "litellm_resolution": {"model": resolved, "provider": provider},
        "credential_env_adopted": adopted or CREDENTIAL_ENV,
    }

    t0 = time.perf_counter()
    try:
        response = litellm.completion(
            model=MODEL,
            messages=[{"role": "user", "content": FIXED_PROMPT}],
            max_tokens=5,
            num_retries=0,
            timeout=PHYSICAL_REQUEST_TIMEOUT_S,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        usage = getattr(response, "usage", None)
        in_tok = int(getattr(usage, "prompt_tokens", 0) or 0)
        out_tok = int(getattr(usage, "completion_tokens", 0) or 0)
        payload.update(
            {
                "provider_final_status": ProviderFinalStatus.SUCCESS.value,
                "http_status": 200,
                "latency_ms": latency_ms,
                "sanitized_response_text": redact(
                    str(response.choices[0].message.content)
                )[:500],
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "total_tokens": in_tok + out_tok,
                "eligibility": "ELIGIBLE",
                "decision": "PROCEED_TO_AVAILABILITY_GATE",
            }
        )
    except Exception as exc:  # noqa: BLE001 - probe must classify everything
        latency_ms = (time.perf_counter() - t0) * 1000
        status, code = classify_provider_error(exc)
        if status in TRANSIENT_OK:
            eligibility = "TRANSIENT_UNKNOWN"
            decision = "MAY_ENTER_AVAILABILITY_GATE"
        else:
            eligibility = "INELIGIBLE"
            decision = "STOP"
        payload.update(
            {
                "provider_final_status": status.value,
                "http_status": code,
                "latency_ms": latency_ms,
                "sanitized_error": redact(str(exc))[:2000],
                "exception_type": type(exc).__name__,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "eligibility": eligibility,
                "decision": decision,
            }
        )

    payload.update(
        {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "physical_attempt_count": 1,
            "actual_spend_usd": 0.0,
            "global_provider_attempts": global_ledger.used,
            "model_specific_attempts_used": model_budget.used,
            "model_specific_attempts_remaining": model_budget.remaining,
            "interpretation": (
                "account eligibility test; not a model performance benchmark"
            ),
        }
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"gemini-36-eligibility-{started.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"artifact={out}")
    return 0 if payload["decision"] != "STOP" else 10


if __name__ == "__main__":
    raise SystemExit(main())
