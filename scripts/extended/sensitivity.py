"""Sensitivity of real-censoring estimates to outcome-dependent (MNAR)
censoring (extended paper).

For a run invalidated at step v, its success probability under independent
censoring is m(v) = P(Y=1 | H >= v), estimated from completed runs of the same
agent with Kaplan-Meier weights. We tilt its odds by gamma:
logit P(Y=1 | invalidated at v) = logit m(v) + log gamma. gamma = 1 is the
independent-censoring estimate, gamma -> 0 recovers the invalid-as-failure
lower bound, gamma -> infinity the upper bound. For each real case we report
p(gamma) and the tipping gammas at which the leaderboard position changes.

    uv run python scripts/extended/sensitivity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "censoring"))
sys.path.insert(0, str(Path(__file__).parent))
from revision_analysis import km_censoring_survival  # noqa: E402
from frontier_analysis import load as load_frontier, short  # noqa: E402

OUT = REPO_ROOT / "results" / "extended"
GAMMAS = np.exp(np.linspace(np.log(1 / 64), np.log(64), 241))


def imputed_mar(H, Y, E):
    """m(v) for each invalidated run: KM-weighted success rate among completed
    runs with horizon >= v."""
    G = km_censoring_survival(H, E, int(H.max()) + 1)
    C = ~E
    w = np.where(C, 1.0 / np.where(G[H] > 0, G[H], np.inf), 0.0)
    order = np.argsort(H)
    Hs, ws, wys = H[order], w[order], (w * Y)[order]
    # suffix sums over completed runs with H >= v
    suf_w = np.concatenate([np.cumsum(ws[::-1])[::-1], [0.0]])
    suf_wy = np.concatenate([np.cumsum(wys[::-1])[::-1], [0.0]])
    pos = np.searchsorted(Hs, H[E], side="left")
    return np.clip(suf_wy[pos] / np.maximum(suf_w[pos], 1e-12), 1e-6, 1 - 1e-6)


def p_of_gamma(Y, E, m):
    """Reliability with censored runs imputed at tilted probabilities."""
    lo = np.log(m / (1 - m))
    out = []
    for g in GAMMAS:
        pe = 1 / (1 + np.exp(-(lo + np.log(g))))
        out.append((Y[~E].sum() + pe.sum()) / len(Y))
    return np.array(out)


def main() -> int:
    res = {"gammas": GAMMAS.tolist()}

    # SWE-agent early_exit (Nebius corpus)
    t = pq.read_table(REPO_ROOT / "results" / "censoring" / "trajectory_summary.parquet")
    H = np.asarray(t.column("step_count")).astype(np.int64)
    Y = np.asarray(t.column("target")).astype(float)
    E = np.asarray(t.column("exit_status")).astype(str) == "early_exit"
    m = imputed_mar(H, Y, E)
    pg = p_of_gamma(Y, E, m)
    res["swe_early_exit"] = {"p_gamma": pg.tolist(),
                             "p_at": {str(g): float(np.interp(np.log(g), np.log(GAMMAS), pg))
                                      for g in (0.25, 0.5, 1, 2, 4)}}
    print("SWE early_exit p(gamma):", {k: round(v * 100, 2)
                                       for k, v in res["swe_early_exit"]["p_at"].items()})

    # frontier leaderboard: every submission with provider-censored runs
    sub, Hf, Yf, cost, st, cls = load_frontier()
    subs = sorted(set(sub.tolist()))
    score = {s: Yf[sub == s].mean() for s in subs}
    res["frontier"] = {}
    for s in subs:
        msk = sub == s
        Es = cls[msk] == "censored"
        if Es.sum() < 5:
            continue
        # outcomes of censored runs are unknown: drop their recorded labels
        Ys = np.where(Es, 0.0, Yf[msk])
        ms = imputed_mar(Hf[msk], Ys, Es)
        pg = p_of_gamma(Ys, Es, ms)
        others = np.array([score[o] for o in subs if o != s])
        rank = 1 + (others[None, :] > pg[:, None]).sum(axis=1)
        lb_rank = 1 + int((others > score[s]).sum())
        changes = [{"gamma": float(g), "rank": int(r)} for g, r, r0 in
                   zip(GAMMAS[1:], rank[1:], rank[:-1]) if r != r0]
        # tipping points closest to gamma = 1 on each side
        at1 = int(rank[np.argmin(np.abs(np.log(GAMMAS)))])
        res["frontier"][short(s)] = {
            "M_censored": int(Es.sum()), "leaderboard_score": float(score[s]),
            "leaderboard_rank": lb_rank, "rank_at_gamma1": at1,
            "p_at": {str(g): float(np.interp(np.log(g), np.log(GAMMAS), pg))
                     for g in (0.25, 0.5, 1, 2, 4)},
            "rank_range_gamma_quarter_to_4": [
                int(rank[(GAMMAS >= 0.25) & (GAMMAS <= 4)].min()),
                int(rank[(GAMMAS >= 0.25) & (GAMMAS <= 4)].max())],
            "rank_changes": changes}
        r = res["frontier"][short(s)]
        print(f"{short(s)[:30]:30} M={r['M_censored']:3d} lb={r['leaderboard_score']*100:.1f} "
              f"rank {r['leaderboard_rank']} -> {r['rank_at_gamma1']} (gamma=1); "
              f"p(.25..4)={[round(v*100,1) for v in r['p_at'].values()]} "
              f"rank range {r['rank_range_gamma_quarter_to_4']}")
    (OUT / "sensitivity.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
