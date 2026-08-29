"""Phase 0.5 Gemini preflight: verify before spending a single call.

    uv run --group agent python scripts/phase0/preflight_gemini.py

Checks, in order, and STOPS at the first failure:

  1. credential presence           -- existence only; the value is NEVER read,
                                      printed, logged, or written anywhere
  2. litellm provider resolution   -- offline; confirms the model identifier
  3. mini-swe-agent model construction -- offline
  4. minimal connectivity test     -- ONE call, max_tokens=1, trivial prompt

The connectivity call is the smallest harmless request that can prove the
credential and model work. It counts against the Phase 0.5 call ceiling and is
reported in the milestone accounting.

DATA RULE: this script sends the literal string "hi" and nothing else. No
repository content, no environment, no file contents.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

MODEL = "gemini/gemini-3.7-flash"
#: LiteLLM's documented env var for the Gemini Developer API (google AI Studio).
CREDENTIAL_ENV = "GEMINI_API_KEY"
#: Accepted alternates that litellm/google SDKs also honour.
ALT_ENV = ("GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY")


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def main() -> int:
    print(f"Phase 0.5 preflight -- model {MODEL}\n")

    # --- 1. credential presence (existence only; never the value) ----------
    present = [n for n in (CREDENTIAL_ENV, *ALT_ENV) if os.environ.get(n)]
    if not check(
        "1_credential_present",
        bool(present),
        f"found {present}" if present else
        f"none of {CREDENTIAL_ENV}, {', '.join(ALT_ENV)} set in this process",
    ):
        print(
            "\nSTOP: no Gemini credential is visible to this process.\n"
            "  Set it and re-run, e.g. (PowerShell, current session):\n"
            f"    $env:{CREDENTIAL_ENV} = '<key>'\n"
            "  or persist it for future sessions:\n"
            f"    setx {CREDENTIAL_ENV} '<key>'\n"
            "  NOTE: a variable set in another terminal does NOT reach an\n"
            "  already-running process; the harness must be started after it.\n"
            "  Do not paste the key into the repository or any config file\n"
            "  that git tracks."
        )
        return 2

    # --- 2. litellm resolution (offline) -----------------------------------
    try:
        import litellm

        resolved, provider = litellm.get_llm_provider(MODEL)[:2]
        check("2_litellm_resolves_model", True, f"{resolved} -> provider '{provider}'")
    except Exception as exc:
        check("2_litellm_resolves_model", False, repr(exc)[:200])
        return 3

    # --- 3. mini-swe-agent model construction (offline) --------------------
    try:
        os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")
        from minisweagent.models import get_model

        model = get_model(MODEL)
        check("3_mini_swe_agent_model_built", True, type(model).__name__)
    except Exception as exc:
        check("3_mini_swe_agent_model_built", False, repr(exc)[:300])
        return 4

    # --- 4. minimal connectivity test: ONE call, 1 token -------------------
    try:
        resp = litellm.completion(
            model=MODEL,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        usage = getattr(resp, "usage", None)
        detail = (
            f"prompt_tokens={getattr(usage, 'prompt_tokens', '?')} "
            f"completion_tokens={getattr(usage, 'completion_tokens', '?')}"
        )
        check("4_connectivity", True, detail)
    except Exception as exc:
        name = type(exc).__name__
        check("4_connectivity", False, f"{name}: {str(exc)[:300]}")
        if "RateLimit" in name or "429" in str(exc):
            print("\nSTOP: rate limited / quota exhausted on the free tier.")
            return 5
        print("\nSTOP: connectivity failed. Do NOT substitute another model.")
        return 6

    print("\nPreflight OK. 1 model call consumed by the connectivity test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
