#!/usr/bin/env python3
"""Identify tracked and untracked source bytes without adding files to Git."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def snapshot(root: Path, exclusions: list[str]) -> dict:
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    ).decode().split("\0")
    digest = hashlib.sha256()
    for name in sorted(set(names) - {""}):
        if any(name == p or name.startswith(p.rstrip("/") + "/") for p in exclusions):
            continue
        path = root / name
        digest.update(name.encode() + b"\0")
        if path.is_symlink():
            digest.update(os.readlink(path).encode())
        else:
            digest.update(path.read_bytes() if path.is_file() else b"<deleted>")
        digest.update(b"\0")
    return {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "sourceSha256": digest.hexdigest(),
        "excluded": exclusions,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(snapshot(Path(__file__).resolve().parent.parent, args.exclude), indent=2))
