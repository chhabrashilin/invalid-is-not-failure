"""Validate the tau-bench horizon parser against independently re-read records.

Re-reads 20 randomly chosen records (seed 20260905) from the cached raw JSONL
via a separate code path and recounts target-agent decision turns, then compares
against the stored summary. Also records how many of those turns are tool-call
turns vs. natural-language turns, so the reader can see what H_tau counts.

    uv run python scripts/censoring/audit_tau_step_counts.py
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results" / "censoring"
MASTER_SEED = 20260905
N_AUDIT = 20
AGENT_ROLE = "assistant"
CACHE = Path(
    os.environ.get("TAU_CACHE")
    or Path(os.environ.get("TEMP", "/tmp")) / "tau_bench_cache"
)


def main() -> int:
    tbl = pq.read_table(OUT_DIR / "tau_trajectory_summary.parquet")
    n = tbl.num_rows
    stored_steps = np.asarray(tbl.column("step_count"))
    stored_ids = tbl.column("task_id").to_pylist()
    stored_models = tbl.column("model_path").to_pylist()

    # Rebuild the (file, line) index in the same deterministic order as the build.
    files = sorted(p.name for p in CACHE.glob("*.jsonl"))
    index: list[tuple[str, int]] = []
    for fn in files:
        with (CACHE / fn).open(encoding="utf-8") as f:
            for li, line in enumerate(f):
                if line.strip():
                    index.append((fn, li))
    if len(index) != n:
        print(f"ERROR: index {len(index)} != summary rows {n}")
        return 2

    rng = np.random.default_rng(MASTER_SEED)
    picks = sorted(rng.choice(n, size=N_AUDIT, replace=False).tolist())

    rows, n_match, n_id_match = [], 0, 0
    for pick in picks:
        fn, li = index[pick]
        with (CACHE / fn).open(encoding="utf-8") as f:
            for j, line in enumerate(f):
                if j == li:
                    rec = json.loads(line)
                    break
        msgs = rec["messages"]
        # Independent recount, written separately from the builder.
        independent = 0
        toolcall_turns = 0
        text_turns = 0
        for m in msgs:
            if m.get("role") != AGENT_ROLE:
                continue
            independent += 1
            if m.get("tool_calls"):
                toolcall_turns += 1
            elif (m.get("content") or "").strip():
                text_turns += 1
        roles = Counter(m.get("role") for m in msgs)

        match = independent == int(stored_steps[pick])
        id_ok = rec["meta"]["id"] == stored_ids[pick]
        n_match += match
        n_id_match += id_ok
        rows.append({
            "row_index": pick,
            "file": fn,
            "line": li,
            "task_id_raw": rec["meta"]["id"],
            "task_id_summary": stored_ids[pick],
            "task_id_match": id_ok,
            "model_summary": stored_models[pick],
            "parser_step_count": int(stored_steps[pick]),
            "independent_agent_turns": independent,
            "toolcall_turns": toolcall_turns,
            "nl_turns": text_turns,
            "empty_turns": independent - toolcall_turns - text_turns,
            "exact_match": match,
            "role_breakdown": json.dumps(dict(roles)),
            "score": rec["eval_result"]["score"],
        })
        print(f"  {fn[:30]:30} line {li:4d}: parser={int(stored_steps[pick]):3d} "
              f"independent={independent:3d} (tool={toolcall_turns} nl={text_turns}) "
              f"{'OK' if match else '*** MISMATCH ***'}")

    with (OUT_DIR / "tau_step_count_audit.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\naudited {N_AUDIT}  exact matches {n_match}/{N_AUDIT}  "
          f"task_id matches {n_id_match}/{N_AUDIT}  seed={MASTER_SEED}")
    print(f"wrote {OUT_DIR/'tau_step_count_audit.csv'}")
    return 0 if n_match == N_AUDIT and n_id_match == N_AUDIT else 1


if __name__ == "__main__":
    raise SystemExit(main())
