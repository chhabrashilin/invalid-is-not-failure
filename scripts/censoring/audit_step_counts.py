"""Validate the step-count parser against independently fetched full trajectories.

The summary parquet is built from a pruned `role` column. This script re-fetches
20 randomly chosen trajectories IN FULL from the datasets-server rows API and
recounts agent decision turns from the complete record, then compares.

Exact agreement is required before any censoring result is computed.

    uv run python scripts/censoring/audit_step_counts.py
"""

from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results" / "censoring"
DATASET = "nebius/SWE-agent-trajectories"
MASTER_SEED = 20260905
N_AUDIT = 20
AGENT_ROLE = "ai"


def fetch_row(offset: int) -> dict:
    url = (
        "https://datasets-server.huggingface.co/rows?"
        f"dataset={urllib.parse.quote(DATASET, safe='')}"
        f"&config=default&split=train&offset={offset}&length=1"
    )
    for _ in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)["rows"][0]["row"]
        except Exception:  # noqa: BLE001 - transient API errors
            continue
    raise RuntimeError(f"could not fetch row {offset}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tbl = pq.read_table(OUT_DIR / "trajectory_summary.parquet")
    n = tbl.num_rows
    ids = tbl.column("instance_id").to_pylist()
    parser_steps = np.asarray(tbl.column("step_count"))
    parser_msgs = np.asarray(tbl.column("n_messages"))

    rng = np.random.default_rng(MASTER_SEED)
    offsets = sorted(rng.choice(n, size=N_AUDIT, replace=False).tolist())

    rows, n_match, n_id_match = [], 0, 0
    for off in offsets:
        row = fetch_row(off)
        traj = row["trajectory"]
        roles = Counter(m["role"] for m in traj)
        independent_H = roles[AGENT_ROLE]

        # An agent decision turn must carry model-authored text.
        nonempty_ai = sum(
            1 for m in traj if m["role"] == AGENT_ROLE and (m.get("text") or "").strip()
        )

        id_ok = row["instance_id"] == ids[off]
        match = independent_H == int(parser_steps[off])
        n_match += match
        n_id_match += id_ok
        rows.append(
            {
                "row_offset": off,
                "instance_id_api": row["instance_id"],
                "instance_id_parquet": ids[off],
                "instance_id_match": id_ok,
                "parser_step_count": int(parser_steps[off]),
                "independent_ai_turns": independent_H,
                "nonempty_ai_turns": nonempty_ai,
                "exact_match": match,
                "total_messages_parquet": int(parser_msgs[off]),
                "total_messages_api": len(traj),
                "role_breakdown": dict(roles),
                "target": row["target"],
                "exit_status": row["exit_status"],
            }
        )
        print(
            f"  offset {off:6d}: parser={int(parser_steps[off]):3d} "
            f"independent={independent_H:3d} nonempty={nonempty_ai:3d} "
            f"{'OK' if match else '*** MISMATCH ***'}"
        )

    with (OUT_DIR / "step_count_audit.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            r = dict(r)
            r["role_breakdown"] = json.dumps(r["role_breakdown"])
            w.writerow(r)

    all_nonempty = all(r["nonempty_ai_turns"] == r["independent_ai_turns"] for r in rows)
    print(
        f"\naudited {N_AUDIT}  exact step matches {n_match}/{N_AUDIT}  "
        f"instance_id matches {n_id_match}/{N_AUDIT}  "
        f"every ai turn non-empty: {all_nonempty}"
    )
    print(f"seed={MASTER_SEED}  wrote {OUT_DIR/'step_count_audit.csv'}")
    return 0 if n_match == N_AUDIT and n_id_match == N_AUDIT else 1


if __name__ == "__main__":
    raise SystemExit(main())
