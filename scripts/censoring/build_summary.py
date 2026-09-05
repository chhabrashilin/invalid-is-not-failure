"""Build the compact trajectory summary from nebius/SWE-agent-trajectories.

Only five leaf columns are read from the remote parquet shards
(instance_id, model_name, target, exit_status, trajectory.list.element.role),
which is ~0.1% of the 1.11 GB payload. The large `text`, `generated_patch` and
`eval_logs` columns are never downloaded.

STEP-COUNT DEFINITION (fixed before any censoring result was examined):
    H = number of messages in `trajectory` whose role == "ai".
Each such message is one agent decision/action turn. `system` and `user`
messages are environment/scaffold turns and are NOT agent decisions.

    uv run python scripts/censoring/build_summary.py
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import fsspec
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results" / "censoring"
DATASET = "nebius/SWE-agent-trajectories"
PARQUET_API = (
    f"https://huggingface.co/api/datasets/{DATASET}/parquet/default/train"
)
AGENT_ROLE = "ai"


def dataset_revision() -> dict:
    """Record the exact dataset revision for reproducibility."""
    with urllib.request.urlopen(
        f"https://huggingface.co/api/datasets/{DATASET}"
    ) as r:
        info = json.load(r)
    return {
        "dataset": DATASET,
        "sha": info.get("sha"),
        "lastModified": info.get("lastModified"),
        "license": (info.get("cardData") or {}).get("license"),
        "downloads": info.get("downloads"),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    rev = dataset_revision()
    print(f"dataset revision: {rev['sha']}  license={rev['license']}")

    urls = json.load(urllib.request.urlopen(PARQUET_API))
    print(f"shards: {len(urls)}")
    fs = fsspec.filesystem("http")

    ids, models, targets, exits, steps, msgs = [], [], [], [], [], []
    bytes_read = 0
    t0 = time.time()

    for si, url in enumerate(urls):
        # HF range requests occasionally return 400; retry with a fresh handle.
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                pf = pq.ParquetFile(fs.open(url))
                # Leaf paths live in row-group column metadata, not schema.names.
                rg0 = pf.metadata.row_group(0)
                leafs = [rg0.column(i).path_in_schema for i in range(rg0.num_columns)]
                role_leaf = next(k for k in leafs if k.endswith(".role"))
                cols = ["instance_id", "model_name", "target", "exit_status", role_leaf]

                shard_bytes = 0
                for rg in range(pf.metadata.num_row_groups):
                    m = pf.metadata.row_group(rg)
                    for i in range(m.num_columns):
                        c = m.column(i)
                        if c.path_in_schema in cols:
                            shard_bytes += c.total_compressed_size

                tbl = pf.read(columns=cols)
                bytes_read += shard_bytes
                break
            except Exception as exc:  # noqa: BLE001 - transient HTTP/range errors
                last_exc = exc
                wait = 5 * (attempt + 1)
                print(f"  shard {si+1} attempt {attempt+1} failed "
                      f"({type(exc).__name__}); retrying in {wait}s", flush=True)
                time.sleep(wait)
        else:
            raise RuntimeError(f"shard {si+1} failed after 4 attempts") from last_exc
        ids.append(tbl.column("instance_id").combine_chunks())
        models.append(tbl.column("model_name").combine_chunks())
        targets.append(tbl.column("target").combine_chunks())
        exits.append(tbl.column("exit_status").combine_chunks())

        # Vectorised H: flatten the list<struct<role>> and count "ai" per row.
        traj = tbl.column("trajectory").combine_chunks()
        offsets = np.asarray(traj.offsets)
        roles = np.asarray(traj.values.field("role"))
        is_agent = (roles == AGENT_ROLE).astype(np.int64)
        cum = np.concatenate([[0], np.cumsum(is_agent)])
        steps.append(cum[offsets[1:]] - cum[offsets[:-1]])
        msgs.append(np.diff(offsets))

        print(
            f"  shard {si+1}/{len(urls)}: rows={tbl.num_rows} "
            f"cum_rows={sum(len(s) for s in steps)} "
            f"elapsed={time.time()-t0:.0f}s",
            flush=True,
        )

    table = pa.table(
        {
            "instance_id": pa.concat_arrays([a.cast(pa.string()) for a in ids]),
            "model_name": pa.concat_arrays([a.cast(pa.string()) for a in models]),
            "target": pa.concat_arrays([a.cast(pa.bool_()) for a in targets]),
            "exit_status": pa.concat_arrays([a.cast(pa.string()) for a in exits]),
            "step_count": pa.array(np.concatenate(steps), pa.int32()),
            "n_messages": pa.array(np.concatenate(msgs), pa.int32()),
        }
    )
    out = OUT_DIR / "trajectory_summary.parquet"
    pq.write_table(table, out)

    prov = {
        "kind": "censoring_trajectory_summary_provenance",
        **rev,
        "parquet_shards": len(urls),
        "retrieval_date": started.date().isoformat(),
        "retrieved_at": started.isoformat(),
        "rows": table.num_rows,
        "columns_read": ["instance_id", "model_name", "target", "exit_status",
                         "trajectory.list.element.role"],
        "compressed_bytes_read": int(bytes_read),
        "full_dataset_bytes": 1_113_000_000,
        "fraction_downloaded": round(bytes_read / 1_113_000_000, 5),
        "step_count_definition": (
            'H = number of trajectory messages with role == "ai"; one agent '
            "decision/action turn each. system/user messages are scaffold and "
            "environment turns and are excluded."
        ),
        "step_count_defined_before_results": True,
        "filtering": "none at this stage; all rows retained",
        "wall_time_s": time.time() - t0,
    }
    (OUT_DIR / "dataset_provenance.json").write_text(
        json.dumps(prov, indent=2), encoding="utf-8"
    )

    print(f"\nrows={table.num_rows}  downloaded={bytes_read/1e6:.2f} MB "
          f"({100*bytes_read/1.113e9:.2f}% of full dataset)")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
