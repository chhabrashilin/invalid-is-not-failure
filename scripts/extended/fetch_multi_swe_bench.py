"""Fetch per-submission results from the public Multi-SWE-bench experiments
repository (github.com/multi-swe-bench/experiments) for the census.

Each submission's results/results.json reports, per language split, the total,
submitted, completed and resolved instance counts and id lists, plus instances
whose patch was empty or errored and instances whose evaluation did not
complete. Pinned to one commit.

    uv run python scripts/extended/fetch_multi_swe_bench.py
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.parse
from pathlib import Path

from fetch_swebench_census import fetch

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "data" / "raw" / "multi_swe_bench"
REPO = "multi-swe-bench/experiments"
PINNED_SHA = "6a7d5566f62fa76f4192302cf763051b98e4facc"


def gh(path: str):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def q(p: str) -> str:
    return urllib.parse.quote(p, safe="/")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"repo": REPO, "commit": PINNED_SHA,
                "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "splits": {}}
    langs = [e["name"] for e in gh(f"repos/{REPO}/contents/evaluation?ref={PINNED_SHA}")
             if e["type"] == "dir"]
    for lang in langs:
        for sub_split in gh(f"repos/{REPO}/contents/{q('evaluation/' + lang)}?ref={PINNED_SHA}"):
            if sub_split["type"] != "dir":
                continue
            split = f"{lang}/{sub_split['name']}"
            subs = [e["name"] for e in
                    gh(f"repos/{REPO}/contents/{q('evaluation/' + split)}?ref={PINNED_SHA}")
                    if e["type"] == "dir"]
            got = 0
            for s in subs:
                d = OUT / lang / sub_split["name"] / s
                d.mkdir(parents=True, exist_ok=True)
                base = (f"https://raw.githubusercontent.com/{REPO}/{PINNED_SHA}/"
                        f"{q('evaluation/' + split + '/' + s)}")
                for rel, fn in (("results/results.json", "results.json"),
                                ("metadata.yaml", "metadata.yaml")):
                    if not (d / fn).exists():
                        b = fetch(f"{base}/{rel}")
                        if b is not None:
                            (d / fn).write_bytes(b)
                got += (d / "results.json").exists()
            manifest["splits"][split] = {"submissions": len(subs), "with_results": got}
            print(f"{split}: {got}/{len(subs)}", flush=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
