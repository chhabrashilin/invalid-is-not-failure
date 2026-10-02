"""Rank confidence sets: sampling uncertainty + identification uncertainty.

Phase 2A companion to the extended paper *Invalid Is Not Failure*.

For a fixed task sample, each submission has an identified success interval
[lo, hi] (strict or broad). Sharp rank intervals follow Proposition (rank) in
the paper: best = 1 + #{k: lo_k > hi_j}, worst = 1 + #{k!=j: hi_k > lo_j}.

Sampling uncertainty: resample the N tasks jointly (same indices for every
submission), recompute [lo, hi] and sharp rank intervals on each bootstrap
draw. The reported 95% rank confidence set for submission j is the envelope
  [percentile_2.5(best^b), percentile_97.5(worst^b)].
Pairwise ordering A above B is called *supported* at level 95% when the
bootstrap frequency of the identification event lo_A > hi_B is at least 95%.

This is a transparent, conservative combination of partial identification and
a paired task bootstrap. It is related in spirit to work on inference for
ranks (likely Mogstad, Romano, Shaikh, Wilhelm - VERIFY before citing) and
to sample-selection / missing-outcome bounds (likely Lee - VERIFY before
citing). Do not treat those citations as verified from this file.

Usage:
  uv run python scripts/extended/rank_confidence.py
  uv run python scripts/extended/rank_confidence.py --split swebench/verified --B 1000
  uv run python scripts/extended/rank_confidence.py --sim-only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from census_leaderboard import MSWE_LANGS, SWE_EVAL, SWE_N, SWE_UNATTR  # noqa: E402

OUT = REPO_ROOT / "results" / "extended"
DEFAULT_B = 2000
DEFAULT_SEED = 20261001
ALPHA = 0.05


def sharp_rank_intervals(lo: np.ndarray, hi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(lo)
    best = 1 + (lo[None, :] > hi[:, None]).sum(axis=1)
    worst = 1 + ((hi[None, :] > lo[:, None]) & ~np.eye(n, dtype=bool)).sum(axis=1)
    return best.astype(int), worst.astype(int)


def identified_matrix(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    return lo[:, None] > hi[None, :]


def rows_to_status(rows: list[dict]) -> tuple[list[str], np.ndarray, int]:
    """Return (names, status[J,T], N).

    status: 0 = observed failure, 1 = resolved, 2 = eval-censored (E),
    3 = unattributable (U). Structural missing counts become shared pad
    columns marked U only for submissions that still need them.
    """
    if not rows:
        raise ValueError("no submissions")
    N = int(rows[0]["N"])
    if any(int(r["N"]) != N for r in rows):
        raise ValueError("mixed N within split; refuse joint bootstrap")
    if "E_ids" not in rows[0] or "U_ids" not in rows[0]:
        raise ValueError("rows need E_ids and U_ids for bootstrap")

    all_ids: set[str] = set()
    for r in rows:
        all_ids |= set(r["R"]) | set(r["E_ids"]) | set(r["U_ids"])

    tasks = sorted(all_ids)
    if len(tasks) > N:
        tasks = tasks[:N]
    pads = [f"__pad_{i}" for i in range(N - len(tasks))]
    tasks = tasks + pads
    ti = {t: k for k, t in enumerate(tasks)}
    J = len(rows)
    status = np.zeros((J, N), dtype=np.int8)
    names = []
    need_u = []
    for a, r in enumerate(rows):
        names.append(r["submission"])
        for t in r["R"]:
            if t in ti:
                status[a, ti[t]] = 1
        for t in r["E_ids"]:
            if t in ti and status[a, ti[t]] == 0:
                status[a, ti[t]] = 2
        for t in r["U_ids"]:
            if t in ti and status[a, ti[t]] == 0:
                status[a, ti[t]] = 3
        already = int((status[a] == 3).sum())
        need_u.append(max(0, int(r["U"]) - already))

    for pad in pads:
        col = ti[pad]
        for a in range(J):
            if need_u[a] > 0:
                status[a, col] = 3
                need_u[a] -= 1
    return names, status, N


def load_swe_ids(split: str) -> list[dict]:
    RAW = REPO_ROOT / "data" / "raw"
    rows = []
    N = SWE_N[split]
    for f in sorted((RAW / "swebench_experiments" / split).glob("*/results.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        R = d.get("resolved", [])
        if not isinstance(R, list):
            continue
        R = set(R)
        E = set().union(*(set(d.get(k, [])) for k in SWE_EVAL)) - R
        U = set().union(*(set(d.get(k, [])) for k in SWE_UNATTR)) - R - E
        rows.append({
            "submission": f.parent.name,
            "N": N,
            "R": R,
            "E": len(E),
            "U": len(U),
            "E_ids": E,
            "U_ids": U,
            "missing_n": 0,
        })
    return rows


def load_mswe_ids(lang: str) -> list[dict]:
    RAW = REPO_ROOT / "data" / "raw"
    rows = []
    for f in sorted((RAW / "multi_swe_bench" / lang / "verified").glob("*/results.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        N = int(d["total_instances"])
        R = set(d["resolved"])
        C = set(d.get("completed_ids", []))
        E = (set(d.get("incomplete_ids", [])) | set(d.get("error_ids", []))) - R
        Ul = (set(d.get("empty_error_patch_ids", [])) | set(d.get("empty_patch_ids", []))) - R - E
        missing_n = max(0, N - len(C | E | Ul))
        rows.append({
            "submission": f.parent.name,
            "N": N,
            "R": R,
            "E": len(E),
            "U": len(Ul) + missing_n,
            "E_ids": E,
            "U_ids": Ul,
            "missing_n": missing_n,
        })
    return rows


def intervals_from_status(status: np.ndarray, reading: str) -> tuple[np.ndarray, np.ndarray]:
    T = status.shape[1]
    resolved = (status == 1).sum(axis=1).astype(float)
    e = (status == 2).sum(axis=1).astype(float)
    u = (status == 3).sum(axis=1).astype(float)
    lo = resolved / T
    if reading == "strict":
        hi = (resolved + e) / T
    elif reading == "broad":
        hi = (resolved + e + u) / T
    else:
        raise ValueError(reading)
    return lo, hi


def bootstrap_rank_confidence(
    status: np.ndarray,
    reading: str = "strict",
    B: int = DEFAULT_B,
    seed: int = DEFAULT_SEED,
    alpha: float = ALPHA,
) -> dict:
    J, T = status.shape
    rng = np.random.default_rng(seed)
    lo0, hi0 = intervals_from_status(status, reading)
    best0, worst0 = sharp_rank_intervals(lo0, hi0)
    ident0 = identified_matrix(lo0, hi0)

    best_draws = np.empty((B, J), dtype=int)
    worst_draws = np.empty((B, J), dtype=int)
    support_count = np.zeros((J, J), dtype=np.int32)

    for b in range(B):
        idx = rng.integers(0, T, size=T)
        lo, hi = intervals_from_status(status[:, idx], reading)
        best, worst = sharp_rank_intervals(lo, hi)
        best_draws[b] = best
        worst_draws[b] = worst
        support_count += identified_matrix(lo, hi).astype(np.int32)

    lo_q = 100 * (alpha / 2)
    hi_q = 100 * (1 - alpha / 2)
    rank_ci_int = np.stack([
        np.floor(np.percentile(best_draws, lo_q, axis=0)).astype(int),
        np.ceil(np.percentile(worst_draws, hi_q, axis=0)).astype(int),
    ], axis=1)
    rank_ci_int[:, 0] = np.clip(rank_ci_int[:, 0], 1, J)
    rank_ci_int[:, 1] = np.clip(rank_ci_int[:, 1], 1, J)

    support_freq = support_count / B
    supported = support_freq >= (1 - alpha)
    width_point = worst0 - best0
    width_ci = rank_ci_int[:, 1] - rank_ci_int[:, 0]

    return {
        "reading": reading,
        "B": B,
        "seed": seed,
        "alpha": alpha,
        "lo": lo0,
        "hi": hi0,
        "rank_point": np.stack([best0, worst0], axis=1),
        "rank_ci95": rank_ci_int,
        "support_freq": support_freq,
        "supported": supported,
        "n_supported_pairs": int(supported.sum() - np.diag(supported).sum()),
        "n_identified_pairs_point": int(ident0.sum()),
        "median_rank_ci_width": float(np.median(width_ci)),
        "median_point_rank_width": float(np.median(width_point)),
        "max_rank_ci_width": int(width_ci.max()),
    }


def simulate_coverage(
    J: int = 12,
    T: int = 200,
    B: int = 500,
    n_mc: int = 200,
    miss_rate: float = 0.05,
    seed: int = DEFAULT_SEED,
    reading: str = "strict",
) -> dict:
    """Monte Carlo coverage of true ranks by the combined CI.

    DGP: p_j evenly spaced in (0.25, 0.75); Y_jt ~ Bern(p_j); independently
    each cell is missing with probability miss_rate and enters E. True rank
    is the rank of p_j. Related literature to VERIFY before citing: inference
    for ranks (e.g. Mogstad, Romano, Shaikh, Wilhelm); sample-selection bounds
    (e.g. Lee).
    """
    rng = np.random.default_rng(seed)
    p = np.linspace(0.25, 0.75, J)
    true_order = np.argsort(-p, kind="mergesort")
    true_rank = np.empty(J, dtype=int)
    true_rank[true_order] = np.arange(1, J + 1)

    marg_hit = np.zeros(J, dtype=int)
    simul_hit = 0
    widths = []

    for _ in range(n_mc):
        Y = rng.random((J, T)) < p[:, None]
        M = rng.random((J, T)) < miss_rate
        status = np.zeros((J, T), dtype=np.int8)
        status[Y & ~M] = 1
        status[M] = 2
        out = bootstrap_rank_confidence(
            status, reading=reading, B=B, seed=int(rng.integers(0, 2**31 - 1)),
        )
        ci = out["rank_ci95"]
        widths.append(ci[:, 1] - ci[:, 0])
        hits = (ci[:, 0] <= true_rank) & (true_rank <= ci[:, 1])
        marg_hit += hits.astype(int)
        simul_hit += bool(hits.all())

    return {
        "design": {
            "J": J, "T": T, "B": B, "n_mc": n_mc,
            "miss_rate": miss_rate, "seed": seed, "reading": reading,
            "p": p.tolist(), "true_rank": true_rank.tolist(),
            "citation_note": (
                "Related literature to VERIFY before citing: inference for "
                "ranks (e.g. Mogstad, Romano, Shaikh, Wilhelm); sample-selection "
                "bounds (e.g. Lee). This simulation checks our procedure only."
            ),
        },
        "marginal_coverage": (marg_hit / n_mc).tolist(),
        "mean_marginal_coverage": float(marg_hit.mean() / n_mc),
        "simultaneous_coverage": float(simul_hit / n_mc),
        "mean_ci_width": float(np.mean(widths)),
        "median_ci_width": float(np.median(widths)),
    }


def analyse_split(names: list[str], status: np.ndarray, label: str,
                  B: int, seed: int) -> dict:
    print(f"\n== {label}: J={len(names)} T={status.shape[1]} B={B}")
    report = {
        "label": label,
        "n_submissions": len(names),
        "N_tasks": int(status.shape[1]),
        "readings": {},
    }
    for reading in ("strict", "broad"):
        t0 = time.time()
        out = bootstrap_rank_confidence(status, reading=reading, B=B, seed=seed)
        dt = time.time() - t0
        rows = []
        order = np.argsort(-out["lo"])
        for rank_obs, a in enumerate(order, start=1):
            rows.append({
                "submission": names[a],
                "observed_score_rank": rank_obs,
                "lo": float(out["lo"][a]),
                "hi": float(out["hi"][a]),
                "rank_point": [int(out["rank_point"][a, 0]), int(out["rank_point"][a, 1])],
                "rank_ci95": [int(out["rank_ci95"][a, 0]), int(out["rank_ci95"][a, 1])],
            })
        adj_supported = adj_total = 0
        for i in range(len(order) - 1):
            a, b = order[i], order[i + 1]
            if out["lo"][a] == out["lo"][b]:
                continue
            adj_total += 1
            adj_supported += bool(out["supported"][a, b])
        summary = {
            "B": out["B"],
            "seed": out["seed"],
            "alpha": out["alpha"],
            "seconds": round(dt, 2),
            "n_supported_pairs": out["n_supported_pairs"],
            "n_identified_pairs_point": out["n_identified_pairs_point"],
            "adjacent_supported": [adj_total, adj_supported],
            "median_rank_ci_width": out["median_rank_ci_width"],
            "median_point_rank_width": out["median_point_rank_width"],
            "max_rank_ci_width": out["max_rank_ci_width"],
            "top10": rows[:10],
            "rows": rows,
        }
        report["readings"][reading] = summary
        print(
            f"   {reading}: point-ident pairs {out['n_identified_pairs_point']}  "
            f"bootstrap-supported pairs {out['n_supported_pairs']}  "
            f"adj supported {adj_supported}/{adj_total}  "
            f"median CI width {out['median_rank_ci_width']:.0f}  ({dt:.1f}s)"
        )
    return report


def load_split(key: str) -> tuple[list[str], np.ndarray, str, dict]:
    if key.startswith("swebench/"):
        split = key.split("/", 1)[1]
        rows = load_swe_ids(split)
        label = f"SWE-bench {split}"
    elif key.startswith("multi-swe-bench/"):
        lang = key.split("/", 1)[1]
        rows = load_mswe_ids(lang)
        label = f"Multi-SWE-bench {lang}"
    else:
        raise ValueError(key)
    n_counts = Counter(int(r["N"]) for r in rows)
    N_star, _ = n_counts.most_common(1)[0]
    dropped = [r["submission"] for r in rows if int(r["N"]) != N_star]
    rows = [r for r in rows if int(r["N"]) == N_star]
    meta = {
        "modal_N": N_star,
        "dropped_nonmodal_N": dropped,
        "n_N_values": {str(k): v for k, v in n_counts.items()},
    }
    rows.sort(key=lambda r: -len(r["R"]) / r["N"])
    names, status, _N = rows_to_status(rows)
    return names, status, label, meta


def all_split_keys() -> list[str]:
    return [f"swebench/{s}" for s in SWE_N] + [f"multi-swe-bench/{L}" for L in MSWE_LANGS]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default=None, help="e.g. swebench/verified; default=all")
    ap.add_argument("--B", type=int, default=DEFAULT_B)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--sim-only", action="store_true")
    ap.add_argument("--skip-sim", action="store_true")
    ap.add_argument("--sim-mc", type=int, default=200)
    ap.add_argument("--sim-B", type=int, default=400)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    if not args.skip_sim or args.sim_only:
        print("Running coverage simulation...")
        sim = {
            "independent_missing_005": simulate_coverage(
                miss_rate=0.05, n_mc=args.sim_mc, B=args.sim_B, seed=args.seed),
            "independent_missing_000": simulate_coverage(
                miss_rate=0.0, n_mc=args.sim_mc, B=args.sim_B, seed=args.seed + 1),
            "independent_missing_100": simulate_coverage(
                miss_rate=0.10, n_mc=args.sim_mc, B=args.sim_B, seed=args.seed + 2),
        }
        (OUT / "rank_confidence_sim.json").write_text(
            json.dumps(sim, indent=1), encoding="utf-8")
        for k, v in sim.items():
            print(
                f"  {k}: simultaneous={v['simultaneous_coverage']:.3f} "
                f"mean_marginal={v['mean_marginal_coverage']:.3f} "
                f"median_width={v['median_ci_width']:.2f}"
            )
        if args.sim_only:
            return 0

    keys = [args.split] if args.split else all_split_keys()
    report = {
        "method": {
            "description": (
                "Joint task bootstrap of sharp identified rank intervals; "
                "95% rank CI = [P2.5(best), P97.5(worst)]; pairwise support "
                "if bootstrap frequency of lo_A > hi_B >= 95%."
            ),
            "B": args.B,
            "seed": args.seed,
            "alpha": ALPHA,
            "citations_to_verify": [
                "Mogstad, Romano, Shaikh, Wilhelm (inference for ranks) - verify exact citation",
                "Lee (sample selection bounds) - verify exact citation",
            ],
        },
        "splits": {},
    }
    for key in keys:
        try:
            names, status, label, meta = load_split(key)
        except FileNotFoundError as exc:
            print(f"skip {key}: {exc}")
            continue
        if status.shape[0] < 2:
            print(f"skip {key}: fewer than 2 submissions")
            continue
        split_report = analyse_split(names, status, label, args.B, args.seed)
        split_report["modal_filter"] = meta
        if meta["dropped_nonmodal_N"]:
            print(
                f"   dropped non-modal N: {len(meta['dropped_nonmodal_N'])} "
                f"(kept N={meta['modal_N']})"
            )
        report["splits"][key] = split_report

    (OUT / "rank_confidence.json").write_text(
        json.dumps(report, indent=1, default=lambda o: float(o) if hasattr(o, "item") else o),
        encoding="utf-8",
    )
    print("\nWrote", OUT / "rank_confidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
