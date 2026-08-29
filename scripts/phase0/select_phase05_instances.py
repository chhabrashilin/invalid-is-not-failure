"""Select THREE Phase 0.5 candidate instances by a pre-declared deterministic rule.

SELECTION RULE (fixed before any execution, Phase 0.5 Step 8)
--------------------------------------------------------------
    key(instance_id) = sha256(PROJECT_SEED + "|" + instance_id).hexdigest()
    sort all 500 SWE-bench_Verified instance_ids by key, ascending
    take the first three

PROJECT_SEED is a fixed string committed to the repository. The rule depends
only on the instance id and that constant, so it is:
  * reproducible by anyone,
  * blind to difficulty, repository, patch size, and expected pass/fail,
  * impossible to tune toward a desired outcome without changing the committed
    seed (which would be visible in git history).

Candidate #1 is the one to run. #2 and #3 exist only as replacements if #1
exposes an INFRASTRUCTURE failure (e.g. image unavailable) rather than valid
agent behaviour. A run that simply fails the task is a valid outcome and must
NOT trigger a switch to #2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATASET = "princeton-nlp/SWE-bench_Verified"
BASE = "https://datasets-server.huggingface.co/rows"
PAGE = 100
EXPECTED_ROWS = 500

#: Fixed project seed. Changing this invalidates the pre-declaration.
PROJECT_SEED = "resched-phase0.5-2026"


def sort_key(instance_id: str) -> str:
    return hashlib.sha256(f"{PROJECT_SEED}|{instance_id}".encode()).hexdigest()


def fetch_instance_ids() -> list[str]:
    ids: list[str] = []
    for offset in range(0, EXPECTED_ROWS, PAGE):
        url = (
            f"{BASE}?dataset={DATASET.replace('/', '%2F')}"
            f"&config=default&split=test&offset={offset}&length={PAGE}"
        )
        with urllib.request.urlopen(url, timeout=120) as resp:
            payload = json.load(resp)
        ids.extend(row["row"]["instance_id"] for row in payload["rows"])
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="configs/phase0/phase05_candidates.json")
    args = ap.parse_args()

    ids = fetch_instance_ids()
    if len(ids) != EXPECTED_ROWS:
        print(f"WARNING: expected {EXPECTED_ROWS}, got {len(ids)}", file=sys.stderr)

    ranked = sorted(ids, key=sort_key)
    candidates = ranked[:3]

    record = {
        "dataset": DATASET,
        "project_seed": PROJECT_SEED,
        "selection_rule": (
            "sort instance_ids by sha256(PROJECT_SEED + '|' + instance_id), "
            "ascending; take the first three"
        ),
        "rule_declared_before_execution": True,
        "n_instances_seen": len(ids),
        "candidates": [
            {"rank": i + 1, "instance_id": cid, "sort_key": sort_key(cid)[:16]}
            for i, cid in enumerate(candidates)
        ],
        "run_policy": (
            "Run candidate #1 only. Fall through to #2/#3 ONLY on infrastructure "
            "failure (image unavailable, container will not start). A failed task "
            "is a valid outcome and must not trigger a switch."
        ),
        "selected_at": datetime.now(timezone.utc).isoformat(),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
