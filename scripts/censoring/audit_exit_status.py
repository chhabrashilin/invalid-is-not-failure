"""Audit exit_status categories and their association with target and horizon.

The dataset's own exit statuses are part of the historical trajectory-generating
process. They are NOT our infrastructure censoring, and this script exists so
that the base population is chosen with that association visible rather than
assumed away.

    uv run python scripts/censoring/audit_exit_status.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results" / "censoring"


def main() -> int:
    tbl = pq.read_table(OUT_DIR / "trajectory_summary.parquet")
    exits = np.asarray(tbl.column("exit_status"))
    target = np.asarray(tbl.column("target"))
    H = np.asarray(tbl.column("step_count")).astype(np.int64)
    models = np.asarray(tbl.column("model_name"))

    rows = []
    for status in sorted(set(exits.tolist())):
        m = exits == status
        rows.append(
            {
                "exit_status": status,
                "n": int(m.sum()),
                "share_of_all": round(float(m.mean()), 6),
                "resolved_n": int(target[m].sum()),
                "resolve_rate": round(float(target[m].mean()), 6),
                "mean_H": round(float(H[m].mean()), 3),
                "median_H": float(np.median(H[m])),
                "mean_H_resolved": (
                    round(float(H[m & target].mean()), 3) if (m & target).any() else None
                ),
                "mean_H_unresolved": (
                    round(float(H[m & ~target].mean()), 3) if (m & ~target).any() else None
                ),
                "n_models": int(len(set(models[m].tolist()))),
            }
        )
    rows.sort(key=lambda r: -r["n"])

    with (OUT_DIR / "exit_status_audit.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"{'exit_status':38} {'n':>7} {'resolve':>8} {'meanH':>7} {'H|res':>7} {'H|unres':>8}")
    for r in rows:
        print(
            f"{r['exit_status'][:38]:38} {r['n']:7d} {r['resolve_rate']:8.4f} "
            f"{r['mean_H']:7.1f} {str(r['mean_H_resolved']):>7} {str(r['mean_H_unresolved']):>8}"
        )

    # Population summary: everything with a defined target and a parseable trajectory.
    parseable = H > 0
    summary = {
        "kind": "censoring_base_population",
        "total_rows": int(tbl.num_rows),
        "rows_with_zero_agent_steps": int((~parseable).sum()),
        "primary_population_rule": (
            "all trajectories with a defined target label and at least one parsed "
            "agent decision step (H >= 1). No row is excluded on the basis of "
            "exit_status, because exit_status is associated with success and "
            "filtering on it would condition on the outcome."
        ),
        "primary_population_n": int(parseable.sum()),
        "excluded_n": int((~parseable).sum()),
        "true_reliability_p": round(float(target[parseable].mean()), 6),
        "resolved_n": int(target[parseable].sum()),
        "unresolved_n": int((~target[parseable]).sum()),
        "mean_H_all": round(float(H[parseable].mean()), 3),
        "mean_H_resolved": round(float(H[parseable & target].mean()), 3),
        "mean_H_unresolved": round(float(H[parseable & ~target].mean()), 3),
        "median_H_resolved": float(np.median(H[parseable & target])),
        "median_H_unresolved": float(np.median(H[parseable & ~target])),
        "max_H": int(H.max()),
        "n_exit_statuses": len(rows),
        "n_models": int(len(set(models.tolist()))),
    }
    (OUT_DIR / "base_population.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("\n" + json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
