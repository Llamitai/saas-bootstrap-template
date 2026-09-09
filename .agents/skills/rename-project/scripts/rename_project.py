#!/usr/bin/env python3
"""Rename the neutral SaaS Bootstrap branding tokens to a real project name.

Tokens, context-aware rules, and exclusions live in
``scripts/branding_tokens.json`` at the repository root — the single source
shared with ``scripts/build_template.py`` (Copier template builder). Edit the
JSON, never the hardcoded values, or the two flows diverge silently.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

BRANDING_CONFIG_RELATIVE = Path("scripts/branding_tokens.json")


def load_config(root: Path) -> dict[str, Any]:
    config_path = root / BRANDING_CONFIG_RELATIVE
    if not config_path.is_file():
        raise SystemExit(
            f"Branding config not found at {config_path}. "
            "This script must run against a repository that keeps its token "
            "inventory in scripts/branding_tokens.json (pass --root if needed). "
            "Projects generated with Copier are already renamed and do not "
            "ship that file — this skill only applies to GitHub-template or "
            "cloned copies of the boilerplate."
        )
    return json.loads(config_path.read_text(encoding="utf-8"))


def slugify(value: str, separator: str = "-") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", separator, value)
    value = value.strip(separator)
    return value or "project"


def is_probably_text(path: Path, config: dict[str, Any]) -> bool:
    if path.suffix.lower() in set(config["text_suffixes"]):
        return True
    if path.name in set(config["text_filenames"]):
        return True
    if ".env" in path.name:
        return True
    return False


def should_skip_file(path: Path, config: dict[str, Any]) -> bool:
    if path.name in set(config["lockfile_names"]) or path.suffix == ".lock":
        return True
    if any(path.name.startswith(prefix) for prefix in config["skip_file_prefixes"]):
        return True
    return False


def excluded_parts(config: dict[str, Any], extra_excludes: set[str]) -> set[str]:
    parts = set(config["exclude_parts"])
    parts.update(config["rename_exclude_extra"]["paths"])
    parts.update(extra_excludes)
    return parts


def should_skip_relative(
    relative_path: Path, config: dict[str, Any], exclude_parts: set[str]
) -> bool:
    rel = relative_path.as_posix()
    if set(relative_path.parts) & set(config["exclude_dirs"]):
        return True
    if any(rel == item or rel.startswith(f"{item}/") for item in exclude_parts):
        return True
    return False


def iter_files(root: Path, config: dict[str, Any], exclude_parts: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            relative_dir = (current / dirname).relative_to(root)
            if not should_skip_relative(relative_dir, config, exclude_parts):
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            path = current / filename
            relative_file = path.relative_to(root)
            if should_skip_relative(relative_file, config, exclude_parts):
                continue
            yield path


def package_context(path: Path, line: str, config: dict[str, Any]) -> bool:
    rules = config["package_context"]
    stripped = line.strip()
    for prefix in rules["filename_line_prefixes"].get(path.name, []):
        if stripped.startswith(prefix):
            return True
    return any(fragment in line for fragment in rules["line_contains"])


def replace_line(
    path: Path,
    line: str,
    display_name: str,
    slug: str,
    python_name: str,
    config: dict[str, Any],
) -> str:
    tokens = config["tokens"]
    display_replacement = slug if package_context(path, line, config) else display_name
    line = line.replace(tokens["project_name"], display_replacement)
    line = line.replace(tokens["project_slug"], slug)
    line = line.replace(tokens["python_name"], python_name)
    return line


def rewrite_file(
    path: Path,
    display_name: str,
    slug: str,
    python_name: str,
    dry_run: bool,
    config: dict[str, Any],
) -> bool:
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False

    updated = "".join(
        replace_line(path, line, display_name, slug, python_name, config)
        for line in original.splitlines(keepends=True)
    )

    if updated == original:
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Display name for the project, for example 'Acme Portal'.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--slug", help="Kebab-case slug/package name. Defaults to a slugified display name.")
    parser.add_argument("--python-name", help="Python identifier form. Defaults to slug with underscores.")
    parser.add_argument("--exclude", action="append", default=[], help="Extra relative path or directory to skip.")
    parser.add_argument("--dry-run", action="store_true", help="Print files that would change without writing.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    config = load_config(root)
    slug = args.slug or slugify(args.name)
    python_name = args.python_name or slug.replace("-", "_")
    extra_excludes = {item.strip("/").replace("\\", "/") for item in args.exclude}
    exclude_parts = excluded_parts(config, extra_excludes)

    changed: list[Path] = []
    for path in iter_files(root, config, exclude_parts):
        if not path.is_file():
            continue
        if should_skip_file(path, config):
            continue
        if not is_probably_text(path, config):
            continue
        if rewrite_file(path, args.name, slug, python_name, args.dry_run, config):
            changed.append(path.relative_to(root))

    prefix = "Would update" if args.dry_run else "Updated"
    for path in changed:
        print(f"{prefix}: {path.as_posix()}")
    print(f"{prefix} {len(changed)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
