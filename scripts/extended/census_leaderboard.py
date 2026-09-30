"""Invalidity census of the public SWE-bench leaderboards (extended paper).

Every submission's results.json lists instance ids per evaluation outcome. The
leaderboard score is |resolved| / N, which is the invalid-as-failure policy.
We classify outcomes with Definition 1 of the paper:

  evaluation censoring   no_logs, install_fail, reset_failed
                         (the evaluation harness produced no verdict)
  unattributable         no_generation, test_timeout
                         (no patch, or tests ran out of time: agent, provider,
                         or harness could be responsible)
  outcome                everything else (resolved, patch failed to apply,
                         applied but not resolved)

For each submission we report the assumption-free identified interval under a
strict reading (only evaluation censoring is missing) and a broad reading
(unattributable runs are missing too), and we count leaderboard orderings the
data do not identify: A above B is identified only if A's lower endpoint
exceeds B's upper endpoint.

    uv run python scripts/extended/census_leaderboard.py
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "data" / "raw" / "swebench_experiments"
OUT = REPO_ROOT / "results" / "extended"
N_TASKS = {"verified": 500, "lite": 300, "test": 2294}
EVAL_CENSOR = ("no_logs", "install_fail", "reset_failed")
UNATTRIB = ("no_generation", "test_timeout")


def classify(d: dict) -> dict:
    R = set(d.get("resolved", []))
    E = set().union(*(set(d.get(k, [])) for k in EVAL_CENSOR)) - R
    U = set().union(*(set(d.get(k, [])) for k in UNATTRIB)) - R - E
    return {"R": len(R), "E": len(E), "U": len(U),
            "detailed": "install_fail" in d}


def identified_pairs(rows, key_hi):
    """Share of ordered pairs (by score) whose order the intervals identify."""
    total = ident = 0
    for a, b in combinations(sorted(rows, key=lambda r: -r["score"]), 2):
        if a["score"] == b["score"]:
            continue
        total += 1
        ident += a["lo"] > b[key_hi]
    return total, ident


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((RAW / "manifest.json").read_text())
    report = {"source": manifest, "splits": {}}
    for split, N in N_TASKS.items():
        rows = []
        for f in sorted((RAW / split).glob("*/results.json")):
            c = classify(json.loads(f.read_text(encoding="utf-8")))
            rows.append({
                "submission": f.parent.name, "N": N, **c,
                "score": c["R"] / N, "lo": c["R"] / N,
                "hi_strict": (c["R"] + c["E"]) / N,
                "hi_broad": (c["R"] + c["E"] + c["U"]) / N,
                "cc_strict": c["R"] / (N - c["E"]) if N > c["E"] else None,
            })
        rows.sort(key=lambda r: -r["score"])
        inv_e = np.array([r["E"] / N for r in rows])
        inv_u = np.array([r["U"] / N for r in rows])
        tot, id_s = identified_pairs(rows, "hi_strict")
        _, id_b = identified_pairs(rows, "hi_broad")
        adj = [(a, b) for a, b in zip(rows, rows[1:]) if a["score"] > b["score"]]
        adj_s = sum(a["lo"] > b["hi_strict"] for a, b in adj)
        adj_b = sum(a["lo"] > b["hi_broad"] for a, b in adj)
        top = rows[:10]
        ttot, tid_s = identified_pairs(top, "hi_strict")
        _, tid_b = identified_pairs(top, "hi_broad")
        s = {
            "n_submissions": len(rows),
            "n_detailed": int(sum(r["detailed"] for r in rows)),
            "share_with_any_eval_censoring": float((inv_e > 0).mean()),
            "share_with_any_unattributable": float((inv_u > 0).mean()),
            "median_eval_censored_pct": float(np.median(inv_e) * 100),
            "max_eval_censored_pct": float(inv_e.max() * 100),
            "median_unattrib_pct": float(np.median(inv_u) * 100),
            "max_unattrib_pct": float(inv_u.max() * 100),
            "pairs": tot, "pairs_identified_strict": id_s, "pairs_identified_broad": id_b,
            "adjacent_pairs": len(adj), "adjacent_identified_strict": adj_s,
            "adjacent_identified_broad": adj_b,
            "top10_pairs": ttot, "top10_identified_strict": tid_s,
            "top10_identified_broad": tid_b,
            "top10": [{k: r[k] for k in ("submission", "score", "E", "U", "hi_strict",
                                         "hi_broad")} for r in top],
        }
        report["splits"][split] = {"summary": s, "rows": rows}
        print(f"\n== {split}: {len(rows)} submissions ({s['n_detailed']} with detailed "
              f"harness categories)")
        print(f"   any eval censoring: {s['share_with_any_eval_censoring']:.2f}  "
              f"median {s['median_eval_censored_pct']:.2f}%  max {s['max_eval_censored_pct']:.2f}%")
        print(f"   any unattributable: {s['share_with_any_unattributable']:.2f}  "
              f"median {s['median_unattrib_pct']:.2f}%  max {s['max_unattrib_pct']:.2f}%")
        print(f"   pairs identified strict {id_s}/{tot} ({id_s / tot:.3f}), "
              f"broad {id_b}/{tot} ({id_b / tot:.3f})")
        print(f"   adjacent identified strict {adj_s}/{len(adj)}, broad {adj_b}/{len(adj)}")
        print(f"   top-10 pairs identified strict {tid_s}/{ttot}, broad {tid_b}/{ttot}")
    (OUT / "census_leaderboard.json").write_text(json.dumps(report, indent=1),
                                                 encoding="utf-8")
    print(f"\nwrote {OUT / 'census_leaderboard.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
