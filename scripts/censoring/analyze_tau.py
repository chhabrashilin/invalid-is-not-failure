"""Secondary censoring analysis on the tau-bench corpus.

Uses the SAME predeclared hazard grid, master seed, and estimators as the
primary SWE-agent analysis. Model eligibility is >= 100 labelled trajectories.

    uv run python scripts/censoring/analyze_tau.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
OUT_DIR = REPO_ROOT / "results" / "censoring"

from analyze import MASTER_SEED, N_REPLICATES, Q_GRID, analytic, monte_carlo  # noqa: E402

MIN_TRAJ_PER_MODEL_TAU = 100


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    rk = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1  # average rank for ties
        for k in range(i, j + 1):
            rk[order[k]] = avg
        i = j + 1
    return rk


def spearman(a, b):
    ra, rb = np.array(ranks(a)), np.array(ranks(b))
    ra -= ra.mean()
    rb -= rb.mean()
    d = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / d) if d else 1.0


def kendall_and_reversals(true_v, obs_v):
    """Kendall tau-b plus a strict-reversal count."""
    n = len(true_v)
    conc = disc = ties_t = ties_o = 0
    reversals = 0
    for i in range(n):
        for j in range(i + 1, n):
            dt = np.sign(true_v[i] - true_v[j])
            do = np.sign(obs_v[i] - obs_v[j])
            if dt == 0 and do == 0:
                ties_t += 1
                ties_o += 1
                continue
            if dt == 0:
                ties_t += 1
                continue
            if do == 0:
                ties_o += 1
                continue
            if dt == do:
                conc += 1
            else:
                disc += 1
                reversals += 1
    n0 = n * (n - 1) / 2
    denom = np.sqrt((n0 - ties_t) * (n0 - ties_o))
    tau = float((conc - disc) / denom) if denom else 1.0
    return tau, reversals, int(n0)


def main() -> int:
    tbl = pq.read_table(OUT_DIR / "tau_trajectory_summary.parquet")
    H = np.asarray(tbl.column("step_count")).astype(np.int64)
    score = np.asarray(tbl.column("score")).astype(float)
    model = np.asarray(tbl.column("model_path"))
    task = np.asarray(tbl.column("task_id"))
    domain = np.asarray(tbl.column("task_name"))

    # Y = 1 iff score == 1 (score verified strictly binary in tau_provenance.json)
    Y = (score == 1.0).astype(np.float64)
    n = len(Y)
    p = float(Y.mean())
    print(f"tau-bench n={n}  p_true={p:.6f}  meanH={H.mean():.2f}")
    print(f"  meanH|Y=1 {H[Y == 1].mean():.2f}  meanH|Y=0 {H[Y == 0].mean():.2f}")
    print(f"  medianH|Y=1 {np.median(H[Y == 1]):.1f}  medianH|Y=0 {np.median(H[Y == 0]):.1f}")
    print(f"  domains: {dict(zip(*np.unique(domain, return_counts=True)))}")

    analytic_rows = [analytic(H, Y, q) for q in Q_GRID]
    print(f"\n{'q':>7} {'p_drop':>9} {'p_fail':>9} {'bias_drop':>10} {'bias_fail':>10} {'retain':>7}")
    for r in analytic_rows:
        print(f"{r['q']:7.4f} {r['p_drop']:9.5f} {r['p_fail']:9.5f} "
              f"{r['bias_drop_pp']:+10.3f} {r['bias_fail_pp']:+10.3f} "
              f"{r['expected_retained_frac']:7.3f}")

    mc_rows = []
    for i, q in enumerate(Q_GRID):
        if q == 0.0:
            continue
        m = monte_carlo(H, Y, q, N_REPLICATES, MASTER_SEED + i)
        mc_rows.append(m)
        print(f"\nq={q}: retained={m['mean_retained_frac']:.3f}")
        for k in ("drop", "fail", "ht", "hajek"):
            print(f"   {k:6} bias={m[k]['bias_pp']:+.3f}pp sd={m[k]['sd_pp']:.3f}pp")

    # task-balanced (each task_id equally weighted across models)
    uniq_t, inv_t, cnt_t = np.unique(task, return_inverse=True, return_counts=True)
    tw = 1.0 / cnt_t[inv_t]
    task_rows = [analytic(H, Y, q, weights=tw) for q in Q_GRID]
    print(f"\ntask-balanced ({len(uniq_t)} unique task ids):")
    for r in task_rows:
        print(f"{r['q']:7.4f} p_true={r['p_true']:.5f} "
              f"bias_drop={r['bias_drop_pp']:+.3f} bias_fail={r['bias_fail_pp']:+.3f}")

    # ---------------- model-level ranking (30 models) ----------------
    models = sorted(set(model.tolist()))
    eligible = [m for m in models if (model == m).sum() >= MIN_TRAJ_PER_MODEL_TAU]
    model_rows = []
    for m in eligible:
        sel = model == m
        Hm, Ym = H[sel], Y[sel]
        row = {"model": m, "n": int(sel.sum()), "p_true": float(Ym.mean()),
               "mean_H": float(Hm.mean()), "median_H": float(np.median(Hm)),
               "mean_H_success": float(Hm[Ym == 1].mean()) if (Ym == 1).any() else None,
               "mean_H_failure": float(Hm[Ym == 0].mean()) if (Ym == 0).any() else None,
               "by_q": {}}
        for q in Q_GRID:
            a = analytic(Hm, Ym, q)
            row["by_q"][f"{q:.4f}"] = {"p_true": a["p_true"], "p_drop": a["p_drop"],
                                       "p_fail": a["p_fail"]}
        model_rows.append(row)
    model_rows.sort(key=lambda r: -r["p_true"])
    print(f"\neligible models: {len(model_rows)} (>= {MIN_TRAJ_PER_MODEL_TAU} trajectories)")
    for r in model_rows[:8]:
        print(f"   {r['model'][:40]:40} n={r['n']} p={r['p_true']:.4f} "
              f"H={r['mean_H']:5.1f} H|s={r['mean_H_success']:5.1f} H|f={r['mean_H_failure']:5.1f}")

    true_v = [r["p_true"] for r in model_rows]
    ranking_rows = []
    first_reversal = {"p_drop": None, "p_fail": None}
    for q in Q_GRID:
        rep = {"q": q, "n_eligible_models": len(model_rows)}
        for policy in ("p_drop", "p_fail"):
            obs = [r["by_q"][f"{q:.4f}"][policy] for r in model_rows]
            tau, rev, npairs = kendall_and_reversals(true_v, obs)
            rep[policy] = {"spearman_rho": spearman(true_v, obs), "kendall_tau": tau,
                           "pairwise_reversals": rev, "n_pairs": npairs}
            if rev > 0 and first_reversal[policy] is None:
                first_reversal[policy] = q
        ranking_rows.append(rep)
        print(f"  q={q:.4f} drop: rev={rep['p_drop']['pairwise_reversals']:3d}/"
              f"{rep['p_drop']['n_pairs']} rho={rep['p_drop']['spearman_rho']:.4f} "
              f"tau={rep['p_drop']['kendall_tau']:.4f} | "
              f"fail: rev={rep['p_fail']['pairwise_reversals']:3d} "
              f"rho={rep['p_fail']['spearman_rho']:.4f}")

    payload = {
        "kind": "tau_bench_censoring_analysis",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus": "AgentSuite/tau-bench-trajectories",
        "revision": "382e57d1784b55c5155f4ef394ef48f1c747a287",
        "predeclared": {"q_grid": Q_GRID, "master_seed": MASTER_SEED,
                        "n_replicates": N_REPLICATES,
                        "min_trajectories_per_model": MIN_TRAJ_PER_MODEL_TAU,
                        "outcome_rule": "Y = 1 iff eval_result.score == 1.0",
                        "horizon_rule": 'H = count of messages with role=="assistant"'},
        "population": {"n": n, "p_true": p, "mean_H": float(H.mean()),
                       "mean_H_success": float(H[Y == 1].mean()),
                       "mean_H_failure": float(H[Y == 0].mean()),
                       "median_H_success": float(np.median(H[Y == 1])),
                       "median_H_failure": float(np.median(H[Y == 0])),
                       "max_H": int(H.max())},
        "analytic": analytic_rows,
        "monte_carlo": mc_rows,
        "task_balanced": task_rows,
        "models": model_rows,
        "ranking": ranking_rows,
        "first_reversal_hazard": first_reversal,
    }
    (OUT_DIR / "tau_analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_DIR/'tau_analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
