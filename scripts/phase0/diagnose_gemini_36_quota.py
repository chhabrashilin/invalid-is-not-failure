"""Capture the verbatim Gemini 3.6 Flash 429 body to identify the quota type.

The Phase 0.5 real run terminated on HTTP 429 after 9 successful model calls.
Whether that is a per-minute (RPM) or per-day (RPD) quota decides whether a
same-configuration rerun is possible at all, so the response body is needed.

Makes at most one physical attempt, never retries, and records the attempt in
both the global provenance ledger and the Gemini-3.6-specific ceiling. The API
key is never logged or persisted.
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
from preflight_gemini import (  # noqa: E402
    ALT_ENV,
    CREDENTIAL_ENV,
    load_agent_dotenv,
    load_windows_user_scope_env,
)

MODEL = "gemini/gemini-3.6-flash"
GLOBAL_LEDGER_PATH = REPO_ROOT / "artifacts/phase0_5/global_provider_attempts.json"
MODEL_LEDGER_PATH = REPO_ROOT / "artifacts/phase0_5/gemini_3_6_flash_call_ledger.json"
OUT = REPO_ROOT / "artifacts/phase0_5/availability"


def main() -> int:
    load_agent_dotenv()
    load_windows_user_scope_env((CREDENTIAL_ENV, *ALT_ENV))
    key = os.environ.get(CREDENTIAL_ENV)
    if not key:
        print("STOP: credential unavailable")
        return 2

    def redact(t: str) -> str:
        return t.replace(key, "<REDACTED_GEMINI_API_KEY>")

    import litellm

    global_ledger = GlobalAttemptLedger.from_ledger(GLOBAL_LEDGER_PATH, initial_used=12)
    model_budget = CallBudget.from_ledger(
        MODEL_LEDGER_PATH,
        max_calls=100,
        initial_used=0,
        metadata={
            "model_id": MODEL,
            "constant": "PHASE_0_5_36_FLASH_MAX_PHYSICAL_CALLS",
            "actual_spend_ceiling_usd": 0.0,
        },
    )
    budget = CompositeCallBudget(
        model_budget=model_budget, global_ledger=global_ledger, model_id=MODEL
    )
    budget.check_and_reserve(scope="gemini-3.6-quota-diagnostic")

    started = datetime.now(timezone.utc)
    result: dict = {
        "kind": "phase0_5_gemini_3_6_flash_quota_diagnostic",
        "model": MODEL,
        "started_at": started.isoformat(),
        "physical_attempts": 1,
        "purpose": "identify RPM vs RPD quota from the verbatim 429 body",
    }
    t0 = time.perf_counter()
    try:
        resp = litellm.completion(
            model=MODEL,
            messages=[{"role": "user", "content": "Reply with OK."}],
            max_tokens=5,
            num_retries=0,
            timeout=90.0,
        )
        result.update(
            {
                "outcome": "SUCCESS",
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "text": str(resp.choices[0].message.content),
                "quota_state": "RECOVERED - quota window has reset",
            }
        )
    except Exception as exc:  # noqa: BLE001 - diagnostic captures everything
        status, code = classify_provider_error(exc)
        msg = redact(str(exc))
        low = msg.lower()
        if "perday" in low.replace("_", "").replace(" ", "") or "per day" in low:
            quota = "PER_DAY (RPD) - blocked until the daily window resets"
        elif "perminute" in low.replace("_", "").replace(" ", "") or "per minute" in low:
            quota = "PER_MINUTE (RPM) - short cooldown"
        else:
            quota = "UNDETERMINED from body"
        result.update(
            {
                "outcome": "ERROR",
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "classified_status": status.value,
                "status_code": code,
                "exception_type": type(exc).__name__,
                "exception_message": msg[:4000],
                "quota_state": quota,
            }
        )

    result.update(
        {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "global_provider_attempts": global_ledger.used,
            "model_specific_attempts_used": model_budget.used,
            "model_specific_attempts_remaining": model_budget.remaining,
            "actual_spend_usd": 0.0,
        }
    )
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"gemini-36-quota-{started.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"artifact={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
