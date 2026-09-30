"""Invalidity census of public agent leaderboards (extended paper).

Sources (pinned commits):
  SWE-bench experiments      Verified (500), Lite (300), Test (2294)
  Multi-SWE-bench experiments  c, c++, go, java, javascript, python, rust,
                               typescript (verified splits)
SWE-bench Multimodal is excluded: its published files imply two different task
counts (517 and 510), so scores are not comparable across submissions.

Every leaderboard score is |resolved| / N, the invalid-as-failure policy. We
classify runs with Definition 1 of the paper:
  evaluation censoring  SWE-bench: no_logs, install_fail, reset_failed
                        Multi-SWE-bench: incomplete or errored evaluation
  unattributable        SWE-bench: no_generation, test_timeout
                        Multi-SWE-bench: empty or error patch, and instances
                        missing from every outcome list
  outcome               everything else

For each split we report
  * assumption-free intervals (strict: only evaluation censoring is missing;
    broad: unattributable runs are missing too),
  * orderings the data identify (A above B iff lo_A > hi_B),
  * sharp rank intervals: best rank 1 + #{B: lo_B > hi_A}, worst rank
    1 + #{B: hi_B > lo_A}; sharp because each submission's missing outcomes
    are separate unknowns,
  * paired significance: a paired z-test on per-task differences for the
    submissions whose resolved-id lists are published, cross-tabulated with
    identification.

    uv run python scripts/extended/census_leaderboard.py
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "data" / "raw"
OUT = REPO_ROOT / "results" / "extended"
SWE_N = {"verified": 500, "lite": 300, "test": 2294}
SWE_EVAL = ("no_logs", "install_fail", "reset_failed")
SWE_UNATTR = ("no_generation", "test_timeout")
MSWE_LANGS = ("c", "c++", "go", "java", "javascript", "python", "rust", "typescript")
Z = 1.959964


def load_swe(split):
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
        rows.append({"submission": f.parent.name, "N": N, "R": R,
                     "E": len(E), "U": len(U)})
    return rows


def load_mswe(lang):
    rows = []
    for f in sorted((RAW / "multi_swe_bench" / lang / "verified").glob("*/results.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        N = int(d["total_instances"])
        R = set(d["resolved"])
        C = set(d.get("completed_ids", []))
        E = (set(d.get("incomplete_ids", [])) | set(d.get("error_ids", []))) - R
        Ul = (set(d.get("empty_error_patch_ids", [])) | set(d.get("empty_patch_ids", []))) - R - E
        missing = max(0, N - len(C | E | Ul))
        rows.append({"submission": f.parent.name, "N": N, "R": R,
                     "E": len(E), "U": len(Ul) + missing})
    return rows


def analyse(rows, label):
    for r in rows:
        N = r["N"]
        r["score"] = len(r["R"]) / N
        r["lo"] = r["score"]
        r["hi_strict"] = (len(r["R"]) + r["E"]) / N
        r["hi_broad"] = (len(r["R"]) + r["E"] + r["U"]) / N
    rows.sort(key=lambda r: -r["score"])
    n = len(rows)
    lo = np.array([r["lo"] for r in rows])
    out = {"n_submissions": n,
           "N_tasks": sorted({r["N"] for r in rows}),
           "share_any_eval": float(np.mean([r["E"] > 0 for r in rows])),
           "share_any_unattr": float(np.mean([r["U"] > 0 for r in rows])),
           "share_any_invalid": float(np.mean([(r["E"] + r["U"]) > 0 for r in rows])),
           "n_over_5pct": int(sum((r["E"] + r["U"]) / r["N"] > 0.05 for r in rows)),
           "max_invalid_pct": float(max((r["E"] + r["U"]) / r["N"] for r in rows) * 100),
           "median_invalid_pct": float(np.median([(r["E"] + r["U"]) / r["N"] for r in rows]) * 100)}
    for key in ("strict", "broad"):
        hi = np.array([r[f"hi_{key}"] for r in rows])
        tot = ident = 0
        for i, j in combinations(range(n), 2):
            if lo[i] == lo[j]:
                continue
            tot += 1
            ident += lo[i] > hi[j]
        adj = [(i, i + 1) for i in range(n - 1) if lo[i] > lo[i + 1]]
        out[f"pairs_{key}"] = [tot, ident]
        out[f"adjacent_{key}"] = [len(adj), int(sum(lo[i] > hi[j] for i, j in adj))]
        best = 1 + (lo[None, :] > hi[:, None]).sum(axis=1)
        worst = 1 + ((hi[None, :] > lo[:, None]) & ~np.eye(n, dtype=bool)).sum(axis=1)
        width = worst - best
        out[f"rank_width_{key}"] = {"median": float(np.median(width)),
                                    "max": int(width.max()),
                                    "share_width_ge_3": float(np.mean(width >= 3))}
        for r, b, w in zip(rows, best, worst):
            r[f"rank_{key}"] = [int(b), int(w)]
    # paired significance on per-task differences
    N = rows[0]["N"]
    universe = sorted(set().union(*(r["R"] for r in rows)))
    idx = {t: k for k, t in enumerate(universe)}
    Ymat = np.zeros((n, len(universe)), dtype=np.int8)
    for a, r in enumerate(rows):
        for t in r["R"]:
            Ymat[a, idx[t]] = 1
    sig_tab = {"sig_ident_strict": 0, "sig_notident_strict": 0,
               "sig_ident_broad": 0, "sig_notident_broad": 0, "sig": 0, "pairs": 0}
    hi_s = np.array([r["hi_strict"] for r in rows])
    hi_b = np.array([r["hi_broad"] for r in rows])
    for i, j in combinations(range(n), 2):
        if rows[i]["N"] != rows[j]["N"] or lo[i] == lo[j]:
            continue
        d = Ymat[i].astype(float) - Ymat[j]
        # tasks nobody resolved contribute d = 0 and count toward N
        mean = d.sum() / N
        var = (d ** 2).sum() / N - mean ** 2
        se = np.sqrt(max(var, 0) / N)
        sig_tab["pairs"] += 1
        if se > 0 and abs(mean) > Z * se:
            sig_tab["sig"] += 1
            sig_tab["sig_ident_strict" if lo[i] > hi_s[j] else "sig_notident_strict"] += 1
            sig_tab["sig_ident_broad" if lo[i] > hi_b[j] else "sig_notident_broad"] += 1
    out["significance"] = sig_tab
    out["top10"] = [{k: r[k] for k in ("submission", "score", "E", "U", "hi_strict",
                                       "hi_broad", "rank_strict", "rank_broad")}
                    for r in rows[:10]]
    out["rows"] = [{k: (v if k != "R" else len(v)) for k, v in r.items()} for r in rows]
    print(f"\n== {label}: {n} subm, N={out['N_tasks']}, any invalid {out['share_any_invalid']:.2f}, "
          f">5% {out['n_over_5pct']}, max {out['max_invalid_pct']:.1f}%")
    for key in ("strict", "broad"):
        p, a, w = out[f"pairs_{key}"], out[f"adjacent_{key}"], out[f"rank_width_{key}"]
        print(f"   {key}: pairs {p[1]}/{p[0]}  adjacent {a[1]}/{a[0]}  rank width median "
              f"{w['median']:.0f} max {w['max']} share>=3 {w['share_width_ge_3']:.2f}")
    s = sig_tab
    print(f"   significant pairs {s['sig']}/{s['pairs']}; significant but not identified: "
          f"strict {s['sig_notident_strict']}, broad {s['sig_notident_broad']}")
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"sources": {
        "swebench": json.loads((RAW / "swebench_experiments" / "manifest.json").read_text()),
        "multi_swe_bench": json.loads((RAW / "multi_swe_bench" / "manifest.json").read_text())},
        "splits": {}}
    for split in SWE_N:
        report["splits"][f"swebench/{split}"] = analyse(load_swe(split), f"SWE-bench {split}")
    for lang in MSWE_LANGS:
        report["splits"][f"multi-swe-bench/{lang}"] = analyse(load_mswe(lang),
                                                              f"Multi-SWE-bench {lang}")
    agg = {"submissions": 0, "adj_strict": [0, 0], "adj_broad": [0, 0],
           "sig": 0, "sig_notident_strict": 0, "sig_notident_broad": 0, "any_invalid": 0}
    for s in report["splits"].values():
        agg["submissions"] += s["n_submissions"]
        agg["any_invalid"] += round(s["share_any_invalid"] * s["n_submissions"])
        for k in ("strict", "broad"):
            agg[f"adj_{k}"][0] += s[f"adjacent_{k}"][0]
            agg[f"adj_{k}"][1] += s[f"adjacent_{k}"][1]
        agg["sig"] += s["significance"]["sig"]
        agg["sig_notident_strict"] += s["significance"]["sig_notident_strict"]
        agg["sig_notident_broad"] += s["significance"]["sig_notident_broad"]
    report["aggregate"] = agg
    print("\nAGGREGATE", agg)
    (OUT / "census_leaderboard.json").write_text(json.dumps(report, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
