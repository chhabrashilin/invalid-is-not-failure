"""Fetch per-submission evaluation outcomes from the public SWE-bench
experiments repository (github.com/swe-bench/experiments) for the
invalidity census in the extended paper.

For every submission under evaluation/<split>/ we download results/results.json
(instance-id lists per outcome category) and metadata.yml, pinned to one commit
so the census is reproducible.

    uv run python scripts/extended/fetch_swebench_census.py
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "data" / "raw" / "swebench_experiments"
SPLITS = ["verified", "lite", "test"]


def gh(path: str):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def fetch(url: str) -> bytes | None:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            time.sleep(1 + attempt)
    return None


def main() -> int:
    sha = gh("repos/swe-bench/experiments/commits/main")["sha"]
    print("pinned commit", sha)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"repo": "swe-bench/experiments", "commit": sha,
                "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "splits": {}}
    for split in SPLITS:
        names = [e["name"] for e in gh(f"repos/swe-bench/experiments/contents/evaluation/{split}?ref={sha}")
                 if e["type"] == "dir"]
        got = 0
        for name in names:
            d = OUT / split / name
            d.mkdir(parents=True, exist_ok=True)
            base = f"https://raw.githubusercontent.com/swe-bench/experiments/{sha}/evaluation/{split}/{name}"
            if not (d / "results.json").exists():
                res = fetch(f"{base}/results/results.json")
                if res is not None:
                    (d / "results.json").write_bytes(res)
            if not (d / "metadata.yml").exists():
                meta = fetch(f"{base}/metadata.yml")
                if meta is not None:
                    (d / "metadata.yml").write_bytes(meta)
            got += (d / "results.json").exists()
        manifest["splits"][split] = {"submissions": len(names), "with_results": got}
        print(f"{split}: {got}/{len(names)} submissions with results.json")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
