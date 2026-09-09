#!/usr/bin/env python3
"""Sync .claude/skills to the versioned subsets in skill_inventory.json.

--check and --dry-run never write. --all explicitly enrolls all canonical skills
in every target; ordinary sync repairs only the declared inventory. Unknown
content is reported for review, never deleted. Symlinks are not distributed.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_NAMES = {"__pycache__", ".DS_Store", "node_modules", ".venv", ".pytest_cache", ".ruff_cache"}
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def safe_path(root: Path, relative: str) -> Path:
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or ".." in parts:
        raise ValueError(f"unsafe path: {relative}")
    current = root
    for part in parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"symlinks are not managed: {current}")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path leaves checkout: {relative}")
    return current


def ignore_excluded(_dir: str, names: list[str]) -> set[str]:
    return EXCLUDED_NAMES & set(names)


def relevant_files(root: Path) -> dict[Path, Path]:
    files = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if EXCLUDED_NAMES & set(relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"symlink in skill tree: {path}")
        if path.is_file():
            files[relative] = path
    return files


def skill_up_to_date(source: Path, target: Path) -> bool:
    if not target.is_dir():
        return False
    source_files, target_files = relevant_files(source), relevant_files(target)
    return source_files.keys() == target_files.keys() and all(
        filecmp.cmp(source_files[name], target_files[name], shallow=False)
        for name in source_files
    )


def sync_skill(source: Path, target: Path, dry_run: bool) -> None:
    if dry_run:
        return
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=ignore_excluded)


def main(argv: list[str] | None = None, *, root: Path = REPO_ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--all", action="store_true", help="enroll every canonical skill")
    parser.add_argument("skills", nargs="*")
    args = parser.parse_args(argv)
    readonly = args.check or args.dry_run
    try:
        canonical = safe_path(root, ".claude/skills")
        inventory_path = safe_path(root, "scripts/skill_inventory.json")
        inventory = json.loads(inventory_path.read_text())
        targets = inventory["targets"]
        if not isinstance(targets, dict) or not targets:
            raise ValueError("inventory needs nonempty targets")
        known = {p.name for p in canonical.iterdir() if p.is_dir() and p.name not in EXCLUDED_NAMES}
        if set(args.skills) - known:
            raise ValueError(f"unknown skills: {sorted(set(args.skills) - known)}")
        operations = []
        for target_name, required in targets.items():
            if not isinstance(required, list) or len(required) != len(set(required)):
                raise ValueError(f"invalid inventory: {target_name}")
            target_dir = safe_path(root, target_name)
            if args.all:
                required = sorted(known)
                targets[target_name] = required
            for name in required:
                if not NAME.fullmatch(name) or name not in known:
                    raise ValueError(f"{target_name}: unknown canonical skill {name!r}")
                source = safe_path(root, f".claude/skills/{name}")
                if not (source / "SKILL.md").is_file():
                    raise ValueError(f"missing canonical SKILL.md: {source}")
                relevant_files(source)
            if target_dir.exists():
                unexpected = {p.name for p in target_dir.iterdir() if p.name not in EXCLUDED_NAMES} - set(required)
                if unexpected:
                    raise ValueError(f"{target_name}: orphan/unmanaged content {sorted(unexpected)}; review inventory, no files removed")
            for name in required:
                target = safe_path(root, f"{target_name}/{name}")
                if target.exists():
                    relevant_files(target)
                if args.skills and name not in args.skills:
                    continue
                source = canonical / name
                if not skill_up_to_date(source, target):
                    operations.append((source, target))
        # Validate every path before performing any mutation.
        for source, target in operations:
            print(f"{'missing' if not target.exists() else 'different'}: {target.relative_to(root)}; repair: just sync-skills {source.name}")
            sync_skill(source, target, readonly)
        if args.all and not readonly:
            inventory_path.write_text(json.dumps(inventory, indent=2) + "\n")
        print(f"skills: {len(operations)} copies {'need sync' if readonly else 'updated'}")
        return int(args.check and bool(operations))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"error: {error}; inspect scripts/skill_inventory.json", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
