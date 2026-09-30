"""Upload packed derived files to a Hugging Face dataset repo.

Requires:
  pip install huggingface_hub
  huggingface-cli login   # or set HF_TOKEN

Usage:
  python hf_dataset/upload.py --repo YOURUSER/infra-censoring-derived
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


def _pack() -> None:
    path = Path(__file__).resolve().parent / "pack_derived.py"
    spec = importlib.util.spec_from_file_location("pack_derived", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    raise_if = mod.main()
    if raise_if:
        raise SystemExit(raise_if)


def upload(repo_id: str) -> None:
    from huggingface_hub import HfApi

    _pack()
    root = Path(__file__).resolve().parent
    api = HfApi()
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True, private=False)
    api.upload_folder(
        folder_path=str(root),
        repo_id=repo_id,
        repo_type="dataset",
        ignore_patterns=["upload.py", "pack_derived.py", "__pycache__/*"],
    )
    print(f"uploaded to https://huggingface.co/datasets/{repo_id}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, help="e.g. chhabrashilin/infra-censoring-derived")
    args = p.parse_args()
    upload(args.repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
