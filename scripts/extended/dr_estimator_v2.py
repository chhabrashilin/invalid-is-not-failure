"""Doubly robust estimation with richer prefixes and a flexible outcome model
(extended paper, second iteration).

Adds to dr_estimator.py:
  * prefix signals read from the trajectory text: observations that look like
    passing tests or a successful run, actions that run tests, actions that
    run or create a reproduction script, and whether a passing observation
    followed the most recent edit;
  * a gradient-boosted outcome model (scikit-learn HistGradientBoosting) next
    to logistic regression;
  * out-of-fold AUC (two task-level folds), so discrimination is measured on
    tasks the model did not see.

    uv run --with scikit-learn python scripts/extended/dr_estimator_v2.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dr_estimator import (EDIT, OUT, RUN, SEED, auc, build_features, dr_estimate,  # noqa: E402
                          draw_T, fit_logistic, load, predict)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "censoring"))
from revision_analysis import km_censoring_survival  # noqa: E402

N_REP = 30
SCENARIOS = [(0.02, False), (0.01, True)]


def rich_features(H, model, codes, obs_err, edit_fail, obs_pass, cmd_test, cmd_repro):
    X, run_of, t, start, names = build_features(H, model, codes, obs_err, edit_fail)
    n_steps = len(t)
    idx = np.arange(n_steps)

    def run_exclusive_count(flag):
        c = np.concatenate([[0], np.cumsum(flag.astype(np.int64))])
        return c[idx] - c[start]

    prev = np.maximum(idx - 1, 0)
    first = t == 1
    n_pass = run_exclusive_count(obs_pass == 1)
    n_test = run_exclusive_count(cmd_test == 1)
    n_repro = run_exclusive_count(cmd_repro == 1)
    last_pass = np.where(first, 0, obs_pass[prev])
    edit_pos = np.where(codes == EDIT, idx, -1)
    pass_pos = np.where(obs_pass == 1, idx, -1)
    le = np.where(first, -1, np.maximum.accumulate(edit_pos)[prev])
    lp = np.where(first, -1, np.maximum.accumulate(pass_pos)[prev])
    le = np.where(le >= start, le, -1)
    lp = np.where(lp >= start, lp, -1)
    pass_after_edit = ((le >= 0) & (lp > le)).astype(float)
    extra = np.column_stack([np.log1p(n_pass), np.log1p(n_test), np.log1p(n_repro),
                             last_pass, pass_after_edit,
                             pass_after_edit * np.log1p(t - 1)])
    return (np.hstack([X, extra]), run_of, t, start,
            names + ["log_pass_obs", "log_test_cmds", "log_repro_cmds", "last_obs_pass",
                     "pass_after_last_edit", "pass_after_edit_x_log_steps"])


def make_model(kind):
    if kind == "logistic":
        return None
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=150, learning_rate=0.1,
                                          max_leaf_nodes=31, l2_regularization=1.0,
                                          random_state=SEED)


def fit_predict(kind, Xtr, ytr, wtr, Xte, beta0=None):
    if kind == "logistic":
        b = fit_logistic(Xtr, ytr, wtr, beta0=beta0)
        return predict(Xte, b), b
    m = make_model(kind)
    m.fit(Xtr[:, 1:], ytr, sample_weight=wtr)
    return m.predict_proba(Xte[:, 1:])[:, 1], None


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="all", choices=["all", "auc", "0", "1"],
                    help="run only the AUC analysis or one scenario; results are "
                         "merged into dr_estimator_v2.json")
    part = ap.parse_args().part
    H, Y, model, task, exits, codes, obs_err, edit_fail = load()
    z = np.load(OUT / "swe_prefix_records.npz")
    X, run_of, t_rows, start, names = rich_features(
        H, model, codes, obs_err, edit_fail, z["obs_pass"], z["cmd_test"], z["cmd_repro"])
    N, p, hmax = len(Y), Y.mean(), int(H.max()) + 1
    uniq, inv = np.unique(task, return_inverse=True)
    fold_task = np.random.default_rng(SEED).integers(0, 2, len(uniq))
    folds_run = fold_task[inv]
    fold_rows = folds_run[run_of]
    print(f"N={N} rows={len(X)} features={len(names)}")
    path = OUT / "dr_estimator_v2.json"
    payload = (json.loads(path.read_text(encoding="utf-8")) if path.exists() else
               {"kind": "doubly_robust_v2", "seed": SEED, "n_rep": N_REP,
                "simulation": [None] * len(SCENARIOS)})
    payload["features"] = names

    # out-of-fold discrimination on uncensored data (own random stream)
    auc_oof = {}
    rng_sub = np.random.default_rng(SEED + 3)
    for kind in (("logistic", "gbm") if part in ("all", "auc") else ()):
        mu = np.empty(len(X))
        for fold in (0, 1):
            tr = np.flatnonzero(fold_rows != fold)
            tr = tr[rng_sub.random(len(tr)) < 0.25]
            te = fold_rows == fold
            mu[te], _ = fit_predict(kind, X[tr], Y[run_of[tr]], np.ones(len(tr)), X[te])
        auc_oof[kind] = {tt: auc(mu[t_rows == tt], Y[run_of[t_rows == tt]])
                         for tt in (1, 5, 10, 20, 40)}
        print(kind, "out-of-fold AUC", {k: round(v, 3) for k, v in auc_oof[kind].items()})
    if auc_oof:
        payload["auc_out_of_fold"] = auc_oof

    for si, (q0, stepdep) in enumerate(SCENARIOS):
        if part not in ("all", str(si)):
            continue
        est = {k: [] for k in ("km_hajek", "param_hajek", "dr_km_logistic", "dr_km_gbm",
                               "dr_param_logistic", "dr_param_gbm")}
        rng = np.random.default_rng(SEED + 700 + si)
        rng_sub = np.random.default_rng(SEED + 3 + 100 * (si + 1))  # per-scenario stream
        t0 = time.time()
        for r in range(N_REP):
            T = draw_T(rng, N, q0, stepdep)
            C = T > H
            V = np.where(C, H, T)
            G_km = km_censoring_survival(V, ~C, hmax)
            qhat = (~C).sum() / V.sum()
            G_par = (1 - qhat) ** np.arange(hmax + 1)
            for gname, G in (("km", G_km), ("param", G_par)):
                Gprev = np.concatenate([[1.0], G])
                for kind in ("logistic", "gbm"):
                    mu = np.empty(len(X))
                    for fold in (0, 1):
                        tr = np.flatnonzero(C[run_of] & (fold_rows != fold))
                        tr = tr[rng_sub.random(len(tr)) < 0.25]
                        w = Gprev[t_rows[tr]] / G[H[run_of[tr]]]
                        te = fold_rows == fold
                        mu[te], _ = fit_predict(kind, X[tr], Y[run_of[tr]], w, X[te])
                    psi, hajek = dr_estimate(Y, H, C, V, T, G, mu, run_of, t_rows)
                    est[f"dr_{gname}_{kind}"].append(psi)
                est[f"{gname}_hajek"].append(hajek)
            if (r + 1) % 5 == 0:
                print(f"  scenario {si} rep {r + 1} ({time.time() - t0:.0f}s)", flush=True)
        row = {"q0": q0, "hazard": "step-dependent" if stepdep else "constant", "n_rep": N_REP}
        for k, v in est.items():
            v = np.asarray(v)
            row[k] = {"bias_pp": float((v.mean() - p) * 100), "sd_pp": float(v.std(ddof=1) * 100),
                      "rmse_pp": float(np.sqrt(((v - p) ** 2).mean()) * 100)}
        payload["simulation"][si] = row
        print(f"q0={q0} {row['hazard']}: " + "  ".join(
            f"{k}={row[k]['bias_pp']:+.3f}({row[k]['sd_pp']:.3f})" for k in est))
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")  # save each part

    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
