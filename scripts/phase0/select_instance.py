"""Select the Phase 0 benchmark instance by a pre-declared, success-blind rule.

SELECTION RULE (fixed before any agent execution, Phase 0 Step 8)
-----------------------------------------------------------------
    Take SWE-bench_Verified (500 instances). Sort `instance_id` as ASCII
    strings, ascending. Select the FIRST element.

Why this rule: it is deterministic, reproducible by anyone, and depends only on
instance naming -- not on difficulty, image size, repository, or any belief
about whether an agent would succeed. It cannot be gamed to obtain a pass.

Writes the selection and its provenance to configs/phase0/selected_instance.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATASET = "princeton-nlp/SWE-bench_Verified"
BASE = "https://datasets-server.huggingface.co/rows"
PAGE = 100
EXPECTED_ROWS = 500


def fetch_instance_ids() -> list[str]:
    ids: list[str] = []
    for offset in range(0, EXPECTED_ROWS, PAGE):
        url = (
            f"{BASE}?dataset={DATASET.replace('/', '%2F')}"
            f"&config=default&split=test&offset={offset}&length={PAGE}"
        )
        with urllib.request.urlopen(url, timeout=120) as resp:
            payload = json.load(resp)
        for row in payload["rows"]:
            ids.append(row["row"]["instance_id"])
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="configs/phase0/selected_instance.json")
    args = ap.parse_args()

    ids = fetch_instance_ids()
    if len(ids) != EXPECTED_ROWS:
        print(f"WARNING: expected {EXPECTED_ROWS} instances, got {len(ids)}", file=sys.stderr)

    selected = sorted(ids)[0]
    record = {
        "dataset": DATASET,
        "selection_rule": "lexicographically first instance_id (ASCII ascending)",
        "rule_declared_before_execution": True,
        "n_instances_seen": len(ids),
        "selected_instance_id": selected,
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "first_five_sorted": sorted(ids)[:5],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
