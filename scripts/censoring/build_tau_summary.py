"""Build the derived tau-bench trajectory summary (secondary validation corpus).

The dataset card declares no license, so raw trajectories are cached OUTSIDE the
repository (in a temp/cache dir) and are never redistributed. Only derived
per-trajectory statistics are written into results/.

HORIZON DEFINITION (fixed before any censoring result was examined):
    H_tau = number of messages with role == "assistant".
These are the evaluated target agent's decision turns. Excluded: `system`
(policy prompt), `user` (simulated user turns), `tool` (environment results).

    uv run python scripts/censoring/build_tau_summary.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results" / "censoring"
DATASET = "AgentSuite/tau-bench-trajectories"
REVISION = "382e57d1784b55c5155f4ef394ef48f1c747a287"
BASE = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
AGENT_ROLE = "assistant"

CACHE = Path(
    os.environ.get("TAU_CACHE")
    or Path(os.environ.get("TEMP", "/tmp")) / "tau_bench_cache"
)


def list_files() -> list[str]:
    with urllib.request.urlopen(
        f"https://huggingface.co/api/datasets/{DATASET}", timeout=120
    ) as r:
        info = json.load(r)
    return sorted(
        s["rfilename"] for s in info["siblings"] if s["rfilename"].endswith(".jsonl")
    )


def fetch(fn: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / fn
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    for attempt in range(4):
        try:
            urllib.request.urlretrieve(BASE + fn, dest)
            return dest
        except Exception:  # noqa: BLE001 - transient network
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not fetch {fn}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    files = list_files()
    print(f"model files: {len(files)}  revision {REVISION[:12]}")

    models, tasks, ids, scores, correct, finish, steps, nmsg, roles_seen = (
        [], [], [], [], [], [], [], [], Counter()
    )
    score_values = Counter()
    bad = 0
    t0 = time.time()

    for i, fn in enumerate(files):
        path = fetch(fn)
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                msgs = rec.get("messages") or []
                er = rec.get("eval_result") or {}
                meta = rec.get("meta") or {}
                roles_seen.update(m.get("role") for m in msgs)
                sc = er.get("score")
                score_values[repr(sc)] += 1

                models.append(rec.get("model_path"))
                tasks.append(rec.get("task_name"))
                ids.append(meta.get("id"))
                scores.append(np.nan if sc is None else float(sc))
                correct.append(bool(meta.get("is_correct")) if meta.get("is_correct") is not None else None)
                finish.append(meta.get("finish_reason"))
                steps.append(sum(1 for m in msgs if m.get("role") == AGENT_ROLE))
                nmsg.append(len(msgs))
        print(f"  [{i+1}/{len(files)}] {fn[:44]:44} rows={len(models)} "
              f"elapsed={time.time()-t0:.0f}s", flush=True)

    sc_arr = np.array(scores, dtype=float)
    finite = np.isfinite(sc_arr)
    uniq = sorted(set(sc_arr[finite].tolist()))
    is_binary = set(uniq).issubset({0.0, 1.0})

    table = pa.table({
        "model_path": pa.array(models, pa.string()),
        "task_name": pa.array(tasks, pa.string()),
        "task_id": pa.array(ids, pa.string()),
        "score": pa.array(sc_arr, pa.float64()),
        "is_correct": pa.array(correct, pa.bool_()),
        "finish_reason": pa.array(finish, pa.string()),
        "step_count": pa.array(np.array(steps, dtype=np.int32), pa.int32()),
        "n_messages": pa.array(np.array(nmsg, dtype=np.int32), pa.int32()),
    })
    pq.write_table(table, OUT_DIR / "tau_trajectory_summary.parquet")

    prov = {
        "kind": "tau_bench_summary_provenance",
        "dataset": DATASET,
        "revision": REVISION,
        "retrieval_date": started.date().isoformat(),
        "declared_license": None,
        "license_note": (
            "The dataset card declares no license. Raw trajectories are cached "
            "outside the repository and are NOT redistributed; only derived "
            "per-trajectory statistics are stored."
        ),
        "model_files": len(files),
        "rows": table.num_rows,
        "unparseable_lines": bad,
        "roles_observed": dict(roles_seen),
        "agent_role_counted": AGENT_ROLE,
        "step_count_definition": (
            'H_tau = number of messages with role == "assistant" (evaluated '
            "target agent decision turns); system/user/tool excluded."
        ),
        "step_count_defined_before_results": True,
        "score_values_observed": dict(score_values),
        "distinct_finite_scores": uniq,
        "score_is_binary": bool(is_binary),
        "n_missing_score": int((~finite).sum()),
        "finish_reasons": dict(Counter(finish)),
        "wall_time_s": time.time() - t0,
    }
    (OUT_DIR / "tau_provenance.json").write_text(
        json.dumps(prov, indent=2), encoding="utf-8"
    )
    print(f"\nrows={table.num_rows}  roles={dict(roles_seen)}")
    print(f"distinct scores={uniq}  binary={is_binary}  missing={int((~finite).sum())}")
    print(f"finish_reasons={dict(Counter(finish))}")
    if not is_binary:
        print("\n*** SCORE IS NOT BINARY -- STOP and define a principled mapping "
              "from benchmark documentation before computing censoring results.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
