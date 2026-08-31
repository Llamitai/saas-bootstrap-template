#!/usr/bin/env python3
"""Keep every Node.js major pin aligned with the latest approved LTS line."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SCHEDULE_URL = "https://raw.githubusercontent.com/nodejs/Release/main/schedule.json"
DYNAMIC_WORKFLOW = Path(".github/workflows/node-lts.yml")
COMMON_STATIC_WORKFLOWS = (Path(".github/workflows/code_quality.yml"),)
CANONICAL_STATIC_WORKFLOWS = (Path(".github/workflows/publish-template.yml"),)
SETUP_NODE_RE = re.compile(r"\buses:\s*actions/setup-node@")
STATIC_NODE_RE = re.compile(r"\bnode-version:\s*['\"]?(\d+)['\"]?\s*(?:#.*)?$")
NODE_FILE_RE = re.compile(r"\bnode-version-file:\s*['\"]?([^'\"\s#]+)['\"]?")


class PolicyError(RuntimeError):
    """Raised when the repository or release schedule violates the policy."""


@dataclass(frozen=True)
class LTSRelease:
    major: int
    lts_date: date

    def as_dict(self) -> dict[str, str | int]:
        return {"major": self.major, "lts_date": self.lts_date.isoformat()}


@dataclass(frozen=True)
class SetupNodeReference:
    path: Path
    line: int
    static_major: int | None = None
    version_file: str | None = None


def _require_file(root: Path, relative: Path) -> Path:
    path = root / relative
    if not path.is_file():
        raise PolicyError(f"required file is missing: {relative}")
    return path


def _read_text(root: Path, relative: Path) -> str:
    return _require_file(root, relative).read_text(encoding="utf-8")


def _read_json(root: Path, relative: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read_text(root, relative))
    except json.JSONDecodeError as exc:
        raise PolicyError(f"invalid JSON in {relative}: {exc}") from exc
    if not isinstance(value, dict):
        raise PolicyError(f"expected a JSON object in {relative}")
    return value


def read_local_major(root: Path) -> int:
    raw = _read_text(root, Path(".nvmrc")).strip()
    if not re.fullmatch(r"[1-9]\d*", raw):
        raise PolicyError(".nvmrc must contain one explicit positive major")
    return int(raw)


def _engine_range(major: int) -> str:
    return f">={major}.0.0 <{major + 1}.0.0"


def _nested_string(document: dict[str, Any], *keys: str) -> str | None:
    value: Any = document
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value if isinstance(value, str) else None


def _setup_node_references(path: Path, root: Path) -> list[SetupNodeReference]:
    text = _read_text(root, path)
    lines = text.splitlines()
    references: list[SetupNodeReference] = []

    for index, line in enumerate(lines):
        if not SETUP_NODE_RE.search(line):
            continue

        uses_indent = len(line) - len(line.lstrip())
        static_major: int | None = None
        version_file: str | None = None

        for candidate in lines[index + 1 :]:
            stripped = candidate.lstrip()
            indent = len(candidate) - len(stripped)
            if stripped.startswith("-") and indent < uses_indent:
                break
            static_match = STATIC_NODE_RE.search(candidate)
            if static_match:
                static_major = int(static_match.group(1))
            file_match = NODE_FILE_RE.search(candidate)
            if file_match:
                version_file = file_match.group(1)

        if (static_major is None) == (version_file is None):
            raise PolicyError(
                f"{path}:{index + 1} must define exactly one of node-version "
                "or node-version-file"
            )
        references.append(
            SetupNodeReference(path, index + 1, static_major, version_file)
        )

    return references


def _workflow_paths(root: Path) -> list[Path]:
    workflow_dir = _require_file(
        root, Path(".github/workflows/code_quality.yml")
    ).parent
    paths = [*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]
    return sorted(path.relative_to(root) for path in paths if path.is_file())


def _assert_dependabot_rules(root: Path) -> None:
    text = _read_text(root, Path(".github/dependabot.yml"))

    def count_rule(dependency_name: str) -> int:
        pattern = re.compile(
            rf'- dependency-name:\s*"{re.escape(dependency_name)}"\s*\n'
            r'\s*update-types:\s*\["version-update:semver-major"\]'
        )
        return len(pattern.findall(text))

    if count_rule("@types/node") != 2:
        raise PolicyError(
            ".github/dependabot.yml must contain two semver-major ignore rules "
            "for @types/node"
        )
    if count_rule("node") != 1:
        raise PolicyError(
            ".github/dependabot.yml must contain one semver-major ignore rule for node"
        )


def check_repository(root: Path) -> tuple[int, str]:
    root = root.resolve()
    major = read_local_major(root)
    engine = _engine_range(major)

    for relative in (
        Path("package.json"),
        Path("frontend/package.json"),
        Path("docs/package.json"),
    ):
        actual = _nested_string(_read_json(root, relative), "engines", "node")
        if actual != engine:
            raise PolicyError(
                f"{relative} engines.node must be {engine!r}, found {actual!r}"
            )

    for relative in (Path("frontend/package.json"), Path("docs/package.json")):
        actual = _nested_string(
            _read_json(root, relative), "devDependencies", "@types/node"
        )
        expected = f"^{major}"
        if actual != expected:
            raise PolicyError(
                f"{relative} devDependencies.@types/node must be {expected!r}, "
                f"found {actual!r}"
            )

    readme = _read_text(root, Path("README.md"))
    readme_majors = [
        int(value) for value in re.findall(r"\*\*Node\.js (\d+)\*\*", readme)
    ]
    if readme_majors != [major]:
        raise PolicyError(
            f"README.md must contain exactly one Node.js prerequisite for major {major}"
        )

    dockerfile = _read_text(root, Path("frontend/Dockerfile"))
    docker_majors = [
        int(value)
        for value in re.findall(
            r"^FROM node:(\d+)-slim(?:\s|$)", dockerfile, re.MULTILINE
        )
    ]
    if docker_majors != [major, major, major]:
        raise PolicyError(
            f"frontend/Dockerfile must contain exactly three node:{major}-slim stages"
        )

    gitlab = _read_text(root, Path(".gitlab/ci/quality.gitlab-ci.yml"))
    gitlab_majors = [
        int(value)
        for value in re.findall(
            r"^\s*image:\s*node:(\d+)-slim\s*$", gitlab, re.MULTILINE
        )
    ]
    if gitlab_majors != [major]:
        raise PolicyError(
            ".gitlab/ci/quality.gitlab-ci.yml must contain exactly one aligned "
            f"node:{major}-slim image"
        )

    canonical = (root / "scripts/build_template.py").is_file()
    required_static = list(COMMON_STATIC_WORKFLOWS)
    if canonical:
        required_static.extend(CANONICAL_STATIC_WORKFLOWS)
    for relative in required_static:
        _require_file(root, relative)
    _require_file(root, DYNAMIC_WORKFLOW)

    dynamic_references: list[SetupNodeReference] = []
    static_references: list[SetupNodeReference] = []
    for relative in _workflow_paths(root):
        references = _setup_node_references(relative, root)
        if relative == DYNAMIC_WORKFLOW:
            dynamic_references.extend(references)
        else:
            static_references.extend(references)

    if len(dynamic_references) != 1:
        raise PolicyError(
            f"{DYNAMIC_WORKFLOW} must contain exactly one actions/setup-node step"
        )
    dynamic = dynamic_references[0]
    if dynamic.version_file != ".nvmrc" or dynamic.static_major is not None:
        raise PolicyError(f"{DYNAMIC_WORKFLOW} must use node-version-file: .nvmrc")

    required_static_set = set(required_static)
    observed_static_paths = {reference.path for reference in static_references}
    missing_setup = required_static_set - observed_static_paths
    if missing_setup:
        missing = ", ".join(str(path) for path in sorted(missing_setup))
        raise PolicyError(f"required workflows lack actions/setup-node: {missing}")

    for reference in static_references:
        if reference.version_file is not None:
            raise PolicyError(
                f"{reference.path}:{reference.line} may not use node-version-file"
            )
        if reference.static_major != major:
            raise PolicyError(
                f"{reference.path}:{reference.line} must use Node {major}, "
                f"found {reference.static_major}"
            )

    _assert_dependabot_rules(root)
    return major, "canonical" if canonical else "generated"


def _parse_date(value: Any, *, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise PolicyError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PolicyError(f"{field} must be a valid ISO date") from exc


def select_latest_lts(schedule: Any, today: date) -> LTSRelease:
    if not isinstance(schedule, dict) or not schedule:
        raise PolicyError("release schedule must be a non-empty JSON object")

    eligible: list[LTSRelease] = []
    for key, value in schedule.items():
        match = re.fullmatch(r"v([1-9]\d*)", key) if isinstance(key, str) else None
        if not match:
            continue
        if not isinstance(value, dict):
            raise PolicyError(f"release schedule entry {key} must be an object")
        if "lts" not in value:
            continue
        lts_date = _parse_date(value["lts"], field=f"{key}.lts")
        end_date = _parse_date(value.get("end"), field=f"{key}.end")
        if lts_date <= today < end_date:
            eligible.append(LTSRelease(int(match.group(1)), lts_date))

    if not eligible:
        raise PolicyError(f"no supported LTS release exists on {today.isoformat()}")
    return max(eligible, key=lambda release: release.major)


def _load_schedule(schedule_file: Path | None) -> Any:
    if schedule_file is not None:
        try:
            return json.loads(schedule_file.read_text(encoding="utf-8"))
        except OSError as exc:
            raise PolicyError(
                f"could not read schedule file {schedule_file}: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise PolicyError(
                f"invalid schedule JSON in {schedule_file}: {exc}"
            ) from exc

    request = urllib.request.Request(
        SCHEDULE_URL,
        headers={"Accept": "application/json", "User-Agent": "wise-node-lts-policy"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise PolicyError(f"release schedule returned HTTP {response.status}")
            payload = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PolicyError(f"could not download the release schedule: {exc}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PolicyError("official release schedule is not valid JSON") from exc


def latest_lts(schedule_file: Path | None, today: date | None = None) -> LTSRelease:
    effective_date = today or datetime.now(timezone.utc).date()
    return select_latest_lts(_load_schedule(schedule_file), effective_date)


def migration_required(local_major: int, official_release: LTSRelease) -> bool:
    if local_major > official_release.major:
        raise PolicyError(
            f"local Node {local_major} is newer than official LTS "
            f"{official_release.major}"
        )
    return local_major < official_release.major


def _replace_exact(
    changes: dict[Path, str], path: Path, old: str, new: str, expected_count: int
) -> None:
    text = changes[path]
    count = text.count(old)
    if count != expected_count:
        raise PolicyError(
            f"{path} expected {expected_count} occurrence(s) of {old!r}, found {count}"
        )
    changes[path] = text.replace(old, new)


def _atomic_write_all(root: Path, changes: dict[Path, str]) -> None:
    staged: list[tuple[Path, Path]] = []
    try:
        for relative, content in changes.items():
            target = root / relative
            descriptor, temporary_name = tempfile.mkstemp(
                dir=target.parent, prefix=f".{target.name}.", text=True
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
            os.chmod(temporary, stat.S_IMODE(target.stat().st_mode))
            staged.append((temporary, target))
        for temporary, target in staged:
            os.replace(temporary, target)
    finally:
        for temporary, _target in staged:
            temporary.unlink(missing_ok=True)


def update_repository(root: Path, target_major: int) -> list[Path]:
    if target_major < 1:
        raise PolicyError("target major must be a positive integer")
    current_major, profile = check_repository(root)
    if target_major == current_major:
        return []

    root = root.resolve()
    paths = {
        Path(".nvmrc"),
        Path("README.md"),
        Path("package.json"),
        Path("frontend/package.json"),
        Path("docs/package.json"),
        Path("frontend/Dockerfile"),
        Path(".gitlab/ci/quality.gitlab-ci.yml"),
        *COMMON_STATIC_WORKFLOWS,
    }
    if profile == "canonical":
        paths.update(CANONICAL_STATIC_WORKFLOWS)

    recognized_workflows = {
        *COMMON_STATIC_WORKFLOWS,
        *CANONICAL_STATIC_WORKFLOWS,
        DYNAMIC_WORKFLOW,
    }
    extra_static = {
        reference.path
        for relative in _workflow_paths(root)
        for reference in _setup_node_references(relative, root)
        if reference.static_major is not None and relative not in recognized_workflows
    }
    if extra_static:
        extras = ", ".join(str(path) for path in sorted(extra_static))
        raise PolicyError(
            "unmanaged static setup-node workflows require an explicit policy update: "
            f"{extras}"
        )

    changes = {relative: _read_text(root, relative) for relative in paths}
    changes[Path(".nvmrc")] = f"{target_major}\n"

    _replace_exact(
        changes,
        Path("README.md"),
        f"**Node.js {current_major}**",
        f"**Node.js {target_major}**",
        1,
    )
    for relative in (
        Path("package.json"),
        Path("frontend/package.json"),
        Path("docs/package.json"),
    ):
        _replace_exact(
            changes,
            relative,
            f'"node": "{_engine_range(current_major)}"',
            f'"node": "{_engine_range(target_major)}"',
            1,
        )
    for relative in (Path("frontend/package.json"), Path("docs/package.json")):
        _replace_exact(
            changes,
            relative,
            f'"@types/node": "^{current_major}"',
            f'"@types/node": "^{target_major}"',
            1,
        )
    _replace_exact(
        changes,
        Path("frontend/Dockerfile"),
        f"FROM node:{current_major}-slim",
        f"FROM node:{target_major}-slim",
        3,
    )
    _replace_exact(
        changes,
        Path(".gitlab/ci/quality.gitlab-ci.yml"),
        f"image: node:{current_major}-slim",
        f"image: node:{target_major}-slim",
        1,
    )
    for relative in COMMON_STATIC_WORKFLOWS:
        _replace_exact(
            changes,
            relative,
            f"node-version: {current_major}",
            f"node-version: {target_major}",
            1,
        )
    if profile == "canonical":
        for relative in CANONICAL_STATIC_WORKFLOWS:
            _replace_exact(
                changes,
                relative,
                f"node-version: {current_major}",
                f"node-version: {target_major}",
                1,
            )

    _atomic_write_all(root, changes)
    check_repository(root)
    return sorted(paths)


def _parse_cli_date(raw: str | None) -> date | None:
    return _parse_date(raw, field="--date") if raw is not None else None


def _write_github_output(
    path: Path, release: LTSRelease, *, needs_migration: bool
) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"major={release.major}\n")
        handle.write(f"lts_date={release.lts_date.isoformat()}\n")
        handle.write(f"migration_needed={str(needs_migration).lower()}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="Validate local Node.js pins without network")

    latest_parser = subparsers.add_parser(
        "latest", help="Resolve the latest officially active LTS major"
    )
    latest_parser.add_argument("--schedule-file", type=Path)
    latest_parser.add_argument("--date")
    latest_parser.add_argument("--github-output", type=Path)

    update_parser = subparsers.add_parser(
        "update", help="Update every managed local pin to one explicit major"
    )
    update_parser.add_argument("major", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            major, profile = check_repository(args.root)
            print(f"Node LTS policy OK: Node {major} ({profile})")
            return 0
        if args.command == "latest":
            release = latest_lts(args.schedule_file, _parse_cli_date(args.date))
            needs_migration = migration_required(read_local_major(args.root), release)
            if args.github_output is not None:
                _write_github_output(
                    args.github_output, release, needs_migration=needs_migration
                )
            result = {**release.as_dict(), "migration_needed": needs_migration}
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command == "update":
            changed = update_repository(args.root, args.major)
            print(
                json.dumps({"changed": [str(path) for path in changed]}, sort_keys=True)
            )
            return 0
    except PolicyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
