"""Critical hazards for pairwise ranking reversals (extended paper).

Proposition (critical hazard). Under a constant per-step hazard q, agent A with
p_A > p_B falls below B under invalid-as-failure iff
    log(p_A/p_B) < log pbar1_B(q) - log pbar1_A(q).
A cumulant expansion of log E[s^H] with log s = log(1-q) gives
    log pbar1(q) = -q mu1 + (q^2/2)(var1 - mu1) + O(q^3),
so to first order the reversal hazard is
    q*_fail = log(p_A/p_B) / (mu1_A - mu1_B)      (if mu1_A > mu1_B),
where mu1 is the mean horizon of successful runs. For the complete case the
odds and the survival ratio play the same roles:
    q*_cc = log(odds_A/odds_B) / [(mu1_A - mu0_A) - (mu1_B - mu0_B)].
We compare first- and second-order predictions with the exact reversal hazard
(computed on a fine logarithmic grid) for every model pair in four corpora.

    uv run python scripts/extended/critical_hazard.py
"""

from __future__ import annotations

import csv
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from frontier_analysis import load as load_frontier, short  # noqa: E402

RES = REPO_ROOT / "results"
OUT = RES / "extended"
QGRID = np.unique(np.concatenate([np.geomspace(1e-5, 0.05, 1200)]))


def corpora():
    out = {}
    sub, H, Y, cost, st, cls = load_frontier()
    k = cls == "outcome"
    out["frontier (SWE-bench Verified, bash-only)"] = (H[k], Y[k], sub[k])
    rows = list(csv.DictReader(open(OUT / "multilingual_runs.csv", encoding="utf-8")))
    out["frontier (SWE-bench Multilingual)"] = (
        np.array([int(float(r["api_calls"])) for r in rows]),
        np.array([r["resolved"] == "True" for r in rows], dtype=float),
        np.array([r["submission"] for r in rows]))
    t = pq.read_table(RES / "censoring" / "tau_trajectory_summary.parquet")
    out["tau-bench"] = (np.asarray(t.column("step_count")).astype(int),
                        (np.asarray(t.column("score")).astype(float) == 1).astype(float),
                        np.asarray(t.column("model_path")).astype(str))
    s = pq.read_table(RES / "censoring" / "trajectory_summary.parquet")
    out["SWE-agent"] = (np.asarray(s.column("step_count")).astype(int),
                        np.asarray(s.column("target")).astype(float),
                        np.asarray(s.column("model_name")).astype(str))
    return out


def model_stats(H, Y, M, min_n):
    names = [m for m in sorted(set(M.tolist())) if (M == m).sum() >= min_n]
    st = []
    for m in names:
        h, y = H[M == m], Y[M == m]
        if y.sum() == 0 or y.sum() == len(y):
            continue
        s = 1.0 - QGRID[:, None]
        pb1 = (s ** h[y == 1][None, :]).mean(axis=1)
        pb0 = (s ** h[y == 0][None, :]).mean(axis=1)
        st.append({"model": m, "p": y.mean(),
                   "mu1": h[y == 1].mean(), "mu0": h[y == 0].mean(),
                   "v1": h[y == 1].var(), "v0": h[y == 0].var(),
                   "pb1": pb1, "pb0": pb0})
    return st


def smallest_root(a, b, c):
    """Smallest positive root of a + b q + c q^2 = 0 (a > 0 means no reversal
    at q = 0); None if none."""
    if abs(c) < 1e-15:
        return (-a / b) if b < 0 else None
    disc = b * b - 4 * c * a
    if disc < 0:
        return None
    r = sorted([(-b - np.sqrt(disc)) / (2 * c), (-b + np.sqrt(disc)) / (2 * c)])
    pos = [x for x in r if x > 0]
    return pos[0] if pos else None


def pair_table(st):
    rows = []
    for A, B in combinations(st, 2):
        if A["p"] == B["p"]:
            continue
        if A["p"] < B["p"]:
            A, B = B, A
        # invalid-as-failure
        f = np.log(A["p"] * A["pb1"]) - np.log(B["p"] * B["pb1"])
        ex_f = QGRID[np.argmax(f < 0)] if (f < 0).any() else None
        a = np.log(A["p"] / B["p"])
        b1 = -(A["mu1"] - B["mu1"])
        c2 = 0.5 * ((A["v1"] - A["mu1"]) - (B["v1"] - B["mu1"]))
        fo_f = a / (A["mu1"] - B["mu1"]) if A["mu1"] > B["mu1"] else None
        so_f = smallest_root(a, b1, c2)
        # complete case
        oddsA, oddsB = A["p"] / (1 - A["p"]), B["p"] / (1 - B["p"])
        g = (np.log(oddsA) + np.log(A["pb1"] / A["pb0"])
             - np.log(oddsB) - np.log(B["pb1"] / B["pb0"]))
        ex_c = QGRID[np.argmax(g < 0)] if (g < 0).any() else None
        a2 = np.log(oddsA / oddsB)
        dA, dB = A["mu1"] - A["mu0"], B["mu1"] - B["mu0"]
        fo_c = a2 / (dA - dB) if dA > dB else None
        rows.append({"A": A["model"], "B": B["model"], "pA": A["p"], "pB": B["p"],
                     "exact_fail": ex_f, "first_fail": fo_f, "second_fail": so_f,
                     "exact_cc": ex_c, "first_cc": fo_c})
    return rows


def accuracy(rows, ex, pred):
    both = [(r[ex], r[pred]) for r in rows if r[ex] is not None and r[pred] is not None]
    miss = sum(1 for r in rows if r[ex] is not None and r[pred] is None)
    false = sum(1 for r in rows if r[ex] is None and r[pred] is not None and r[pred] < QGRID[-1])
    if len(both) < 3:
        return {"n": len(both)}
    e = np.log10([x for x, _ in both])
    p = np.log10([y for _, y in both])
    rk = lambda v: np.argsort(np.argsort(v))
    rho = float(np.corrcoef(rk(e), rk(p))[0, 1])
    return {"n_both": len(both), "spearman_log": rho,
            "median_abs_log10_ratio": float(np.median(np.abs(p - e))),
            "share_within_factor_2": float(np.mean(np.abs(p - e) < np.log10(2))),
            "reversing_but_predicted_never": miss,
            "predicted_but_never_reverses_by_5pct": false}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"qgrid": [float(QGRID[0]), float(QGRID[-1]), len(QGRID)], "corpora": {}}
    scatter = {}
    for name, (H, Y, M) in corpora().items():
        min_n = 100 if name != "SWE-agent" else 500
        st = model_stats(H, Y, M, min_n)
        rows = pair_table(st)
        n = len(rows)
        ex_f = [r["exact_fail"] for r in rows if r["exact_fail"] is not None]
        adj = []
        order = sorted(st, key=lambda s: -s["p"])
        names_adj = {(order[i]["model"], order[i + 1]["model"]) for i in range(len(order) - 1)}
        adj = [r["exact_fail"] for r in rows if (r["A"], r["B"]) in names_adj]
        rep = {"n_models": len(st), "n_pairs": n,
               "pairs_reversing_by_5pct_fail": len(ex_f),
               "pairs_reversing_by_5pct_cc": sum(r["exact_cc"] is not None for r in rows),
               "median_exact_q_fail_among_reversing": float(np.median(ex_f)) if ex_f else None,
               "adjacent_pairs": len(adj),
               "adjacent_median_exact_q_fail": float(np.median([a for a in adj if a is not None]))
               if any(a is not None for a in adj) else None,
               "adjacent_share_reversing_below_0.1pct": float(np.mean(
                   [a is not None and a <= 0.001 for a in adj])) if adj else None,
               "first_order_fail": accuracy(rows, "exact_fail", "first_fail"),
               "second_order_fail": accuracy(rows, "exact_fail", "second_fail"),
               "first_order_cc": accuracy(rows, "exact_cc", "first_cc"),
               "adjacent_exact_fail": [None if a is None else float(a) for a in adj]}
        report["corpora"][name] = rep
        scatter[name] = [(r["exact_fail"], r["first_fail"]) for r in rows
                         if r["exact_fail"] is not None and r["first_fail"] is not None]
        print(f"\n== {name}: {len(st)} models, {n} pairs; reversing by 5% (fail) "
              f"{len(ex_f)}, (cc) {rep['pairs_reversing_by_5pct_cc']}")
        print(f"   adjacent pairs {len(adj)}: median exact q* {rep['adjacent_median_exact_q_fail']}, "
              f"share <= 0.1% {rep['adjacent_share_reversing_below_0.1pct']}")
        for k in ("first_order_fail", "second_order_fail", "first_order_cc"):
            print(f"   {k}: {rep[k]}")
    (OUT / "critical_hazard.json").write_text(
        json.dumps({"report": report, "scatter": scatter}, indent=1,
                   default=lambda o: o.item() if hasattr(o, "item") else str(o)),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
