"""Root-cause diagnostic for the Phase 0.5 Gemini 2.5 Flash HTTP 404.

Makes at most one physical generateContent attempt through the exact LiteLLM
call path used by the availability gate, and records it in BOTH the global
provenance ledger and the Gemini-2.5-specific ceiling. The provider API key is
never written to disk or stdout.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
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

MODEL = "gemini/gemini-2.5-flash"
FIXED_PROMPT = "Reply with OK."
TIMEOUT_S = 90.0
GLOBAL_LEDGER_PATH = REPO_ROOT / "artifacts/phase0_5/global_provider_attempts.json"
MODEL_LEDGER_PATH = REPO_ROOT / "artifacts/phase0_5/gemini_2_5_flash_call_ledger.json"
OUT = REPO_ROOT / "artifacts/phase0_5/availability"


def main() -> int:
    load_agent_dotenv()
    load_windows_user_scope_env((CREDENTIAL_ENV, *ALT_ENV))
    key = os.environ.get(CREDENTIAL_ENV)
    if not key:
        print("STOP: credential unavailable")
        return 2

    def redact(text: str) -> str:
        return text.replace(key, "<REDACTED_GEMINI_API_KEY>")

    import litellm

    global_ledger = GlobalAttemptLedger.from_ledger(GLOBAL_LEDGER_PATH, initial_used=12)
    model_budget = CallBudget.from_ledger(
        MODEL_LEDGER_PATH,
        max_calls=100,
        initial_used=0,
        metadata={
            "model_id": MODEL,
            "constant": "PHASE_0_5_25_FLASH_MAX_PHYSICAL_CALLS",
            "actual_spend_ceiling_usd": 0.0,
        },
    )
    budget = CompositeCallBudget(
        model_budget=model_budget, global_ledger=global_ledger, model_id=MODEL
    )
    budget.check_and_reserve(scope="gemini-2.5-404-root-cause-diagnostic")

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    result: dict = {
        "kind": "phase0_5_gemini_2_5_flash_404_root_cause_diagnostic",
        "model": MODEL,
        "started_at": started.isoformat(),
        "physical_attempts": 1,
        "scope": "gemini-2.5-404-root-cause-diagnostic",
    }
    try:
        response = litellm.completion(
            model=MODEL,
            messages=[{"role": "user", "content": FIXED_PROMPT}],
            max_tokens=5,
            num_retries=0,
            timeout=TIMEOUT_S,
        )
        result["outcome"] = "SUCCESS"
        result["latency_ms"] = (time.perf_counter() - t0) * 1000
        result["text"] = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        result["usage"] = {
            "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        }
    except Exception as exc:  # noqa: BLE001 - diagnostic captures everything
        status, code = classify_provider_error(exc)
        result["outcome"] = "ERROR"
        result["latency_ms"] = (time.perf_counter() - t0) * 1000
        result["classified_status"] = status.value
        result["status_code"] = code
        result["exception_type"] = type(exc).__name__
        result["exception_message"] = redact(str(exc))[:4000]
        result["traceback_tail"] = redact(
            "".join(traceback.format_exception(exc))
        )[-2500:]

    result["completed_at"] = datetime.now(timezone.utc).isoformat()
    result["global_provider_attempts"] = global_ledger.used
    result["model_specific_attempts_used"] = model_budget.used
    result["model_specific_attempts_remaining"] = model_budget.remaining
    result["actual_spend_usd"] = 0.0

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"gemini-25-404-diagnostic-{started.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"artifact={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
