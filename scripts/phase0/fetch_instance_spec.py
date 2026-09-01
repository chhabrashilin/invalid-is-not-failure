"""Fetch one SWE-bench_Verified row and write its instance spec + test_patch.

Mirrors the astropy Phase 0 layout so the Phase 0.5 runner can consume it. The
official ``test_patch`` is written to a separate file and is used ONLY by the
independent evaluator, never by the agent.

    python scripts/phase0/fetch_instance_spec.py --instance matplotlib__matplotlib-23412
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET = "princeton-nlp/SWE-bench_Verified"
BASE = "https://datasets-server.huggingface.co/rows"
PAGE = 100
EXPECTED_ROWS = 500

# Fields copied into the instance spec. `problem_statement` is the ONLY task
# text the agent may see; `test_patch`, FAIL_TO_PASS and PASS_TO_PASS are
# evaluator-side oracle data and must never reach the agent prompt.
SPEC_FIELDS = (
    "repo",
    "instance_id",
    "base_commit",
    "environment_setup_commit",
    "version",
    "problem_statement",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
)


def fetch_row(instance_id: str) -> dict:
    for offset in range(0, EXPECTED_ROWS, PAGE):
        url = (
            f"{BASE}?dataset={urllib.parse.quote(DATASET, safe='')}"
            f"&config=default&split=test&offset={offset}&length={PAGE}"
        )
        with urllib.request.urlopen(url, timeout=180) as resp:
            payload = json.load(resp)
        for row in payload["rows"]:
            if row["row"]["instance_id"] == instance_id:
                return row["row"]
    raise SystemExit(f"instance {instance_id!r} not found in {DATASET}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", required=True)
    ap.add_argument("--outdir", default="configs/phase0")
    args = ap.parse_args()

    row = fetch_row(args.instance)
    outdir = REPO_ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    spec = {}
    for field in SPEC_FIELDS:
        value = row[field]
        # HF returns the two test lists as JSON-encoded strings.
        if field in ("FAIL_TO_PASS", "PASS_TO_PASS") and isinstance(value, str):
            value = json.loads(value)
        spec[field] = value

    spec_path = outdir / f"instance_{args.instance}.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    patch_path = outdir / f"test_patch_{args.instance}.diff"
    patch_path.write_text(row["test_patch"], encoding="utf-8")

    print(f"spec={spec_path}")
    print(f"test_patch={patch_path}")
    print(f"repo={spec['repo']} base_commit={spec['base_commit']} version={spec['version']}")
    print(f"FAIL_TO_PASS ({len(spec['FAIL_TO_PASS'])}):")
    for t in spec["FAIL_TO_PASS"]:
        print("   ", t)
    print(f"PASS_TO_PASS count: {len(spec['PASS_TO_PASS'])}")
    print(f"problem_statement chars: {len(spec['problem_statement'])}")
    print(f"test_patch chars: {len(row['test_patch'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
