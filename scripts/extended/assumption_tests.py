"""Real-data tests of the independent-failure assumption (extended paper).

Weighting assumes an invalidated run would have succeeded as often as a
completed run that reached the same step (gamma = 1 in the sensitivity model).
Two public data structures let us check this without running any agent.

(a) SWE-agent corpus, container failures (early_exit). Each task x model cell
    holds many repeated runs. The completed runs in a crashed run's cell
    estimate that run's success probability under within-cell exchangeability,
    which is weaker than global independence. We compare this cell-based
    imputation with the independence (step-based) imputation, report the
    reliability estimate it implies, and back out the gamma that reconciles
    the two.

(b) Frontier corpus, provider failures. Other models' results on the same
    task measure task difficulty. We test whether provider failures hit harder
    tasks and impute each censored run from a difficulty model fitted on the
    same submission's completed runs.

    uv run python scripts/extended/assumption_tests.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "censoring"))
from frontier_analysis import load as load_frontier, short  # noqa: E402
from sensitivity import imputed_mar  # noqa: E402

OUT = REPO_ROOT / "results" / "extended"
MIN_CELL = 3


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def expit(x):
    return 1 / (1 + np.exp(-x))


def implied_gamma(m_mar, target_mean):
    """gamma such that mean(expit(logit m + log gamma)) = target_mean."""
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if expit(logit(m_mar) + mid).mean() < target_mean:
            lo = mid
        else:
            hi = mid
    return float(np.exp((lo + hi) / 2))


def fit_logistic_1d(x, y, iters=50):
    X = np.column_stack([np.ones_like(x), x])
    b = np.zeros(2)
    for _ in range(iters):
        mu = expit(X @ b)
        W = mu * (1 - mu) + 1e-9
        b += np.linalg.solve((X * W[:, None]).T @ X + 1e-6 * np.eye(2), X.T @ (y - mu))
    return b


def swe_cells():
    t = pq.read_table(REPO_ROOT / "results" / "censoring" / "trajectory_summary.parquet")
    H = np.asarray(t.column("step_count")).astype(np.int64)
    Y = np.asarray(t.column("target")).astype(float)
    E = np.asarray(t.column("exit_status")).astype(str) == "early_exit"
    cell = np.char.add(np.char.add(np.asarray(t.column("instance_id")).astype(str), "||"),
                       np.asarray(t.column("model_name")).astype(str))
    _, inv = np.unique(cell, return_inverse=True)
    C = ~E
    n_c = np.bincount(inv, weights=C.astype(float))
    s_c = np.bincount(inv, weights=(Y * C))
    N = len(Y)
    m_mar = imputed_mar(H, Y, E)                    # independence imputation
    r_cell = np.where(n_c[inv] >= MIN_CELL, s_c[inv] / np.maximum(n_c[inv], 1), np.nan)[E]
    have = ~np.isnan(r_cell)
    # difficulty bands: cell success among completed runs
    diff = np.where(n_c >= MIN_CELL, s_c / np.maximum(n_c, 1), np.nan)
    band_edges = [0, 1e-9, 0.1, 0.3, 0.6, 1.0001]
    bands = []
    cell_rate_run = diff[inv]
    for lo_, hi_ in zip(band_edges[:-1], band_edges[1:]):
        sel = (cell_rate_run >= lo_) & (cell_rate_run < hi_)
        if sel.sum():
            bands.append({"cell_success": f"[{lo_:.1f},{hi_:.1f})" if lo_ > 0 else "0",
                          "runs": int(sel.sum()), "early_exit_rate_pct": float(E[sel].mean() * 100)})
    p_cell = (Y[C].sum() + np.where(have, r_cell, m_mar).sum()) / N
    res = {
        "n_censored": int(E.sum()), "censored_with_cell_data": int(have.sum()),
        "mean_success_completed_pct": float(Y[C].mean() * 100),
        "mean_imputed_independence_pct": float(m_mar[have].mean() * 100),
        "mean_imputed_cell_pct": float(r_cell[have].mean() * 100),
        "implied_gamma": implied_gamma(m_mar[have], r_cell[have].mean()),
        "estimate_cell_imputation_pct": float(p_cell * 100),
        "early_exit_rate_by_cell_difficulty": bands,
    }
    return res


def frontier_difficulty():
    sub, H, Y, cost, st, cls = load_frontier()
    subs = sorted(set(sub.tolist()))
    tasks = sorted(set())
    # per-task resolution of every submission (valid outcome runs only)
    import collections
    inst = []
    import csv
    rows = list(csv.DictReader(open(OUT / "bash_only_runs.csv", encoding="utf-8")))
    excl = set(json.loads((OUT / "frontier_analysis.json").read_text())["excluded"])
    rows = [r for r in rows if r["submission"] not in excl]
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["submission"]][r["instance_id"]] = r
    out = {}
    for s in subs:
        runs = by[s]
        cens = [i for i, r in runs.items() if r["exit_status"] in
                ("APIError", "RetryError", "ServiceUnavailableError")]
        if len(cens) < 5:
            continue
        others = [o for o in subs if o != s]
        def difficulty(i):
            ys = [by[o][i]["resolved"] == "True" for o in others
                  if i in by[o] and by[o][i]["exit_status"] not in
                  ("APIError", "RetryError", "ServiceUnavailableError")]
            return np.mean(ys) if ys else np.nan
        comp = [i for i in runs if i not in cens]
        d_c = np.array([difficulty(i) for i in cens])
        d_o = np.array([difficulty(i) for i in comp])
        y_o = np.array([runs[i]["resolved"] == "True" for i in comp], dtype=float)
        b = fit_logistic_1d(logit(d_o), y_o)
        p_cens = expit(b[0] + b[1] * logit(d_c))
        N = len(runs)
        est = (y_o.sum() + p_cens.sum()) / N
        # independence (step-based) imputation for the same runs
        Hs = np.array([int(float(runs[i]["api_calls"])) for i in list(runs)])
        Ys = np.array([0.0 if i in cens else float(runs[i]["resolved"] == "True") for i in runs])
        Es = np.array([i in cens for i in runs])
        m_mar = imputed_mar(Hs, Ys, Es)
        # step + difficulty: among completed runs that reached the failure step
        # (H >= v), regress success on task difficulty with Kaplan-Meier
        # weights, then predict at the censored task's difficulty. Under
        # T independent of Y given H, difficulty should add nothing beyond the
        # step; a shift is evidence against independence.
        from revision_analysis import km_censoring_survival
        order_ids = list(runs)
        d_all = np.array([difficulty(i) for i in order_ids])
        G = km_censoring_survival(Hs, Es, int(Hs.max()) + 1)
        w_all = np.where(~Es, 1.0 / np.where(G[Hs] > 0, G[Hs], np.inf), 0.0)
        p_sd = []
        for k, i in enumerate(order_ids):
            if not Es[k]:
                continue
            v = Hs[k]
            tr = (~Es) & (Hs >= v) & ~np.isnan(d_all)
            yt = Ys[tr]
            if tr.sum() >= 10 and 0 < yt.sum() < tr.sum():
                X = np.column_stack([np.ones(tr.sum()), logit(d_all[tr])])
                b2 = np.zeros(2)
                wt = w_all[tr]
                for _ in range(50):
                    mu = expit(X @ b2)
                    W = wt * mu * (1 - mu) + 1e-9
                    b2 += np.linalg.solve((X * W[:, None]).T @ X + 1e-6 * np.eye(2),
                                          X.T @ (wt * (yt - mu)))
                p_sd.append(float(expit(b2[0] + b2[1] * logit(d_all[k]))))
            else:
                p_sd.append(float(yt.mean()) if tr.sum() else 0.0)
        p_sd = np.array(p_sd)
        est_sd = (y_o.sum() + p_sd.sum()) / N
        out[short(s)] = {
            "mean_imputed_step_and_difficulty_pct": float(p_sd.mean() * 100),
            "estimate_step_and_difficulty_pct": float(est_sd * 100),
            "implied_gamma_step_and_difficulty": implied_gamma(m_mar, p_sd.mean()),
            "censored": len(cens),
            "mean_difficulty_censored_tasks": float(np.nanmean(d_c)),
            "mean_difficulty_completed_tasks": float(np.nanmean(d_o)),
            "mean_imputed_difficulty_pct": float(p_cens.mean() * 100),
            "mean_imputed_independence_pct": float(m_mar.mean() * 100),
            "implied_gamma": implied_gamma(m_mar, p_cens.mean()),
            "estimate_difficulty_imputation_pct": float(est * 100),
            "slope_logit": float(b[1]),
        }
    return out


def main() -> int:
    res = {"swe_agent_early_exit": swe_cells(), "frontier_provider": frontier_difficulty()}
    print(json.dumps(res, indent=1))
    (OUT / "assumption_tests.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
