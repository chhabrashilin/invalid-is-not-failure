"""Sampling uncertainty for the real provider-failure cases (extended paper).

Paired task bootstrap on the frontier leaderboard: the 500 SWE-bench Verified
tasks are resampled jointly for all 39 submissions, so score differences keep
their pairing. For each submission with provider-censored runs we recompute its
Kaplan-Meier estimate, its leaderboard score, and its rank against the other
submissions' resampled leaderboard scores.

    uv run python scripts/extended/real_case_uncertainty.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "censoring"))
from frontier_analysis import CLASS, excluded_submissions, short  # noqa: E402
from revision_analysis import km_censoring_survival  # noqa: E402

OUT = REPO_ROOT / "results" / "extended"
B = 2000
SEED = 20260930


def km_estimate(H, Y, E):
    G = km_censoring_survival(H, E, int(H.max()) + 1)
    with np.errstate(divide="ignore"):
        w = np.where(~E, 1.0 / np.where(G[H] > 0, G[H], np.inf), 0.0)
    return float((w * Y).sum() / w.sum())


def main() -> int:
    rows = list(csv.DictReader(open(OUT / "bash_only_runs.csv", encoding="utf-8")))
    excl = excluded_submissions()
    rows = [r for r in rows if r["submission"] not in excl]
    subs = sorted({r["submission"] for r in rows})
    tasks = sorted({r["instance_id"] for r in rows})
    ti = {t: k for k, t in enumerate(tasks)}
    S, T = len(subs), len(tasks)
    Y = np.zeros((S, T))
    H = np.zeros((S, T), dtype=int)
    E = np.zeros((S, T), dtype=bool)
    for r in rows:
        a, b = subs.index(r["submission"]), ti[r["instance_id"]]
        Y[a, b] = r["resolved"] == "True"
        H[a, b] = int(float(r["api_calls"]))
        E[a, b] = CLASS[r["exit_status"] or ""] == "censored"
    affected = [a for a in range(S) if E[a].sum() >= 5]
    rng = np.random.default_rng(SEED)
    res = {}
    point = {}
    for a in affected:
        point[a] = km_estimate(H[a], Y[a], E[a])
    draws = {a: {"km": [], "lb": [], "rank_lb": [], "rank_km": []} for a in affected}
    for _ in range(B):
        idx = rng.integers(0, T, T)
        scores = Y[:, idx].mean(axis=1)
        for a in affected:
            km = km_estimate(H[a, idx], Y[a, idx], E[a, idx])
            others = np.delete(scores, a)
            draws[a]["km"].append(km)
            draws[a]["lb"].append(scores[a])
            draws[a]["rank_lb"].append(1 + int((others > scores[a]).sum()))
            draws[a]["rank_km"].append(1 + int((others > km).sum()))
    for a in affected:
        d = {k: np.array(v) for k, v in draws[a].items()}
        name = short(subs[a])
        res[name] = {
            "censored": int(E[a].sum()),
            "km_point_pct": point[a] * 100,
            "km_ci95_pct": [float(np.percentile(d["km"], 2.5) * 100),
                            float(np.percentile(d["km"], 97.5) * 100)],
            "km_minus_lb_ci95_pp": [float(np.percentile(d["km"] - d["lb"], 2.5) * 100),
                                    float(np.percentile(d["km"] - d["lb"], 97.5) * 100)],
            "rank_lb_ci95": [int(np.percentile(d["rank_lb"], 2.5)),
                             int(np.percentile(d["rank_lb"], 97.5))],
            "rank_km_ci95": [int(np.percentile(d["rank_km"], 2.5)),
                             int(np.percentile(d["rank_km"], 97.5))],
            "prob_km_rank_better_than_lb_rank": float(np.mean(d["rank_km"] < d["rank_lb"])),
        }
        print(name, json.dumps(res[name]))
    (OUT / "real_case_uncertainty.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
