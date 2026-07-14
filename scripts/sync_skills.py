#!/usr/bin/env python3
"""Sync canonical agent skills from .claude/skills into the other agent packs.

Canonical source: .claude/skills/
Targets:          .codex/skills/, .opencode/skills/, and .agents/skills/

By default only skills that ALREADY exist in a target are synced (the
Codex/OpenCode/shared packs are intentionally a subset of the Claude pack).
Use --all to also copy claude-only skills into every target.

Skills whose target copy already matches the canonical content byte-for-byte
are reported as up-to-date and left untouched.

Usage:
    python3 scripts/sync_skills.py                 # sync shared skills
    python3 scripts/sync_skills.py --dry-run       # list what would sync
    python3 scripts/sync_skills.py --check         # exit 1 if any copy drifted
    python3 scripts/sync_skills.py --all           # also copy claude-only skills
    python3 scripts/sync_skills.py python-testing  # only sync the named skills
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = REPO_ROOT / ".claude" / "skills"
TARGET_DIRS = (
    REPO_ROOT / ".codex" / "skills",
    REPO_ROOT / ".opencode" / "skills",
    REPO_ROOT / ".agents" / "skills",
)
EXCLUDED_NAMES = {"__pycache__", ".DS_Store"}


def ignore_excluded(_dir: str, names: list[str]) -> set[str]:
    return EXCLUDED_NAMES & set(names)


def relevant_files(root: Path) -> dict[Path, Path]:
    files: dict[Path, Path] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if EXCLUDED_NAMES & set(relative.parts):
            continue
        if path.is_file():
            files[relative] = path
    return files


def skill_up_to_date(source: Path, target: Path) -> bool:
    if not target.is_dir():
        return False
    source_files = relevant_files(source)
    target_files = relevant_files(target)
    if source_files.keys() != target_files.keys():
        return False
    return all(
        filecmp.cmp(source_files[relative], target_files[relative], shallow=False)
        for relative in source_files
    )


def sync_skill(source: Path, target: Path, dry_run: bool) -> None:
    if dry_run:
        return
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=ignore_excluded)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would sync without copying anything",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="like --dry-run, but exit 1 when any target copy is out of sync",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="also copy skills that exist only in .claude/skills",
    )
    parser.add_argument(
        "skills",
        nargs="*",
        metavar="SKILL",
        help="only sync these skill names (default: every canonical skill)",
    )
    args = parser.parse_args()
    if args.check:
        args.dry_run = True

    if not CANONICAL_DIR.is_dir():
        print(f"error: canonical dir not found: {CANONICAL_DIR}", file=sys.stderr)
        return 1

    canonical_skills = sorted(
        entry
        for entry in CANONICAL_DIR.iterdir()
        if entry.is_dir() and entry.name not in EXCLUDED_NAMES
    )
    if args.skills:
        known = {skill.name for skill in canonical_skills}
        unknown = sorted(set(args.skills) - known)
        if unknown:
            print(f"error: unknown skill(s): {', '.join(unknown)}", file=sys.stderr)
            return 1
        canonical_skills = [
            skill for skill in canonical_skills if skill.name in set(args.skills)
        ]

    verb = "would sync" if args.dry_run else "synced"
    synced = 0
    up_to_date = 0
    skipped = 0

    for target_dir in TARGET_DIRS:
        if not target_dir.is_dir():
            print(f"skipping missing target dir: {target_dir.relative_to(REPO_ROOT)}")
            continue
        for skill in canonical_skills:
            target = target_dir / skill.name
            if not target.exists() and not args.all:
                skipped += 1
                continue
            if skill_up_to_date(skill, target):
                print(f"up-to-date: {skill.name} -> {target_dir.relative_to(REPO_ROOT)}/")
                up_to_date += 1
                continue
            sync_skill(skill, target, args.dry_run)
            print(f"{verb}: {skill.name} -> {target_dir.relative_to(REPO_ROOT)}/")
            synced += 1

    print(
        f"\nsummary: {synced} skill copies {verb.replace('would sync', 'to sync')}, "
        f"{up_to_date} up-to-date, "
        f"{skipped} claude-only skill copies skipped"
        f"{'' if args.all else ' (use --all to include them)'}"
    )
    if args.check and synced:
        print(
            "error: skill copies are out of sync; run `just sync-skills`",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
