"""Copy derived extended results into hf_dataset/data for Hugging Face upload."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "results" / "extended"
DST = Path(__file__).resolve().parent / "data"

# Aggregates and estimator outputs only (not run-level CSVs / npz).
INCLUDE = [
    "census_leaderboard.json",
    "critical_hazard.json",
    "frontier_analysis.json",
    "trace_driven.json",
    "sensitivity.json",
    "assumption_tests.json",
    "real_case_uncertainty.json",
    "dr_estimator.json",
    "dr_estimator_v2.json",
    "label_repair.json",
    "rank_confidence.json",
    "rank_confidence_sim.json",
]


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    missing = []
    for name in INCLUDE:
        src = SRC / name
        if not src.is_file():
            missing.append(name)
            continue
        shutil.copy2(src, DST / name)
        print(f"copied {name}")
    if missing:
        raise SystemExit(f"missing files under {SRC}: {missing}")
    print(f"packed {len(INCLUDE)} files into {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
