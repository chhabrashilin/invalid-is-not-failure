"""Persist a ListModels metadata snapshot for the Phase 0.5 eligibility finding.

ListModels is a non-generative metadata GET. It is recorded in a SEPARATE
metadata counter and is deliberately NOT charged to
PHASE_0_5_25_FLASH_MAX_PHYSICAL_CALLS, which governs inference attempts.
The API key is never persisted.
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

from preflight_gemini import (  # noqa: E402
    ALT_ENV,
    CREDENTIAL_ENV,
    load_agent_dotenv,
    load_windows_user_scope_env,
)

OUT = REPO_ROOT / "artifacts/phase0_5/availability"
COUNTER = REPO_ROOT / "artifacts/phase0_5/provider_metadata_requests.json"


def main() -> int:
    load_agent_dotenv()
    load_windows_user_scope_env((CREDENTIAL_ENV, *ALT_ENV))
    key = os.environ.get(CREDENTIAL_ENV)
    if not key:
        print("STOP: credential unavailable")
        return 2

    import httpx

    started = datetime.now(timezone.utc)
    versions: dict = {}
    requests_made = 0
    for ver in ("v1beta", "v1"):
        t0 = time.perf_counter()
        resp = httpx.get(
            f"https://generativelanguage.googleapis.com/{ver}/models",
            params={"key": key, "pageSize": 200},
            timeout=90.0,
        )
        requests_made += 1
        entry = {
            "status_code": resp.status_code,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            entry["model_count"] = len(models)
            entry["models"] = [
                {
                    "name": m["name"],
                    "supportedGenerationMethods": m.get("supportedGenerationMethods"),
                }
                for m in sorted(models, key=lambda x: x["name"])
            ]
        else:
            entry["body"] = resp.text[:500].replace(key, "<REDACTED>")
        versions[ver] = entry

    snapshot = {
        "kind": "phase0_5_gemini_listmodels_snapshot",
        "captured_at": started.isoformat(),
        "endpoint": "https://generativelanguage.googleapis.com/{version}/models",
        "request_kind": "non-generative metadata GET (ListModels)",
        "credential_env": CREDENTIAL_ENV,
        "versions": versions,
        "finding": (
            "ListModels presence does NOT imply generateContent eligibility: "
            "models/gemini-2.5-flash is listed with generateContent in both v1beta "
            "and v1 for this credential, yet generateContent returns HTTP 404 "
            "'no longer available to new users'."
        ),
        "actual_spend_usd": 0.0,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"gemini-listmodels-{started.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    prior = json.loads(COUNTER.read_text(encoding="utf-8")) if COUNTER.exists() else {
        "kind": "phase0_5_provider_metadata_requests",
        "accounting_unit": "non_generative_metadata_http_request",
        "note": (
            "Separate from GLOBAL_PROVIDER_ATTEMPTS (inference attempts) and from "
            "PHASE_0_5_25_FLASH_MAX_PHYSICAL_CALLS. Disclosed, free, never billed."
        ),
        "requests": 0,
        "events": [],
    }
    prior["requests"] = int(prior.get("requests", 0)) + requests_made
    prior.setdefault("events", []).append(
        {
            "scope": "listmodels-eligibility-diagnostic",
            "requests": requests_made,
            "ts": started.isoformat(),
            "artifact": path.name,
        }
    )
    prior["updated_at"] = datetime.now(timezone.utc).isoformat()
    COUNTER.write_text(json.dumps(prior, indent=2), encoding="utf-8")

    print(f"artifact={path}")
    print(f"metadata_requests_total={prior['requests']}")
    for ver, entry in versions.items():
        print(f"{ver}: status={entry['status_code']} count={entry.get('model_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
