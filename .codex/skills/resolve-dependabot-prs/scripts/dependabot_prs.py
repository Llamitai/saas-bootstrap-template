#!/usr/bin/env python3
"""Deterministic, defensive executor for Dependabot pull requests.

The module intentionally uses only the Python standard library.  Network and
Git access are routed through :class:`Runner`, which makes every operation
injectable in tests and gives ``--dry-run`` a reliable mutation boundary.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence


EXIT_OK = 0
EXIT_ENV = 2
EXIT_INCOMPLETE = 3
EXIT_CONTRACT = 4
EXIT_APPROVAL = 5
EXIT_STALE = 6
EXIT_PROTECTION = 7
EXIT_BLOCKED = 8

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_HASH_RE = re.compile(r"^[0-9a-f]{12}$")
REPLACEMENT_SOURCE_MARKER_RE = re.compile(
    r"<!-- resolve-dependabot-prs:v1 source=([1-9][0-9]*@[0-9a-f]{40}) "
    r"plan=[0-9a-f]{64} tree=[0-9a-f]{40} -->"
)
LEGACY_REPLACEMENT_MARKER_RE = re.compile(
    r"<!-- resolve-dependabot-prs:v1 key=([0-9a-f]{12}) "
    r"source=([1-9][0-9]*@[0-9a-f]{40}) -->"
)
IMPACTS = {"patch", "minor", "major", "non-semver", "unknown"}
ECOSYSTEMS = {"npm", "uv", "docker", "github-actions", "unknown"}


@dataclasses.dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class Runner:
    """Subprocess adapter used by production and replaced by offline tests."""

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        mutating: bool = False,
    ) -> CommandResult:
        del mutating  # The flag is a policy boundary and a test observation.
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class ExecutorError(Exception):
    """A typed, user-actionable executor failure."""

    def __init__(
        self,
        exit_code: int,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def as_json(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


@dataclasses.dataclass
class ApplyOutcome:
    state: dict[str, Any]
    commands: list[list[str]]
    dry_run: bool


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _utc_now(value: str | None = None) -> str:
    if value is None:
        instant = dt.datetime.now(dt.timezone.utc)
    else:
        raw = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            instant = dt.datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ExecutorError(
                EXIT_CONTRACT, "CONTRACT", "Invalid RFC3339 timestamp"
            ) from exc
        if instant.tzinfo is None:
            raise ExecutorError(
                EXIT_CONTRACT, "CONTRACT", "Timestamp must include a timezone"
            )
        instant = instant.astimezone(dt.timezone.utc)
    return instant.isoformat(timespec="seconds").replace("+00:00", "Z")


def _result(value: Any) -> CommandResult:
    if isinstance(value, CommandResult):
        return value
    return CommandResult(
        int(getattr(value, "returncode")),
        str(getattr(value, "stdout", "")),
        str(getattr(value, "stderr", "")),
    )


def _run(
    runner: Runner,
    args: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    mutating: bool = False,
) -> CommandResult:
    kwargs: dict[str, Any] = {
        "cwd": str(cwd) if cwd is not None else None,
        "env": env,
        "mutating": mutating,
    }
    try:
        return _result(runner.run(list(args), **kwargs))
    except TypeError:
        # Small third-party fakes often predate the mutating observation flag.
        kwargs.pop("mutating")
        return _result(runner.run(list(args), **kwargs))


def _checked(
    runner: Runner,
    args: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    mutating: bool = False,
    exit_code: int = EXIT_ENV,
    code: str = "ENV",
) -> CommandResult:
    result = _run(runner, args, cwd=cwd, env=env, mutating=mutating)
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise ExecutorError(
            exit_code,
            code,
            message,
            {"command": list(args), "returncode": result.returncode},
        )
    return result


def _json_result(result: CommandResult, *, code: str = "API") -> Any:
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ExecutorError(
            EXIT_INCOMPLETE, code, "Command returned malformed JSON"
        ) from exc


def _is_404(result: CommandResult) -> bool:
    text = f"{result.stdout}\n{result.stderr}".lower()
    return (
        result.returncode != 0
        and re.search(
            r"(?:http(?: status)?|status(?: code)?)[: ]+404\b",
            text,
        )
        is not None
    )


def _gh_api(
    runner: Runner,
    host: str,
    endpoint: str,
    *,
    method: str = "GET",
    fields: Mapping[str, str] | None = None,
    mutating: bool = False,
    allow_404: bool = False,
) -> Any | None:
    args = ["gh", "api", "--hostname", host, "--method", method, endpoint]
    for key, value in sorted((fields or {}).items()):
        args.extend(["-f", f"{key}={value}"])
    result = _run(runner, args, mutating=mutating)
    if allow_404 and _is_404(result):
        return None
    if result.returncode:
        text = f"{result.stdout}\n{result.stderr}".lower()
        if "rate limit" in text or "http 429" in text:
            raise ExecutorError(
                EXIT_INCOMPLETE,
                "RATE_LIMIT",
                "GitHub rate limit interrupted the request",
            )
        if "http 403" in text and (
            "/rules/branches/" in endpoint or endpoint.endswith("/protection")
        ):
            raise ExecutorError(
                EXIT_PROTECTION,
                "PROTECTION",
                "Branch protection could not be read with the current credentials",
            )
        raise ExecutorError(
            EXIT_INCOMPLETE,
            "API",
            result.stderr.strip() or "GitHub API request failed",
            {"endpoint": endpoint, "returncode": result.returncode},
        )
    return _json_result(result)


def _normalise_remote(url: str) -> tuple[str, str]:
    value = url.strip()
    if not value:
        raise ExecutorError(EXIT_CONTRACT, "REPO_MISMATCH", "origin has an empty URL")
    host: str
    path: str
    if re.match(r"^[^/@:]+@[^:]+:.+$", value):
        authority, path = value.split(":", 1)
        host = authority.split("@", 1)[1]
    else:
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme not in {"https", "http", "ssh", "git"} or not parsed.hostname:
            raise ExecutorError(
                EXIT_CONTRACT, "REPO_MISMATCH", "Unsupported origin URL"
            )
        host = parsed.hostname
        path = parsed.path
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    pieces = path.split("/")
    if len(pieces) != 2 or not all(pieces):
        raise ExecutorError(
            EXIT_CONTRACT, "REPO_MISMATCH", "origin must identify owner/repository"
        )
    return host.lower(), "/".join(pieces)


def _safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ExecutorError(
            EXIT_CONTRACT, "CONTRACT", f"Unsafe repository path: {value!r}"
        )
    return str(path)


def _gh_repo_arg(repository: Mapping[str, Any]) -> str:
    name = str(repository["nameWithOwner"])
    host = str(repository["host"])
    return f"{host}/{name}"


def _repository_runtime_identity(repository: Mapping[str, Any]) -> dict[str, Any]:
    """Exclude the volatile default-branch SHA from apply-time identity."""

    return {
        key: repository[key]
        for key in (
            "host",
            "nameWithOwner",
            "remote",
            "root",
            "defaultBranch",
            "actorLogin",
        )
    }


def _git_identity(root: str | Path, runner: Runner) -> tuple[Path, str, str]:
    requested = Path(root).expanduser().resolve()
    top = _checked(
        runner,
        ["git", "rev-parse", "--show-toplevel"],
        cwd=requested,
        code="REPO_MISMATCH",
        exit_code=EXIT_CONTRACT,
    ).stdout.strip()
    actual = Path(top).resolve()
    if actual != requested:
        raise ExecutorError(
            EXIT_CONTRACT, "REPO_MISMATCH", "--root is not the Git toplevel"
        )
    fetch = _checked(
        runner,
        ["git", "remote", "get-url", "origin"],
        cwd=actual,
        code="REPO_MISMATCH",
        exit_code=EXIT_CONTRACT,
    ).stdout.strip()
    push = _checked(
        runner,
        ["git", "remote", "get-url", "--push", "origin"],
        cwd=actual,
        code="REPO_MISMATCH",
        exit_code=EXIT_CONTRACT,
    ).stdout.strip()
    fetch_identity = _normalise_remote(fetch)
    push_identity = _normalise_remote(push)
    if (fetch_identity[0], fetch_identity[1].lower()) != (
        push_identity[0],
        push_identity[1].lower(),
    ):
        raise ExecutorError(
            EXIT_CONTRACT, "REPO_MISMATCH", "origin fetch and push URLs differ"
        )
    return actual, fetch_identity[0], fetch_identity[1]


def _resolve_repository(root: str | Path, runner: Runner) -> dict[str, Any]:
    actual, host, remote_name = _git_identity(root, runner)
    _checked(runner, ["gh", "auth", "status", "--hostname", host], code="AUTH")
    view = _json_result(
        _checked(
            runner,
            [
                "gh",
                "repo",
                "view",
                f"{host}/{remote_name}",
                "--json",
                "nameWithOwner,isFork,parent,defaultBranchRef",
            ],
            code="REPO_MISMATCH",
            exit_code=EXIT_CONTRACT,
        ),
        code="CONTRACT",
    )
    if not isinstance(view, dict) or not isinstance(view.get("nameWithOwner"), str):
        raise ExecutorError(
            EXIT_CONTRACT, "CONTRACT", "gh repo view returned an invalid repository"
        )
    canonical_name = view["nameWithOwner"]
    if canonical_name.lower() != remote_name.lower():
        raise ExecutorError(
            EXIT_CONTRACT,
            "REPO_MISMATCH",
            "gh and origin identify different repositories",
        )
    if view.get("isFork") is True:
        raise ExecutorError(
            EXIT_CONTRACT,
            "REPO_MISMATCH",
            "origin is a fork, not the pull request base repository",
        )
    default_ref = view.get("defaultBranchRef")
    if not isinstance(default_ref, dict) or not isinstance(
        default_ref.get("name"), str
    ):
        raise ExecutorError(EXIT_CONTRACT, "CONTRACT", "Default branch is unavailable")
    actor = _gh_api(runner, host, "user")
    if not isinstance(actor, dict) or not isinstance(actor.get("login"), str):
        raise ExecutorError(
            EXIT_ENV, "AUTH", "Authenticated GitHub actor is unavailable"
        )
    default_branch = default_ref["name"]
    ref = _gh_api(
        runner,
        host,
        f"repos/{canonical_name}/git/ref/heads/{urllib.parse.quote(default_branch, safe='')}",
    )
    try:
        default_sha = ref["object"]["sha"]
    except (KeyError, TypeError) as exc:
        raise ExecutorError(
            EXIT_INCOMPLETE, "API", "Default branch SHA is unavailable"
        ) from exc
    if not isinstance(default_sha, str) or not SHA40_RE.fullmatch(default_sha):
        raise ExecutorError(EXIT_CONTRACT, "CONTRACT", "Default branch SHA is invalid")
    return {
        "host": host,
        "nameWithOwner": canonical_name,
        "remote": "origin",
        "root": str(actual),
        "defaultBranch": default_branch,
        "defaultBranchSha": default_sha,
        "actorLogin": actor["login"],
    }


_SEMVER = re.compile(
    r"^[vV]?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_ACTION_REF = re.compile(r"^[vV](\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?$")
_PEP440 = re.compile(
    r"^[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:(a|b|rc)(\d+))?(?:\.?(post)(\d+))?(?:\.?(dev)(\d+))?$",
    re.IGNORECASE,
)


def _tuple_impact(old: tuple[int, int, int], new: tuple[int, int, int]) -> str:
    if new[0] != old[0]:
        return "major"
    if new[1] != old[1]:
        return "minor"
    return "patch"


def _semver_pair(old: str, new: str) -> tuple[str, bool | None]:
    old_match = _SEMVER.fullmatch(old)
    new_match = _SEMVER.fullmatch(new)
    if not old_match or not new_match:
        return "non-semver", None
    prerelease = new_match.group(4) is not None
    old_tuple = tuple(int(old_match.group(index)) for index in range(1, 4))
    new_tuple = tuple(int(new_match.group(index)) for index in range(1, 4))
    return _tuple_impact(old_tuple, new_tuple), prerelease


def _pep440_pair(old: str, new: str) -> tuple[str, bool | None]:
    if "!" in old or "!" in new or "+" in old or "+" in new:
        return "unknown", None
    old_match = _PEP440.fullmatch(old)
    new_match = _PEP440.fullmatch(new)
    if not old_match or not new_match:
        return "non-semver", None
    old_tuple = tuple(int(old_match.group(index) or 0) for index in range(1, 4))
    new_tuple = tuple(int(new_match.group(index) or 0) for index in range(1, 4))
    prerelease = bool(new_match.group(4) or new_match.group(8))
    return _tuple_impact(old_tuple, new_tuple), prerelease


def _docker_pair(old: str, new: str) -> tuple[str, bool | None]:
    def split(value: str) -> tuple[str, str | None]:
        if "@" not in value:
            return value, None
        tag, digest = value.rsplit("@", 1)
        return tag, digest

    old_tag, old_digest = split(old)
    new_tag, new_digest = split(new)
    if old_tag == new_tag and old_digest and new_digest and old_digest != new_digest:
        leaf = new_tag.rsplit("/", 1)[-1]
        tag = leaf.rsplit(":", 1)[1] if ":" in leaf else None
        if tag is None:
            return "unknown", None
        tokens = re.split(r"[._-]+", tag.lower())
        prerelease = any(
            re.fullmatch(
                r"(?:a|alpha|b|beta|rc|pre|preview|dev|nightly|canary|edge|snapshot)\d*",
                token,
            )
            for token in tokens
        )
        if prerelease:
            return "patch", True
        version_tag = re.fullmatch(
            r"[vV]?\d+(?:\.\d+){0,2}(?:-([0-9A-Za-z][0-9A-Za-z.-]*))?",
            tag,
        )
        if version_tag is None:
            return "unknown", None
        qualifier = version_tag.group(1)
        if qualifier is None:
            return "patch", False
        stable_variant = re.compile(
            r"(?:slim|alpine\d*|bookworm|bullseye|buster|trixie|stretch|jessie|"
            r"jammy|focal|noble|bionic|debian\d*|ubuntu\d*|windowsservercore|"
            r"servercore|nanoserver|ltsc\d+|jdk|jre|ubi\d*|minimal|distroless|"
            r"rootless)"
        )
        variant_tokens = re.split(r"[._-]+", qualifier.lower())
        if all(
            token.isdigit() or stable_variant.fullmatch(token)
            for token in variant_tokens
        ):
            return "patch", False
        return "unknown", None
    old_version = old_tag.rsplit(":", 1)[-1]
    new_version = new_tag.rsplit(":", 1)[-1]
    return _semver_pair(old_version, new_version)


def _action_pair(
    old: str, new: str, raw_update_type: str | None
) -> tuple[str, bool | None]:
    old_ref = _ACTION_REF.fullmatch(old)
    new_ref = _ACTION_REF.fullmatch(new)
    if old_ref and new_ref:
        old_tuple = tuple(int(old_ref.group(index) or 0) for index in range(1, 4))
        new_tuple = tuple(int(new_ref.group(index) or 0) for index in range(1, 4))
        return _tuple_impact(old_tuple, new_tuple), new_ref.group(4) is not None
    if SHA40_RE.fullmatch(old.lower()) and SHA40_RE.fullmatch(new.lower()):
        match = re.search(r"semver-(patch|minor|major)", raw_update_type or "", re.I)
        if match:
            return match.group(1).lower(), False
        return "unknown", None
    return "non-semver", None


def classify_version(
    ecosystem: str,
    from_version: str | None,
    to_version: str | None,
    raw_update_type: str | None = None,
) -> tuple[str, bool | None]:
    """Return the normative observed impact and prerelease status."""

    if ecosystem not in ECOSYSTEMS or not from_version or not to_version:
        return "unknown", None
    if ecosystem == "npm":
        return _semver_pair(from_version, to_version)
    if ecosystem == "uv":
        return _pep440_pair(from_version, to_version)
    if ecosystem == "docker":
        return _docker_pair(from_version, to_version)
    if ecosystem == "github-actions":
        return _action_pair(from_version, to_version, raw_update_type)
    return "unknown", None


def aggregate_impact(impacts: Sequence[str]) -> str:
    if not impacts:
        return "unknown"
    rank = {"patch": 0, "minor": 1, "major": 2, "non-semver": 3, "unknown": 4}
    return max(impacts, key=lambda item: rank.get(item, 4))


def _ecosystem_for_files(files: Sequence[str]) -> str:
    lowered = [item.lower() for item in files]
    if any(item.startswith(".github/workflows/") for item in lowered):
        return "github-actions"
    if any(item.endswith("dockerfile") or "/dockerfile" in item for item in lowered):
        return "docker"
    if any(
        item.endswith(("pyproject.toml", "uv.lock"))
        or PurePosixPath(item).name.startswith("requirements")
        for item in lowered
    ):
        return "uv"
    if any(
        item.endswith(
            ("package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock")
        )
        for item in lowered
    ):
        return "npm"
    return "unknown"


def _dependency_paths(files: Sequence[str]) -> tuple[list[str], list[str]]:
    lock_names = {"pnpm-lock.yaml", "package-lock.json", "yarn.lock", "uv.lock"}
    lockfiles = sorted(
        {path for path in files if PurePosixPath(path).name in lock_names}
    )
    manifests: set[str] = set()
    for path in files:
        name = PurePosixPath(path).name.lower()
        if name in {
            "package.json",
            "pyproject.toml",
            "dockerfile",
            "compose.yml",
            "compose.yaml",
        }:
            manifests.add(path)
        elif name.startswith("requirements") and name.endswith((".txt", ".in")):
            manifests.add(path)
        elif path.lower().startswith(".github/workflows/") and name.endswith(
            (".yml", ".yaml")
        ):
            manifests.add(path)
    if not manifests:
        manifests.update(path for path in files if path not in lockfiles)
    if not manifests and lockfiles:
        manifests.add(lockfiles[0])
    return sorted(manifests), lockfiles


_BUMP_LINE = re.compile(
    r"^Bumps?[ \t]+(?:\[([^\]]+)\]\([^)]+\)|([^\s]+))[ \t]+from[ \t]+`?([^\s`]+)`?[ \t]+to[ \t]+`?([^\s`]+)`?",
    re.IGNORECASE | re.MULTILINE,
)
_UPDATE_LINE = re.compile(
    r"^Updates[ \t]+`([^`]+)`[ \t]+from[ \t]+`?([^\s`]+)`?[ \t]+to[ \t]+`?([^\s`]+)`?",
    re.IGNORECASE | re.MULTILINE,
)
_BUMP_TITLE = re.compile(
    r"^Bump\s+(.+?)\s+from\s+([^\s]+)\s+to\s+([^\s]+)", re.IGNORECASE
)
_DETAILS_TAG = re.compile(
    r"(?P<close></details\s*>)|(?P<open><details\b[^>]*>)",
    re.IGNORECASE,
)
_RAW_UPDATE_TYPE = re.compile(
    r"version-update:semver-(patch|minor|major)", re.IGNORECASE
)


def _clean_version(value: str) -> str:
    return value.strip().strip("`.,;:)")


def _trusted_body_surface(body: str) -> tuple[str, bool]:
    """Return top-level body text without expandable upstream content."""

    fragments: list[str] = []
    depth = 0
    cursor = 0
    for match in _DETAILS_TAG.finditer(body):
        if depth == 0:
            fragments.append(body[cursor : match.start()])
        if match.group("open") is not None:
            if depth == 0:
                fragments.append("\n")
            depth += 1
        else:
            if depth == 0:
                return "", False
            depth -= 1
        cursor = match.end()
    if depth != 0:
        return "", False
    fragments.append(body[cursor:])
    return "".join(fragments), True


def _dependency_identity(name: str, ecosystem: str) -> str:
    normalized = name.strip()
    if ecosystem == "uv":
        return re.sub(r"[-_.]+", "-", normalized).casefold()
    return normalized.casefold()


def _body_transitions(
    body: str, ecosystem: str
) -> tuple[list[tuple[str, str, str]], str]:
    surface, balanced = _trusted_body_surface(body)
    if not balanced:
        return [], ""

    observed: list[tuple[int, str, str, str]] = []
    for match in _BUMP_LINE.finditer(surface):
        observed.append(
            (
                match.start(),
                (match.group(1) or match.group(2)).strip(),
                _clean_version(match.group(3)),
                _clean_version(match.group(4)),
            )
        )
    for match in _UPDATE_LINE.finditer(surface):
        observed.append(
            (
                match.start(),
                match.group(1).strip(),
                _clean_version(match.group(2)),
                _clean_version(match.group(3)),
            )
        )
    observed.sort(key=lambda item: item[0])

    transitions: dict[str, tuple[str, str, str]] = {}
    for _, name, old, new in observed:
        identity = _dependency_identity(name, ecosystem)
        previous = transitions.get(identity)
        if previous is None:
            transitions[identity] = (name, old, new)
            continue
        if previous[1:] != (old, new):
            return [], surface
    return list(transitions.values()), surface


def _parse_dependencies(
    title: str,
    body: str,
    ecosystem: str,
    head_ref: str,
) -> list[dict[str, Any]]:
    parsed, trusted_body = _body_transitions(body, ecosystem)
    found: list[tuple[str, str | None, str | None]] = list(parsed)
    if not found:
        match = _BUMP_TITLE.search(title)
        if match:
            found.append(
                (
                    match.group(1).strip(),
                    _clean_version(match.group(2)),
                    _clean_version(match.group(3)),
                )
            )
    if not found:
        name = re.sub(r"^Bump\s+", "", title, flags=re.I).strip() or "unknown"
        found.append((name, None, None))
    raw_impacts = {
        match.group(1).lower()
        for match in _RAW_UPDATE_TYPE.finditer(f"{trusted_body}\n{head_ref}")
    }
    raw = (
        f"version-update:semver-{next(iter(raw_impacts))}"
        if len(raw_impacts) == 1 and len(found) == 1
        else None
    )
    dependencies: dict[tuple[str, str | None, str | None], dict[str, Any]] = {}
    for name, old, new in found:
        impact, prerelease = classify_version(ecosystem, old, new, raw)
        key = (_dependency_identity(name, ecosystem), old, new)
        dependencies[key] = {
            "name": name,
            "ecosystem": ecosystem,
            "fromVersion": old,
            "toVersion": new,
            "rawUpdateType": raw,
            "dependencyType": "unknown",
            "impact": impact,
            "prerelease": prerelease,
        }
    return sorted(
        dependencies.values(), key=lambda item: (item["name"], item["toVersion"] or "")
    )


def _page_api(runner: Runner, host: str, endpoint: str) -> list[Any]:
    collected: list[Any] = []
    page = 1
    while True:
        separator = "&" if "?" in endpoint else "?"
        value = _gh_api(runner, host, f"{endpoint}{separator}per_page=100&page={page}")
        if not isinstance(value, list):
            raise ExecutorError(
                EXIT_INCOMPLETE, "API", "Paginated GitHub response is not an array"
            )
        collected.extend(value)
        if len(value) < 100:
            return collected
        page += 1


def _inventory_error(error: ExecutorError) -> dict[str, Any]:
    allowed = {"ENV", "AUTH", "API", "RATE_LIMIT", "PARSE", "REPO_MISMATCH", "CONTRACT"}
    code = error.code if error.code in allowed else "CONTRACT"
    return {
        "code": code,
        "message": error.message,
        "prNumber": error.details.get("prNumber"),
        "transient": code in {"API", "RATE_LIMIT"},
    }


def _build_inventory_groups(
    pull_requests: Sequence[Mapping[str, Any]],
    parser_error_numbers: set[int],
    branch_shas: Mapping[tuple[str, str], str],
) -> list[dict[str, Any]]:
    batch_buckets: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    singleton_buckets: list[list[Mapping[str, Any]]] = []
    for pull in pull_requests:
        stable_low_risk = (
            pull["number"] not in parser_error_numbers
            and pull["observedAggregateImpact"] in {"patch", "minor"}
            and all(
                dependency["prerelease"] is False
                and dependency["impact"] in {"patch", "minor"}
                for dependency in pull["dependencies"]
            )
        )
        if stable_low_risk:
            batch_buckets.setdefault(
                (pull["base"]["repo"], pull["base"]["ref"]), []
            ).append(pull)
        else:
            singleton_buckets.append([pull])

    groups: list[dict[str, Any]] = []
    for bucket in [*batch_buckets.values(), *singleton_buckets]:
        first = bucket[0]
        branch = (first["base"]["repo"], first["base"]["ref"])
        base_sha = branch_shas.get(branch)
        if base_sha is None:
            continue
        ordered = sorted(bucket, key=lambda item: item["number"])
        source_lines = "".join(
            f"{pull['number']}@{pull['head']['sha']}\n" for pull in ordered
        )
        identity = f"v1\n{branch[0]}\n{branch[1]}@{base_sha}\n{source_lines}"
        groups.append(
            {
                "groupKey": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "base": {"repo": branch[0], "ref": branch[1], "sha": base_sha},
                "prNumbers": [pull["number"] for pull in ordered],
                "manifestPaths": sorted(
                    {path for pull in ordered for path in pull["manifests"]}
                ),
                "observedAggregateImpact": aggregate_impact(
                    [pull["observedAggregateImpact"] for pull in ordered]
                ),
            }
        )
    return sorted(groups, key=lambda item: item["groupKey"])


def _resolve_group_branch_shas(
    pull_requests: Sequence[Mapping[str, Any]],
    repository: Mapping[str, Any],
    runner: Runner,
    errors: list[dict[str, Any]],
) -> dict[tuple[str, str], str]:
    branch_shas: dict[tuple[str, str], str] = {}
    attempted: set[tuple[str, str]] = set()
    for pull in pull_requests:
        branch = (str(pull["base"]["repo"]), str(pull["base"]["ref"]))
        if branch in attempted:
            continue
        attempted.add(branch)
        if branch[1] == repository["defaultBranch"]:
            branch_shas[branch] = str(repository["defaultBranchSha"])
            continue
        try:
            current_sha = _current_ref_sha(runner, repository, branch[1])
        except ExecutorError as exc:
            errors.append(
                {
                    "code": "API",
                    "message": (
                        f"Could not resolve base branch {branch[1]}: {exc.message}"
                    ),
                    "prNumber": pull["number"],
                    "transient": True,
                }
            )
            continue
        if current_sha is None:
            errors.append(
                {
                    "code": "API",
                    "message": f"Base branch {branch[1]} is unavailable",
                    "prNumber": pull["number"],
                    "transient": True,
                }
            )
            continue
        branch_shas[branch] = current_sha
    return branch_shas


def inspect_repository(
    root: str | Path,
    now: str | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Build a complete, sorted inventory without mutating Git or GitHub."""

    runner = runner or Runner()
    generated_at = _utc_now(now)
    fatal: dict[str, Any] = {
        "schemaVersion": 1,
        "complete": False,
        "generatedAt": generated_at,
        "repository": None,
        "pullRequests": [],
        "overlaps": [],
        "groups": [],
        "errors": [],
    }
    try:
        repository = _resolve_repository(root, runner)
    except ExecutorError as exc:
        fatal["errors"] = [_inventory_error(exc)]
        return fatal

    inventory = dict(fatal)
    inventory["repository"] = repository
    host = repository["host"]
    repo = repository["nameWithOwner"]
    try:
        raw_prs = _page_api(runner, host, f"repos/{repo}/pulls?state=open")
    except ExecutorError as exc:
        inventory["errors"] = [_inventory_error(exc)]
        return inventory

    pull_requests: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for raw in raw_prs:
        if not isinstance(raw, dict):
            errors.append(
                {
                    "code": "CONTRACT",
                    "message": "Pull request is not an object",
                    "prNumber": None,
                    "transient": False,
                }
            )
            continue
        user = raw.get("user") or raw.get("author")
        if not isinstance(user, dict):
            continue
        source_login = str(user.get("login", ""))
        source_type = str(user.get("type", ""))
        if (
            source_login not in {"dependabot[bot]", "app/dependabot"}
            or source_type != "Bot"
        ):
            continue
        try:
            number = int(raw["number"])
            base = raw["base"]
            head = raw["head"]
            base_repo = base["repo"]["full_name"]
            head_repo = head["repo"]["full_name"] if head.get("repo") else repo
            if str(base_repo).lower() != repo.lower():
                raise ExecutorError(
                    EXIT_CONTRACT,
                    "REPO_MISMATCH",
                    "PR base repository differs from origin",
                    {"prNumber": number},
                )
            base_sha = str(base["sha"]).lower()
            head_sha = str(head["sha"]).lower()
            if not SHA40_RE.fullmatch(base_sha) or not SHA40_RE.fullmatch(head_sha):
                raise ValueError("invalid SHA")
            files_raw = _page_api(runner, host, f"repos/{repo}/pulls/{number}/files")
            files = sorted(
                {
                    _safe_path(str(item["filename"]))
                    for item in files_raw
                    if isinstance(item, dict) and "filename" in item
                }
            )
            manifests, lockfiles = _dependency_paths(files)
            if not manifests:
                raise ExecutorError(
                    EXIT_CONTRACT,
                    "CONTRACT",
                    "No dependency manifest could be identified",
                    {"prNumber": number},
                )
            title = str(raw.get("title") or "")
            body = str(raw.get("body") or "")
            ecosystem = _ecosystem_for_files(files)
            dependencies = _parse_dependencies(
                title, body, ecosystem, str(head.get("ref") or "")
            )
            if any(
                item["fromVersion"] is None or item["toVersion"] is None
                for item in dependencies
            ):
                errors.append(
                    {
                        "code": "PARSE",
                        "message": "Dependabot dependency versions could not be parsed",
                        "prNumber": number,
                        "transient": False,
                    }
                )
            parsed = {
                "number": number,
                "url": str(raw.get("html_url") or raw.get("url") or ""),
                "title": title,
                "body": body,
                "author": {
                    "login": "dependabot[bot]",
                    "type": "Bot",
                    "sourceLogin": source_login,
                },
                "base": {
                    "repo": str(base_repo),
                    "ref": str(base["ref"]),
                    "sha": base_sha,
                },
                "head": {
                    "repo": str(head_repo),
                    "ref": str(head["ref"]),
                    "sha": head_sha,
                },
                "maintainerCanModify": raw.get("maintainer_can_modify")
                if isinstance(raw.get("maintainer_can_modify"), bool)
                else None,
                "files": files,
                "manifests": manifests,
                "lockfiles": lockfiles,
                "dependencies": dependencies,
                "observedAggregateImpact": aggregate_impact(
                    [item["impact"] for item in dependencies]
                ),
                "securityUpdate": any(
                    "security" in str(label.get("name", "")).lower()
                    for label in raw.get("labels", [])
                    if isinstance(label, dict)
                ),
            }
            pull_requests.append(parsed)
        except ExecutorError as exc:
            error = _inventory_error(exc)
            error["prNumber"] = error["prNumber"] or raw.get("number")
            errors.append(error)
        except (KeyError, TypeError, ValueError) as exc:
            number_value = (
                raw.get("number") if isinstance(raw.get("number"), int) else None
            )
            errors.append(
                {
                    "code": "CONTRACT",
                    "message": f"Malformed Dependabot PR metadata: {exc}",
                    "prNumber": number_value,
                    "transient": False,
                }
            )

    pull_requests.sort(key=lambda item: item["number"])
    overlaps: list[dict[str, Any]] = []
    for kind, field in (("manifest", "manifests"), ("lockfile", "lockfiles")):
        mapping: dict[str, list[int]] = {}
        for pull in pull_requests:
            for key in pull[field]:
                mapping.setdefault(key, []).append(pull["number"])
        overlaps.extend(
            {"kind": kind, "key": key, "prNumbers": sorted(numbers)}
            for key, numbers in mapping.items()
            if len(numbers) >= 2
        )
    dependency_mapping: dict[str, list[int]] = {}
    for pull in pull_requests:
        for dependency in pull["dependencies"]:
            dependency_mapping.setdefault(
                f"{dependency['ecosystem']}:{dependency['name']}", []
            ).append(pull["number"])
    overlaps.extend(
        {"kind": "dependency", "key": key, "prNumbers": sorted(set(numbers))}
        for key, numbers in dependency_mapping.items()
        if len(set(numbers)) >= 2
    )
    overlaps.sort(key=lambda item: (item["kind"], item["key"]))

    parser_error_numbers = {
        item["prNumber"] for item in errors if item["code"] == "PARSE"
    }
    branch_shas = _resolve_group_branch_shas(pull_requests, repository, runner, errors)

    groups = _build_inventory_groups(pull_requests, parser_error_numbers, branch_shas)
    errors.sort(key=lambda item: (item["code"], item["prNumber"] or 0))
    inventory.update(
        {
            "complete": not any(
                item["code"]
                in {"ENV", "AUTH", "API", "RATE_LIMIT", "REPO_MISMATCH", "CONTRACT"}
                for item in errors
            ),
            "pullRequests": pull_requests,
            "overlaps": overlaps,
            "groups": groups,
            "errors": errors,
        }
    )
    return inventory


def _contract(condition: bool, message: str, **details: Any) -> None:
    if not condition:
        raise ExecutorError(EXIT_CONTRACT, "CONTRACT", message, details)


def _exact_object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    _contract(isinstance(value, dict), f"{label} must be an object")
    actual = set(value)
    _contract(
        actual == fields,
        f"{label} has unexpected or missing fields",
        expected=sorted(fields),
        actual=sorted(actual),
    )
    return value


def _sorted_unique_strings(
    value: Any, label: str, *, nonempty: bool = False
) -> list[str]:
    _contract(isinstance(value, list), f"{label} must be an array")
    _contract(
        all(isinstance(item, str) and item for item in value),
        f"{label} must contain non-empty strings",
    )
    _contract(value == sorted(set(value)), f"{label} must be sorted and unique")
    if nonempty:
        _contract(bool(value), f"{label} cannot be empty")
    return value


def _version_key(value: Mapping[str, Any]) -> tuple[str, str, str]:
    return str(value["name"]), str(value["ecosystem"]), str(value["to"])


def _source_version_key(value: Mapping[str, Any]) -> tuple[str, str, Any, Any]:
    return value["name"], value["ecosystem"], value["from"], value["to"]


def _release_subject(value: Mapping[str, Any]) -> str:
    name = _dependency_identity(str(value["name"]), str(value["ecosystem"]))
    return f"{value['ecosystem']}:{name}@{value['to']}"


def _effective_impact(versions: Sequence[Mapping[str, Any]]) -> str:
    rank = {"patch": 0, "minor": 1, "major": 2, "non-semver": 2, "unknown": 2}
    if not versions:
        return "major"
    observed = max(
        (str(item["impact"]) for item in versions), key=lambda value: rank.get(value, 2)
    )
    return observed if observed in {"patch", "minor"} else "major"


def _validate_release_evidence(
    value: Any, *, structured_summary: bool = False
) -> list[dict[str, Any]]:
    _contract(isinstance(value, list), "stabilityEvidence must be an array")
    fields = {"kind", "subject", "url", "summary", "contentSha256"}
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        item = _exact_object(raw, fields, f"stabilityEvidence[{index}]")
        _contract(
            item["kind"] in {"registry", "release", "changelog", "compatibility"},
            "Invalid release evidence kind",
        )
        for key in ("subject", "url", "summary"):
            _contract(
                isinstance(item[key], str) and item[key].strip(),
                f"Release evidence {key} must be non-empty",
            )
        _contract(
            isinstance(item["contentSha256"], str)
            and SHA256_RE.fullmatch(item["contentSha256"]),
            "Release evidence digest is invalid",
        )
        if structured_summary:
            summary = str(item["summary"]).strip()
            summary_match = re.fullmatch(
                r"breaking=(none|applicable|not-applicable); adaptation=(not-required|.+)",
                summary,
            )
            _contract(
                summary_match is not None,
                "Release evidence summary must describe breaking changes and adaptation",
            )
            _contract(
                summary_match.group(1) != "applicable"
                or summary_match.group(2) != "not-required",
                "Applicable breaking changes require an adaptation",
            )
        result.append(item)
    _contract(
        len({canonical_json(item) for item in result}) == len(result),
        "stabilityEvidence must be unique",
    )
    return result


def _validate_closure_evidence(
    value: Any, sources: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    _contract(isinstance(value, list), "closureEvidence must be an array")
    _contract(
        len(value) == len(sources),
        "A closure requires exactly one evidence item per source",
    )
    fields = {
        "sourceNumber",
        "predicate",
        "subject",
        "observed",
        "url",
        "contentSha256",
        "replacementPrNumber",
        "replacementMergeSha",
    }
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        item = _exact_object(raw, fields, f"closureEvidence[{index}]")
        _contract(
            item["predicate"]
            in {
                "version-prerelease",
                "replacement-merged",
                "human-reviewed",
                "user-decision",
            },
            "Invalid closure predicate",
        )
        _contract(
            isinstance(item["sourceNumber"], int) and item["sourceNumber"] > 0,
            "Invalid closure source number",
        )
        _contract(
            isinstance(item["subject"], str) and item["subject"],
            "Closure evidence subject is required",
        )
        _contract(
            isinstance(item["observed"], str) and item["observed"],
            "Closure evidence observation is required",
        )
        _contract(
            item["url"] is None or isinstance(item["url"], str),
            "Closure evidence URL is invalid",
        )
        _contract(
            item["contentSha256"] is None
            or (
                isinstance(item["contentSha256"], str)
                and SHA256_RE.fullmatch(item["contentSha256"])
            ),
            "Closure evidence digest is invalid",
        )
        if item["predicate"] == "replacement-merged":
            _contract(
                isinstance(item["url"], str) and bool(item["url"]),
                "Replacement evidence requires a URL",
            )
            _contract(
                isinstance(item["replacementPrNumber"], int)
                and item["replacementPrNumber"] > 0,
                "Replacement evidence requires a PR number",
            )
            _contract(
                isinstance(item["replacementMergeSha"], str)
                and SHA40_RE.fullmatch(item["replacementMergeSha"]),
                "Replacement evidence requires a merge SHA",
            )
        else:
            _contract(
                item["replacementPrNumber"] is None
                and item["replacementMergeSha"] is None,
                "Non-replacement evidence cannot name a replacement",
            )
        if item["predicate"] == "human-reviewed":
            _contract(
                isinstance(item["url"], str) and bool(item["url"]),
                "Human-reviewed evidence requires a URL",
            )
            _contract(
                isinstance(item["contentSha256"], str)
                and SHA256_RE.fullmatch(item["contentSha256"]),
                "Human-reviewed evidence requires a digest",
            )
        if item["predicate"] == "user-decision":
            _contract(
                item["url"] is None and item["contentSha256"] is None,
                "User-decision evidence has no external URL or digest",
            )
        result.append(item)
    _contract(
        [item["sourceNumber"] for item in result]
        == [item["number"] for item in sources],
        "Closure evidence must follow source order",
    )
    return result


def _validate_candidate(
    inventory: dict[str, Any], candidate: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_fields = {
        "schemaVersion",
        "repository",
        "base",
        "groupKey",
        "sources",
        "manifestPaths",
        "versions",
        "additionalDependencies",
        "observedAggregateImpact",
        "effectiveImpact",
        "impactRationale",
        "decision",
        "closureReason",
        "parentPlanDigest",
        "stabilityEvidence",
        "closureEvidence",
        "mode",
        "targetPrNumber",
        "commitSha",
        "treeSha",
        "validation",
    }
    _exact_object(candidate, candidate_fields, "candidate")
    _contract(candidate["schemaVersion"] == 1, "Unsupported candidate schema version")
    _contract(
        inventory.get("schemaVersion") == 1, "Unsupported inventory schema version"
    )
    _contract(
        inventory.get("complete") is True, "Incomplete inventory cannot be planned"
    )
    repository = inventory.get("repository")
    _contract(isinstance(repository, dict), "Resolved inventory repository is required")
    _contract(
        candidate["repository"] == repository,
        "Candidate repository differs from inventory",
    )
    groups = inventory.get("groups")
    _contract(isinstance(groups, list), "Inventory groups are invalid")
    matches = [
        item
        for item in groups
        if isinstance(item, dict) and item.get("groupKey") == candidate["groupKey"]
    ]
    _contract(len(matches) == 1, "Candidate must reference exactly one inventory group")
    group = matches[0]
    _contract(
        candidate["base"] == group.get("base"), "Candidate base differs from its group"
    )
    _contract(
        isinstance(candidate["groupKey"], str)
        and SHA256_RE.fullmatch(candidate["groupKey"]),
        "Invalid group key",
    )

    sources = candidate["sources"]
    _contract(
        isinstance(sources, list) and bool(sources),
        "Candidates require at least one source",
    )
    source_fields = {"number", "headSha"}
    for index, source in enumerate(sources):
        _exact_object(source, source_fields, f"sources[{index}]")
        _contract(
            isinstance(source["number"], int) and source["number"] > 0,
            "Invalid source number",
        )
        _contract(
            isinstance(source["headSha"], str)
            and SHA40_RE.fullmatch(source["headSha"]),
            "Invalid source SHA",
        )
    _contract(
        sources == sorted(sources, key=lambda item: item["number"]),
        "Sources must be sorted",
    )
    _contract(
        len({item["number"] for item in sources}) == len(sources),
        "Sources must be unique",
    )
    _contract(
        {item["number"] for item in sources}.issubset(set(group.get("prNumbers", []))),
        "Sources are not a subset of the inventory group",
    )
    pulls = {
        item["number"]: item
        for item in inventory.get("pullRequests", [])
        if isinstance(item, dict) and isinstance(item.get("number"), int)
    }
    for source in sources:
        pull = pulls.get(source["number"])
        _contract(pull is not None, "Candidate source is missing from inventory")
        _contract(
            pull.get("head", {}).get("sha") == source["headSha"],
            "Candidate source head is stale",
        )
        pull_base = pull.get("base", {})
        _contract(
            pull_base.get("repo") == candidate["base"]["repo"]
            and pull_base.get("ref") == candidate["base"]["ref"],
            "Candidate mixes base repositories or refs",
        )
        _contract(
            not any(
                error.get("code") == "PARSE"
                and error.get("prNumber") == source["number"]
                for error in inventory.get("errors", [])
                if isinstance(error, dict)
            ),
            "A source with parser errors cannot be planned",
        )

    selected_pulls = [pulls[source["number"]] for source in sources]
    for index, left in enumerate(selected_pulls):
        left_dependencies = {
            _dependency_identity(item["name"], item["ecosystem"]): item["toVersion"]
            for item in left.get("dependencies", [])
        }
        for right in selected_pulls[index + 1 :]:
            if not set(left.get("manifests", [])).intersection(
                right.get("manifests", [])
            ):
                continue
            for item in right.get("dependencies", []):
                identity = _dependency_identity(item["name"], item["ecosystem"])
                if (
                    identity in left_dependencies
                    and left_dependencies[identity] != item["toVersion"]
                ):
                    _contract(
                        False,
                        "Sources target incompatible versions in the same manifest",
                        dependency=identity,
                    )

    manifests = _sorted_unique_strings(
        candidate["manifestPaths"], "manifestPaths", nonempty=True
    )
    for path in manifests:
        _safe_path(path)
    _contract(
        manifests
        == sorted(
            {path for pull in selected_pulls for path in pull.get("manifests", [])}
        ),
        "Candidate manifests differ from its selected sources",
    )
    _contract(
        candidate["observedAggregateImpact"]
        == aggregate_impact(
            [pull["observedAggregateImpact"] for pull in selected_pulls]
        ),
        "Observed aggregate impact differs from selected sources",
    )
    _contract(
        candidate["observedAggregateImpact"] in IMPACTS,
        "Invalid observed aggregate impact",
    )
    _contract(
        isinstance(candidate["impactRationale"], str)
        and candidate["impactRationale"].strip(),
        "Impact rationale is required",
    )

    versions = candidate["versions"]
    _contract(isinstance(versions, list) and versions, "versions cannot be empty")
    version_fields = {"name", "ecosystem", "from", "to", "impact", "prerelease"}
    for index, version in enumerate(versions):
        _exact_object(version, version_fields, f"versions[{index}]")
        _contract(
            isinstance(version["name"], str) and version["name"],
            "Version name is required",
        )
        _contract(version["ecosystem"] in ECOSYSTEMS, "Invalid version ecosystem")
        _contract(
            version["from"] is None or isinstance(version["from"], str),
            "Version from value is invalid",
        )
        _contract(
            isinstance(version["to"], str) and version["to"],
            "Version to value is required",
        )
        _contract(
            isinstance(version["impact"], str) and version["impact"] in IMPACTS,
            "Version impact is invalid",
            name=version["name"],
        )
        _contract(
            version["prerelease"] is None or isinstance(version["prerelease"], bool),
            "Version prerelease flag is invalid",
            name=version["name"],
        )
    _contract(versions == sorted(versions, key=_version_key), "Versions must be sorted")

    additions = candidate["additionalDependencies"]
    _contract(isinstance(additions, list), "additionalDependencies must be an array")
    addition_fields = {"name", "ecosystem", "reason", "evidenceUrl"}
    for index, addition in enumerate(additions):
        _exact_object(addition, addition_fields, f"additionalDependencies[{index}]")
        _contract(
            addition["ecosystem"] in ECOSYSTEMS,
            "Invalid additional dependency ecosystem",
        )
        for key in ("name", "reason", "evidenceUrl"):
            _contract(
                isinstance(addition[key], str) and addition[key].strip(),
                f"Additional dependency {key} is required",
            )
    _contract(
        additions
        == sorted(additions, key=lambda item: (item["name"], item["ecosystem"])),
        "Additional dependencies must be sorted",
    )
    _contract(
        len({canonical_json(item) for item in additions}) == len(additions),
        "Additional dependencies must be unique",
    )

    source_versions: list[dict[str, Any]] = []
    for source in sources:
        for dependency in pulls[source["number"]].get("dependencies", []):
            source_versions.append(
                {
                    "name": dependency["name"],
                    "ecosystem": dependency["ecosystem"],
                    "from": dependency["fromVersion"],
                    "to": dependency["toVersion"],
                }
            )
    expected_source = Counter(_source_version_key(item) for item in source_versions)
    addition_names = Counter((item["name"], item["ecosystem"]) for item in additions)
    candidate_source: Counter[tuple[str, str, Any, Any]] = Counter()
    candidate_additions: Counter[tuple[str, str]] = Counter()
    for version in versions:
        identity = (version["name"], version["ecosystem"])
        full = _source_version_key(version)
        if expected_source[full] > candidate_source[full]:
            candidate_source[full] += 1
        else:
            candidate_additions[identity] += 1
    _contract(
        candidate_source == expected_source,
        "Candidate versions are not an exact projection of source dependencies",
    )
    _contract(
        candidate_additions == addition_names,
        "Additional dependency declarations do not match additional versions",
    )

    source_details: dict[tuple[str, str, Any, Any], list[dict[str, Any]]] = {}
    for source in sources:
        for dependency in pulls[source["number"]].get("dependencies", []):
            key = (
                dependency["name"],
                dependency["ecosystem"],
                dependency["fromVersion"],
                dependency["toVersion"],
            )
            source_details.setdefault(key, []).append(dependency)
    for version in versions:
        key = _source_version_key(version)
        details = source_details.get(key, [])
        if details:
            dependency = details.pop(0)
            expected_classification = (dependency["impact"], dependency["prerelease"])
        else:
            expected_classification = classify_version(
                version["ecosystem"],
                version["from"],
                version["to"],
            )
        _contract(
            (version["impact"], version["prerelease"]) == expected_classification,
            "Version classification does not match its source metadata",
            name=version["name"],
        )

    effective = _effective_impact(versions)
    _contract(
        candidate["effectiveImpact"] == effective,
        "Effective impact does not match the normative maximum",
    )
    _contract(
        candidate["effectiveImpact"] in {"patch", "minor", "major"},
        "Invalid effective impact",
    )

    decision = candidate["decision"]
    _contract(
        decision in {"update", "close-nonapplicable", "close-declined-major"},
        "Invalid candidate decision",
    )
    release_evidence = _validate_release_evidence(
        candidate["stabilityEvidence"], structured_summary=len(sources) > 1
    )
    closure_evidence = (
        _validate_closure_evidence(candidate["closureEvidence"], sources)
        if decision != "update"
        else candidate["closureEvidence"]
    )
    if decision == "update":
        _contract(
            candidate["closureReason"] is None
            and candidate["parentPlanDigest"] is None,
            "Update cannot carry closure metadata",
        )
        _contract(
            candidate["mode"] in {"direct", "replacement"}, "Update mode is required"
        )
        _contract(
            isinstance(candidate["commitSha"], str)
            and SHA40_RE.fullmatch(candidate["commitSha"]),
            "Update commit SHA is invalid",
        )
        _contract(
            isinstance(candidate["treeSha"], str)
            and SHA40_RE.fullmatch(candidate["treeSha"]),
            "Update tree SHA is invalid",
        )
        _contract(bool(release_evidence), "Update requires stability evidence")
        if len(sources) > 1:
            required_evidence = {_release_subject(version) for version in versions}
            observed_evidence = {item["subject"] for item in release_evidence}
            _contract(
                required_evidence.issubset(observed_evidence),
                "Release evidence must cover every target dependency",
                missing=sorted(required_evidence - observed_evidence),
            )
        _contract(closure_evidence == [], "Update cannot carry closure evidence")
        _contract(
            not any(item["prerelease"] is True for item in versions),
            "Prerelease updates cannot be planned for merge",
        )
        if candidate["mode"] == "direct":
            _contract(
                len(sources) == 1,
                "Direct updates require exactly one source",
            )
            _contract(
                candidate["targetPrNumber"] == sources[0]["number"],
                "Direct update target must be its source",
            )
            _contract(
                candidate["commitSha"] == sources[0]["headSha"],
                "Direct update commit must be source head",
            )
        else:
            _contract(
                candidate["targetPrNumber"] is None,
                "Replacement cannot have a target PR number",
            )
        validation = candidate["validation"]
        _contract(
            isinstance(validation, list) and validation,
            "Update requires successful validation results",
        )
        validation_fields = {"command", "exitCode", "treeSha", "finishedAt"}
        for index, check in enumerate(validation):
            _exact_object(check, validation_fields, f"validation[{index}]")
            _contract(
                isinstance(check["command"], str) and check["command"],
                "Validation command is required",
            )
            _contract(check["exitCode"] == 0, "All validation commands must succeed")
            _contract(
                check["treeSha"] == candidate["treeSha"],
                "Validation result targets a different tree",
            )
            _utc_now(check["finishedAt"])
        _contract(
            len({canonical_json(item) for item in validation}) == len(validation),
            "Validation results must be unique",
        )
    else:
        reasons = {
            "prerelease",
            "withdrawn",
            "duplicate-merged",
            "already-in-base",
            "unsupported-platform",
            "superseded-merged",
            "major-declined",
        }
        _contract(candidate["closureReason"] in reasons, "Invalid closure reason")
        _contract(
            candidate["mode"] is None and candidate["targetPrNumber"] is None,
            "Closure cannot carry update targets",
        )
        _contract(
            candidate["commitSha"] is None and candidate["treeSha"] is None,
            "Closure cannot carry Git objects",
        )
        _contract(
            candidate["validation"] == [] and release_evidence == [],
            "Closure cannot carry update validation or stability evidence",
        )
        predicate_for_reason = {
            "prerelease": "version-prerelease",
            "duplicate-merged": "replacement-merged",
            "superseded-merged": "replacement-merged",
            "withdrawn": "human-reviewed",
            "already-in-base": "human-reviewed",
            "unsupported-platform": "human-reviewed",
            "major-declined": "user-decision",
        }
        _contract(
            all(
                item["predicate"] == predicate_for_reason[candidate["closureReason"]]
                for item in closure_evidence
            ),
            "Closure reason and evidence predicate differ",
        )
        if candidate["closureReason"] == "prerelease":
            for source in sources:
                source_deps = pulls[source["number"]].get("dependencies", [])
                _contract(
                    any(item.get("prerelease") is True for item in source_deps),
                    "Prerelease closure is not supported by source versions",
                )
        if decision == "close-declined-major":
            _contract(
                candidate["closureReason"] == "major-declined",
                "Declined-major decision requires major-declined reason",
            )
            _contract(
                isinstance(candidate["parentPlanDigest"], str)
                and SHA256_RE.fullmatch(candidate["parentPlanDigest"]),
                "Declined major requires a parent plan digest",
            )
        else:
            _contract(
                candidate["closureReason"] != "major-declined"
                and candidate["parentPlanDigest"] is None,
                "Nonapplicable closure cannot claim a declined major",
            )
    return group, pulls[sources[0]["number"]]


def _source_identity(candidate: Mapping[str, Any]) -> str:
    lines = [
        "v1",
        candidate["repository"]["nameWithOwner"],
        f"{candidate['base']['ref']}@{candidate['base']['sha']}",
        *candidate["manifestPaths"],
        *(f"{source['number']}@{source['headSha']}" for source in candidate["sources"]),
    ]
    return "\n".join(lines) + "\n"


def _manifest_slug(path: str) -> str:
    value = (
        re.sub(r"[^0-9A-Za-z]+", "-", path.lstrip("/"))
        .lower()
        .strip("-")[:32]
        .strip("-")
    )
    return value or "root"


def _plan_digest_payload(plan: Mapping[str, Any]) -> dict[str, Any]:
    approval = plan["approval"]
    return {
        "schemaVersion": plan["schemaVersion"],
        "sourceHash": plan["sourceHash"],
        "candidate": plan["candidate"],
        "destinationBranch": plan["destinationBranch"],
        "operations": plan["operations"],
        "approval": {
            "kind": approval["kind"],
            "required": approval["required"],
            "parentPlanDigest": approval["parentPlanDigest"],
        },
    }


def _verify_plan_digest(plan: dict[str, Any]) -> None:
    fields = {
        "schemaVersion",
        "planDigest",
        "sourceHash",
        "createdAt",
        "candidate",
        "destinationBranch",
        "operations",
        "approval",
    }
    _exact_object(plan, fields, "plan")
    _contract(plan["schemaVersion"] == 1, "Unsupported plan schema version")
    _contract(
        isinstance(plan["sourceHash"], str)
        and SOURCE_HASH_RE.fullmatch(plan["sourceHash"]),
        "Invalid source hash",
    )
    _contract(
        isinstance(plan["planDigest"], str) and SHA256_RE.fullmatch(plan["planDigest"]),
        "Invalid plan digest",
    )
    _utc_now(plan["createdAt"])
    calculated = canonical_digest(_plan_digest_payload(plan))
    _contract(
        calculated == plan["planDigest"], "Plan digest does not match its contents"
    )
    approval = _exact_object(
        plan["approval"],
        {
            "kind",
            "required",
            "approveToken",
            "rejectToken",
            "closeToken",
            "parentPlanDigest",
        },
        "approval",
    )
    digest = plan["planDigest"]
    expected: dict[str, tuple[Any, ...]] = {
        "none": (False, None, None, None, None),
        "update-major": (True, f"approve:{digest}", f"reject:{digest}", None, None),
        "close-reviewed": (True, None, None, f"close:{digest}", None),
        "reject-major": (
            True,
            None,
            f"reject:{approval['parentPlanDigest']}",
            None,
            approval["parentPlanDigest"],
        ),
    }
    _contract(approval["kind"] in expected, "Invalid approval kind")
    actual = (
        approval["required"],
        approval["approveToken"],
        approval["rejectToken"],
        approval["closeToken"],
        approval["parentPlanDigest"],
    )
    _contract(
        actual == expected[approval["kind"]],
        "Approval tokens do not match the plan digest",
    )


def build_plan(
    inventory: dict[str, Any],
    candidate: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    """Validate an offline candidate and return an immutable plan-v1 object."""

    _validate_candidate(inventory, candidate)
    candidate_copy = json.loads(json.dumps(candidate))
    source_hash = hashlib.sha256(
        _source_identity(candidate_copy).encode("utf-8")
    ).hexdigest()[:12]
    decision = candidate_copy["decision"]
    mode = candidate_copy["mode"]
    destination: str | None = None
    operations: list[dict[str, str]]
    if decision == "update" and mode == "direct":
        source = candidate_copy["sources"][0]
        operations = [
            {
                "name": "merge",
                "target": f"source:{source['number']}@{source['headSha']}",
            }
        ]
    elif decision == "update" and mode == "replacement":
        destination = f"automation/dependabot/{_manifest_slug(candidate_copy['manifestPaths'][0])}-{source_hash}"
        operations = [
            {"name": "push", "target": f"branch:{destination}"},
            {"name": "create-replacement", "target": "replacement"},
            {"name": "merge", "target": "replacement"},
            *(
                {
                    "name": "close-source",
                    "target": f"source:{source['number']}@{source['headSha']}",
                }
                for source in candidate_copy["sources"]
            ),
        ]
    else:
        operations = [
            {
                "name": "close-source",
                "target": f"source:{source['number']}@{source['headSha']}",
            }
            for source in candidate_copy["sources"]
        ]

    if decision == "update" and candidate_copy["effectiveImpact"] == "major":
        kind, required, parent = "update-major", True, None
    elif decision == "close-declined-major":
        kind, required, parent = (
            "reject-major",
            True,
            candidate_copy["parentPlanDigest"],
        )
    elif decision != "update" and any(
        item["predicate"] == "human-reviewed"
        for item in candidate_copy["closureEvidence"]
    ):
        kind, required, parent = "close-reviewed", True, None
    else:
        kind, required, parent = "none", False, None
    plan: dict[str, Any] = {
        "schemaVersion": 1,
        "planDigest": "",
        "sourceHash": source_hash,
        "createdAt": _utc_now(created_at),
        "candidate": candidate_copy,
        "destinationBranch": destination,
        "operations": operations,
        "approval": {
            "kind": kind,
            "required": required,
            "approveToken": None,
            "rejectToken": None,
            "closeToken": None,
            "parentPlanDigest": parent,
        },
    }
    digest = canonical_digest(_plan_digest_payload(plan))
    plan["planDigest"] = digest
    if kind == "update-major":
        plan["approval"]["approveToken"] = f"approve:{digest}"
        plan["approval"]["rejectToken"] = f"reject:{digest}"
    elif kind == "close-reviewed":
        plan["approval"]["closeToken"] = f"close:{digest}"
    elif kind == "reject-major":
        plan["approval"]["rejectToken"] = f"reject:{parent}"
    _verify_plan_digest(plan)
    return plan


def _expected_operations(
    candidate: Mapping[str, Any], destination: str | None
) -> list[dict[str, str]]:
    sources = candidate["sources"]
    if candidate["decision"] == "update" and candidate["mode"] == "direct":
        return [
            {
                "name": "merge",
                "target": f"source:{sources[0]['number']}@{sources[0]['headSha']}",
            }
        ]
    if candidate["decision"] == "update" and candidate["mode"] == "replacement":
        return [
            {"name": "push", "target": f"branch:{destination}"},
            {"name": "create-replacement", "target": "replacement"},
            {"name": "merge", "target": "replacement"},
            *(
                {
                    "name": "close-source",
                    "target": f"source:{source['number']}@{source['headSha']}",
                }
                for source in sources
            ),
        ]
    return [
        {
            "name": "close-source",
            "target": f"source:{source['number']}@{source['headSha']}",
        }
        for source in sources
    ]


def _verify_plan_structure(plan: dict[str, Any]) -> None:
    _verify_plan_digest(plan)
    candidate = plan["candidate"]
    _contract(isinstance(candidate, dict), "Plan candidate is invalid")
    required = {
        "schemaVersion",
        "repository",
        "base",
        "groupKey",
        "sources",
        "manifestPaths",
        "versions",
        "additionalDependencies",
        "observedAggregateImpact",
        "effectiveImpact",
        "impactRationale",
        "decision",
        "closureReason",
        "parentPlanDigest",
        "stabilityEvidence",
        "closureEvidence",
        "mode",
        "targetPrNumber",
        "commitSha",
        "treeSha",
        "validation",
    }
    _exact_object(candidate, required, "candidate")
    _contract(candidate["schemaVersion"] == 1, "Unsupported candidate schema")
    sources = candidate["sources"]
    _contract(
        isinstance(sources, list) and bool(sources),
        "Plan must have at least one source",
    )
    for source in sources:
        _exact_object(source, {"number", "headSha"}, "source")
        _contract(
            isinstance(source["number"], int) and source["number"] > 0,
            "Invalid source number",
        )
        _contract(
            isinstance(source["headSha"], str)
            and SHA40_RE.fullmatch(source["headSha"]),
            "Invalid source head",
        )
    _contract(
        sources == sorted(sources, key=lambda item: item["number"])
        and len({item["number"] for item in sources}) == len(sources),
        "Plan sources must be sorted and unique",
    )
    repository = _exact_object(
        candidate["repository"],
        {
            "host",
            "nameWithOwner",
            "remote",
            "root",
            "defaultBranch",
            "defaultBranchSha",
            "actorLogin",
        },
        "candidate.repository",
    )
    for key in ("host", "nameWithOwner", "root", "defaultBranch", "actorLogin"):
        _contract(
            isinstance(repository[key], str) and bool(repository[key]),
            f"Candidate repository {key} is invalid",
        )
    _contract(
        repository["remote"] == "origin", "Candidate repository remote must be origin"
    )
    _contract(
        isinstance(repository["defaultBranchSha"], str)
        and SHA40_RE.fullmatch(repository["defaultBranchSha"]),
        "Candidate default branch SHA is invalid",
    )
    base = _exact_object(candidate["base"], {"repo", "ref", "sha"}, "candidate.base")
    for key in ("repo", "ref", "sha"):
        _contract(
            isinstance(base[key], str) and bool(base[key]),
            "Candidate base is incomplete",
        )
    _contract(
        SHA40_RE.fullmatch(candidate["base"]["sha"]) is not None,
        "Candidate base SHA is invalid",
    )
    _contract(
        isinstance(candidate["groupKey"], str)
        and SHA256_RE.fullmatch(candidate["groupKey"]),
        "Candidate group key is invalid",
    )
    paths = _sorted_unique_strings(
        candidate["manifestPaths"], "manifestPaths", nonempty=True
    )
    for path in paths:
        _safe_path(path)
    identity_hash = hashlib.sha256(
        _source_identity(candidate).encode("utf-8")
    ).hexdigest()[:12]
    _contract(identity_hash == plan["sourceHash"], "Plan source hash is invalid")
    versions = candidate["versions"]
    _contract(isinstance(versions, list) and versions, "Plan versions cannot be empty")
    for version in versions:
        _exact_object(
            version,
            {"name", "ecosystem", "from", "to", "impact", "prerelease"},
            "version",
        )
        _contract(
            isinstance(version["name"], str) and bool(version["name"]),
            "Plan version name is invalid",
        )
        _contract(
            isinstance(version["ecosystem"], str)
            and version["ecosystem"] in ECOSYSTEMS,
            "Plan version ecosystem is invalid",
        )
        _contract(
            version["from"] is None or isinstance(version["from"], str),
            "Plan version source is invalid",
        )
        _contract(
            isinstance(version["to"], str) and bool(version["to"]),
            "Plan version target is invalid",
        )
        _contract(
            isinstance(version["impact"], str) and version["impact"] in IMPACTS,
            "Plan version impact is invalid",
        )
        _contract(
            version["prerelease"] is None or isinstance(version["prerelease"], bool),
            "Plan prerelease flag is invalid",
        )
    _contract(
        versions == sorted(versions, key=_version_key), "Plan versions must be sorted"
    )
    _contract(
        candidate["effectiveImpact"] == _effective_impact(versions),
        "Plan effective impact is invalid",
    )
    _contract(
        isinstance(candidate["observedAggregateImpact"], str)
        and candidate["observedAggregateImpact"] in IMPACTS,
        "Plan observed impact is invalid",
    )
    _contract(
        isinstance(candidate["impactRationale"], str)
        and bool(candidate["impactRationale"].strip()),
        "Plan impact rationale is required",
    )
    additions = candidate["additionalDependencies"]
    _contract(
        isinstance(additions, list), "Plan additionalDependencies must be an array"
    )
    for addition in additions:
        _exact_object(
            addition,
            {"name", "ecosystem", "reason", "evidenceUrl"},
            "additional dependency",
        )
        _contract(
            isinstance(addition["ecosystem"], str)
            and addition["ecosystem"] in ECOSYSTEMS,
            "Additional dependency ecosystem is invalid",
        )
        for key in ("name", "reason", "evidenceUrl"):
            _contract(
                isinstance(addition[key], str) and bool(addition[key].strip()),
                f"Additional dependency {key} is invalid",
            )
    _contract(
        additions
        == sorted(additions, key=lambda item: (item["name"], item["ecosystem"])),
        "Additional dependencies must be sorted",
    )
    _contract(
        len({canonical_json(item) for item in additions}) == len(additions),
        "Additional dependencies must be unique",
    )
    if candidate["decision"] == "update":
        _contract(
            candidate["mode"] in {"direct", "replacement"}, "Update mode is invalid"
        )
        _contract(
            isinstance(candidate["commitSha"], str)
            and SHA40_RE.fullmatch(candidate["commitSha"]),
            "Update commit is invalid",
        )
        _contract(
            isinstance(candidate["treeSha"], str)
            and SHA40_RE.fullmatch(candidate["treeSha"]),
            "Update tree is invalid",
        )
        _contract(
            not any(item["prerelease"] is True for item in versions),
            "Known prerelease versions may not be updated",
        )
        if candidate["mode"] == "direct":
            _contract(
                len(sources) == 1,
                "Direct plans require exactly one source",
            )
            _contract(
                candidate["commitSha"] == sources[0]["headSha"]
                and candidate["targetPrNumber"] == sources[0]["number"],
                "Direct target is invalid",
            )
            _contract(
                plan["destinationBranch"] is None,
                "Direct plan cannot have a destination branch",
            )
        else:
            expected_branch = (
                f"automation/dependabot/{_manifest_slug(paths[0])}-{plan['sourceHash']}"
            )
            _contract(
                plan["destinationBranch"] == expected_branch,
                "Replacement branch is not deterministic",
            )
            _contract(
                candidate["targetPrNumber"] is None,
                "Replacement target PR must be null",
            )
        evidence = _validate_release_evidence(
            candidate["stabilityEvidence"], structured_summary=len(sources) > 1
        )
        _contract(bool(evidence), "Update requires release evidence")
        if len(sources) > 1:
            _contract(
                {_release_subject(version) for version in versions}.issubset(
                    {item["subject"] for item in evidence}
                ),
                "Plan release evidence is incomplete",
            )
        _contract(
            candidate["closureEvidence"] == [], "Update cannot carry closure evidence"
        )
        _contract(
            isinstance(candidate["validation"], list) and candidate["validation"],
            "Update requires validations",
        )
        for check in candidate["validation"]:
            _exact_object(
                check, {"command", "exitCode", "treeSha", "finishedAt"}, "validation"
            )
            _contract(
                check["exitCode"] == 0 and check["treeSha"] == candidate["treeSha"],
                "Validation is unsuccessful or targets another tree",
            )
            _utc_now(check["finishedAt"])
        _contract(
            len({canonical_json(item) for item in candidate["validation"]})
            == len(candidate["validation"]),
            "Validation results must be unique",
        )
    else:
        _contract(
            candidate["decision"] in {"close-nonapplicable", "close-declined-major"},
            "Invalid closure decision",
        )
        _contract(
            candidate["mode"] is None
            and candidate["commitSha"] is None
            and candidate["treeSha"] is None,
            "Closure carries update objects",
        )
        _contract(
            plan["destinationBranch"] is None,
            "Closure cannot have a destination branch",
        )
        _contract(
            candidate["stabilityEvidence"] == [] and candidate["validation"] == [],
            "Closure carries update evidence",
        )
        closure = _validate_closure_evidence(candidate["closureEvidence"], sources)
        reason_predicates = {
            "prerelease": "version-prerelease",
            "duplicate-merged": "replacement-merged",
            "superseded-merged": "replacement-merged",
            "withdrawn": "human-reviewed",
            "already-in-base": "human-reviewed",
            "unsupported-platform": "human-reviewed",
            "major-declined": "user-decision",
        }
        _contract(
            candidate["closureReason"] in reason_predicates, "Closure reason is invalid"
        )
        _contract(
            all(
                item["predicate"] == reason_predicates[candidate["closureReason"]]
                for item in closure
            ),
            "Closure evidence predicate differs from reason",
        )
        if candidate["decision"] == "close-declined-major":
            _contract(
                candidate["closureReason"] == "major-declined",
                "Declined-major decision requires its matching reason",
            )
            _contract(
                isinstance(candidate["parentPlanDigest"], str)
                and SHA256_RE.fullmatch(candidate["parentPlanDigest"]) is not None,
                "Declined-major closure requires a parent plan digest",
            )
        else:
            _contract(
                candidate["closureReason"] != "major-declined",
                "Nonapplicable closure cannot bypass major rejection approval",
            )
            _contract(
                candidate["parentPlanDigest"] is None,
                "Nonapplicable closure cannot carry a parent plan digest",
            )
    _contract(
        plan["operations"]
        == _expected_operations(candidate, plan["destinationBranch"]),
        "Plan operations do not match its decision",
    )
    approval_kind = plan["approval"]["kind"]
    if candidate["decision"] == "update" and candidate["effectiveImpact"] == "major":
        _contract(
            approval_kind == "update-major", "Major update lacks its approval gate"
        )
    elif candidate["decision"] == "close-declined-major":
        _contract(
            approval_kind == "reject-major", "Declined major lacks rejection approval"
        )
    elif candidate["decision"] != "update" and any(
        item.get("predicate") == "human-reviewed"
        for item in candidate["closureEvidence"]
    ):
        _contract(
            approval_kind == "close-reviewed", "Reviewed closure lacks close approval"
        )
    else:
        _contract(
            approval_kind == "none", "Autonomous plan unexpectedly requires approval"
        )


def _atomic_json(path: str | Path, value: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _new_state(plan: Mapping[str, Any], now: str | None) -> dict[str, Any]:
    candidate = plan["candidate"]
    return {
        "schemaVersion": 1,
        "planDigest": plan["planDigest"],
        "repository": {
            "host": candidate["repository"]["host"],
            "nameWithOwner": candidate["repository"]["nameWithOwner"],
        },
        "base": {"ref": candidate["base"]["ref"], "sha": candidate["base"]["sha"]},
        "status": "planned",
        "replacement": None,
        "mergeCommitSha": None,
        "operations": [
            {
                "name": item["name"],
                "target": item["target"],
                "status": "pending",
                "attempts": 0,
                "lastObserved": None,
            }
            for item in plan["operations"]
        ],
        "sources": [
            {"number": item["number"], "headSha": item["headSha"], "status": "open"}
            for item in candidate["sources"]
        ],
        "blocked": None,
        "updatedAt": _utc_now(now),
    }


def _validate_state_shape(state: Any) -> dict[str, Any]:
    fields = {
        "schemaVersion",
        "planDigest",
        "repository",
        "base",
        "status",
        "replacement",
        "mergeCommitSha",
        "operations",
        "sources",
        "blocked",
        "updatedAt",
    }
    value = _exact_object(state, fields, "state")
    _contract(value["schemaVersion"] == 1, "Unsupported state schema version")
    _contract(
        isinstance(value["planDigest"], str)
        and SHA256_RE.fullmatch(value["planDigest"]),
        "State plan digest is invalid",
    )
    repository = _exact_object(
        value["repository"], {"host", "nameWithOwner"}, "state.repository"
    )
    _contract(
        all(isinstance(repository[key], str) and repository[key] for key in repository),
        "State repository is invalid",
    )
    base = _exact_object(value["base"], {"ref", "sha"}, "state.base")
    _contract(
        isinstance(base["ref"], str) and bool(base["ref"]), "State base ref is invalid"
    )
    _contract(
        isinstance(base["sha"], str) and SHA40_RE.fullmatch(base["sha"]),
        "State base SHA is invalid",
    )
    statuses = {
        "planned",
        "published",
        "waiting-checks",
        "queued",
        "merged",
        "sources-closed",
        "closed",
        "blocked",
    }
    _contract(
        isinstance(value["status"], str) and value["status"] in statuses,
        "State status is invalid",
    )

    replacement = value["replacement"]
    if replacement is not None:
        replacement = _exact_object(
            replacement, {"number", "url", "headSha"}, "state.replacement"
        )
        _contract(
            type(replacement["number"]) is int and replacement["number"] > 0,
            "State replacement number is invalid",
        )
        _contract(
            isinstance(replacement["url"], str) and bool(replacement["url"]),
            "State replacement URL is invalid",
        )
        _contract(
            isinstance(replacement["headSha"], str)
            and SHA40_RE.fullmatch(replacement["headSha"]),
            "State replacement head is invalid",
        )
    merge_sha = value["mergeCommitSha"]
    _contract(
        merge_sha is None
        or (isinstance(merge_sha, str) and SHA40_RE.fullmatch(merge_sha)),
        "State merge SHA is invalid",
    )

    operations = value["operations"]
    _contract(
        isinstance(operations, list) and bool(operations),
        "State operations are invalid",
    )
    for operation in operations:
        operation = _exact_object(
            operation,
            {"name", "target", "status", "attempts", "lastObserved"},
            "state operation",
        )
        name = operation["name"]
        target = operation["target"]
        _contract(
            isinstance(name, str)
            and name in {"push", "create-replacement", "merge", "close-source"},
            "State operation name is invalid",
        )
        _contract(
            isinstance(target, str) and bool(target),
            "State operation target is invalid",
        )
        if name == "push":
            _contract(
                re.fullmatch(
                    r"branch:automation/dependabot/[a-z0-9][a-z0-9-]{0,31}-[0-9a-f]{12}",
                    target,
                )
                is not None,
                "State push target is invalid",
            )
        elif name == "create-replacement":
            _contract(
                target == "replacement", "State replacement-create target is invalid"
            )
        elif name == "merge":
            _contract(
                target == "replacement"
                or re.fullmatch(r"source:[1-9][0-9]*@[0-9a-f]{40}", target) is not None,
                "State merge target is invalid",
            )
        else:
            _contract(
                re.fullmatch(r"source:[1-9][0-9]*@[0-9a-f]{40}", target) is not None,
                "State close target is invalid",
            )
        _contract(
            isinstance(operation["status"], str)
            and operation["status"] in {"pending", "confirmed", "blocked"},
            "State operation status is invalid",
        )
        _contract(
            type(operation["attempts"]) is int and operation["attempts"] >= 0,
            "State operation attempts are invalid",
        )
        _contract(
            operation["lastObserved"] is None
            or isinstance(operation["lastObserved"], str),
            "State operation observation is invalid",
        )
    _contract(
        len({canonical_json(item) for item in operations}) == len(operations),
        "State operations must be unique",
    )

    sources = value["sources"]
    _contract(
        isinstance(sources, list) and bool(sources),
        "State must contain at least one source",
    )
    for source in sources:
        source = _exact_object(source, {"number", "headSha", "status"}, "state source")
        _contract(
            type(source["number"]) is int and source["number"] > 0,
            "State source number is invalid",
        )
        _contract(
            isinstance(source["headSha"], str)
            and SHA40_RE.fullmatch(source["headSha"]),
            "State source head is invalid",
        )
        _contract(
            isinstance(source["status"], str)
            and source["status"] in {"open", "merged", "closed"},
            "State source status is invalid",
        )
    _contract(
        sources == sorted(sources, key=lambda item: item["number"])
        and len({item["number"] for item in sources}) == len(sources),
        "State sources must be sorted and unique",
    )

    blocked = value["blocked"]
    if value["status"] == "blocked":
        blocked = _exact_object(blocked, {"reason", "action"}, "state.blocked")
        _contract(
            isinstance(blocked["reason"], str)
            and blocked["reason"]
            in {
                "transient",
                "protection",
                "unsafe-scope",
                "stale-snapshot",
                "ambiguous-remote",
                "timeout",
            },
            "State blocked reason is invalid",
        )
        _contract(
            isinstance(blocked["action"], str) and bool(blocked["action"]),
            "State blocked action is invalid",
        )
    else:
        _contract(blocked is None, "Non-blocked state cannot carry blocked details")
    _utc_now(value["updatedAt"])

    if value["status"] in {"planned", "published", "waiting-checks", "queued"}:
        _contract(merge_sha is None, "Pre-merge state cannot carry a merge SHA")
    if value["status"] == "merged":
        _contract(merge_sha is not None, "Merged state requires a merge SHA")
    if value["status"] == "sources-closed":
        _contract(
            replacement is not None
            and merge_sha is not None
            and all(source["status"] == "closed" for source in sources),
            "sources-closed state is inconsistent",
        )
    if value["status"] == "closed":
        _contract(
            replacement is None
            and merge_sha is None
            and all(source["status"] == "closed" for source in sources),
            "Closed state is inconsistent",
        )
    return value


def _load_state(
    path: str | Path, plan: Mapping[str, Any], now: str | None
) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return _validate_state_shape(_new_state(plan, now))
    try:
        state = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutorError(
            EXIT_CONTRACT, "CONTRACT", "State file is unreadable or malformed"
        ) from exc
    state = _validate_state_shape(state)
    _contract(
        state["planDigest"] == plan["planDigest"], "State belongs to a different plan"
    )
    candidate = plan["candidate"]
    _contract(
        state["repository"]
        == {
            "host": candidate["repository"]["host"],
            "nameWithOwner": candidate["repository"]["nameWithOwner"],
        },
        "State repository differs from plan",
    )
    _contract(
        state["base"]
        == {"ref": candidate["base"]["ref"], "sha": candidate["base"]["sha"]},
        "State base differs from plan",
    )
    _contract(
        [(item.get("name"), item.get("target")) for item in state["operations"]]
        == [(item["name"], item["target"]) for item in plan["operations"]],
        "State operations differ from plan",
    )
    _contract(
        [(item.get("number"), item.get("headSha")) for item in state["sources"]]
        == [(item["number"], item["headSha"]) for item in candidate["sources"]],
        "State sources differ from plan",
    )
    return state


def _save_state(
    path: str | Path, state: dict[str, Any], now: str | None, *, dry_run: bool
) -> None:
    state["updatedAt"] = _utc_now(now)
    _validate_state_shape(state)
    if not dry_run:
        _atomic_json(path, state)


def _operation(
    state: dict[str, Any], name: str, target: str | None = None
) -> dict[str, Any]:
    matches = [
        item
        for item in state["operations"]
        if item["name"] == name and (target is None or item["target"] == target)
    ]
    _contract(
        len(matches) == 1, "Runtime operation is ambiguous", name=name, target=target
    )
    return matches[0]


def _confirm_operation(
    state: dict[str, Any], name: str, target: str | None, observed: str
) -> None:
    item = _operation(state, name, target)
    item["status"] = "confirmed"
    item["lastObserved"] = observed


def _attempt_operation(state: dict[str, Any], name: str, target: str | None) -> None:
    item = _operation(state, name, target)
    item["attempts"] += 1


def _approval_guard(
    plan: Mapping[str, Any], token: str | None, parent_plan: dict[str, Any] | None
) -> None:
    approval = plan["approval"]
    kind = approval["kind"]
    if kind == "none":
        _contract(token is None, "Autonomous plan must not receive an approval token")
        return
    if kind == "update-major":
        if token != approval["approveToken"]:
            raise ExecutorError(
                EXIT_APPROVAL,
                "APPROVAL_REQUIRED",
                "Exact major approval token is required",
            )
        return
    if kind == "close-reviewed":
        if token != approval["closeToken"]:
            raise ExecutorError(
                EXIT_APPROVAL,
                "APPROVAL_REQUIRED",
                "Exact reviewed-close token is required",
            )
        return
    if kind != "reject-major" or token != approval["rejectToken"]:
        raise ExecutorError(
            EXIT_APPROVAL,
            "APPROVAL_REQUIRED",
            "Exact major rejection token is required",
        )
    if parent_plan is None:
        raise ExecutorError(
            EXIT_APPROVAL,
            "APPROVAL_REQUIRED",
            "Declined-major closure requires its parent plan",
        )
    _verify_plan_structure(parent_plan)
    candidate = plan["candidate"]
    parent_candidate = parent_plan["candidate"]
    if (
        parent_plan["planDigest"] != candidate["parentPlanDigest"]
        or parent_plan["approval"]["kind"] != "update-major"
        or parent_candidate["repository"] != candidate["repository"]
        or parent_candidate["base"] != candidate["base"]
        or parent_candidate["sources"] != candidate["sources"]
    ):
        raise ExecutorError(
            EXIT_STALE,
            "STALE_SNAPSHOT",
            "Declined-major parent plan does not match the close plan",
        )


def _verify_candidate_git(
    candidate_root: str | Path, candidate: Mapping[str, Any], runner: Runner
) -> Path:
    actual, host, repo = _git_identity(candidate_root, runner)
    expected = candidate["repository"]
    if host != expected["host"] or repo.lower() != expected["nameWithOwner"].lower():
        raise ExecutorError(
            EXIT_STALE,
            "STALE_SNAPSHOT",
            "Candidate repository origin differs from the plan",
        )
    if candidate["decision"] != "update":
        return actual
    commit = candidate["commitSha"]
    tree = candidate["treeSha"]
    _checked(
        runner,
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=actual,
        exit_code=EXIT_STALE,
        code="STALE_SNAPSHOT",
    )
    observed_tree = _checked(
        runner,
        ["git", "rev-parse", f"{commit}^{{tree}}"],
        cwd=actual,
        exit_code=EXIT_STALE,
        code="STALE_SNAPSHOT",
    ).stdout.strip()
    if observed_tree != tree:
        raise ExecutorError(
            EXIT_STALE, "STALE_SNAPSHOT", "Candidate tree no longer matches its commit"
        )
    ancestor = _run(
        runner,
        ["git", "merge-base", "--is-ancestor", candidate["base"]["sha"], commit],
        cwd=actual,
    )
    if ancestor.returncode != 0:
        raise ExecutorError(
            EXIT_STALE,
            "STALE_SNAPSHOT",
            "Candidate commit does not descend from the planned base",
        )
    return actual


def _current_ref_sha(
    runner: Runner, repository: Mapping[str, Any], ref: str
) -> str | None:
    value = _gh_api(
        runner,
        repository["host"],
        f"repos/{repository['nameWithOwner']}/git/ref/heads/{urllib.parse.quote(ref, safe='')}",
        allow_404=True,
    )
    if value is None:
        return None
    try:
        sha = value["object"]["sha"]
    except (KeyError, TypeError) as exc:
        raise ExecutorError(
            EXIT_STALE, "STALE_SNAPSHOT", "GitHub ref response is malformed"
        ) from exc
    if not isinstance(sha, str) or not SHA40_RE.fullmatch(sha):
        raise ExecutorError(EXIT_STALE, "STALE_SNAPSHOT", "GitHub ref SHA is invalid")
    return sha


def _get_pr(
    runner: Runner, repository: Mapping[str, Any], number: int
) -> dict[str, Any]:
    value = _gh_api(
        runner,
        repository["host"],
        f"repos/{repository['nameWithOwner']}/pulls/{number}",
    )
    if not isinstance(value, dict):
        raise ExecutorError(
            EXIT_STALE, "STALE_SNAPSHOT", "Pull request response is malformed"
        )
    return value


def _pr_head_sha(pr: Mapping[str, Any]) -> str | None:
    head = pr.get("head")
    return (
        head.get("sha")
        if isinstance(head, dict) and isinstance(head.get("sha"), str)
        else None
    )


def _pr_base(pr: Mapping[str, Any]) -> tuple[str | None, str | None, str | None]:
    base = pr.get("base")
    if not isinstance(base, dict):
        return None, None, None
    repo = base.get("repo")
    name = repo.get("full_name") if isinstance(repo, dict) else None
    return name, base.get("ref"), base.get("sha")


def _verify_source_pr(
    pr: Mapping[str, Any],
    candidate: Mapping[str, Any],
    source: Mapping[str, Any],
    *,
    require_open: bool = False,
    allow_merged: bool = False,
) -> None:
    if _pr_head_sha(pr) != source["headSha"]:
        raise ExecutorError(
            EXIT_STALE, "STALE_SNAPSHOT", f"Source PR #{source['number']} head changed"
        )
    repo, ref, _ = _pr_base(pr)
    base = candidate["base"]
    if not (
        isinstance(repo, str)
        and repo.lower() == base["repo"].lower()
        and ref == base["ref"]
    ):
        raise ExecutorError(
            EXIT_STALE, "STALE_SNAPSHOT", f"Source PR #{source['number']} base changed"
        )
    user = pr.get("user")
    if (
        not isinstance(user, dict)
        or user.get("login") not in {"dependabot[bot]", "app/dependabot"}
        or user.get("type") != "Bot"
    ):
        raise ExecutorError(
            EXIT_STALE,
            "STALE_SNAPSHOT",
            f"Source PR #{source['number']} is not owned by Dependabot",
        )
    if pr.get("merged_at") and not allow_merged:
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            f"Source PR #{source['number']} was merged concurrently",
        )
    if require_open and str(pr.get("state") or "").lower() != "open":
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            f"Source PR #{source['number']} is no longer open",
        )


def _validate_live_sources(
    live_sources: Sequence[tuple[Mapping[str, Any], Sequence[str]]],
    candidate: Mapping[str, Any],
) -> None:
    """Bind all planned source versions to current PR bodies per ecosystem."""

    dependencies: list[dict[str, Any]] = []
    for pr, manifest_paths in live_sources:
        ecosystem = _ecosystem_for_files(manifest_paths)
        head = pr.get("head")
        head_ref = str(head.get("ref") or "") if isinstance(head, dict) else ""
        parsed = _parse_dependencies(
            str(pr.get("title") or ""),
            str(pr.get("body") or ""),
            ecosystem,
            head_ref,
        )
        if any(
            item["fromVersion"] is None or item["toVersion"] is None for item in parsed
        ):
            raise ExecutorError(
                EXIT_STALE,
                "STALE_SNAPSHOT",
                "Live Dependabot versions cannot be parsed",
            )
        dependencies.extend(parsed)

    remaining = list(candidate["versions"])
    for dependency in dependencies:
        key = (
            dependency["name"],
            dependency["ecosystem"],
            dependency["fromVersion"],
            dependency["toVersion"],
        )
        matches = [
            index
            for index, version in enumerate(remaining)
            if _source_version_key(version) == key
        ]
        if not matches:
            raise ExecutorError(
                EXIT_STALE,
                "STALE_SNAPSHOT",
                "Live source versions differ from the plan",
            )
        version = remaining.pop(matches[0])
        if (version["impact"], version["prerelease"]) != (
            dependency["impact"],
            dependency["prerelease"],
        ):
            raise ExecutorError(
                EXIT_STALE, "STALE_SNAPSHOT", "Live source impact differs from the plan"
            )

    declared_additions = Counter(
        (item["name"], item["ecosystem"])
        for item in candidate["additionalDependencies"]
    )
    observed_additions = Counter(
        (item["name"], item["ecosystem"]) for item in remaining
    )
    if observed_additions != declared_additions:
        raise ExecutorError(
            EXIT_STALE,
            "STALE_SNAPSHOT",
            "Additional dependency versions differ from the plan",
        )
    for version in remaining:
        if (version["impact"], version["prerelease"]) != classify_version(
            version["ecosystem"],
            version["from"],
            version["to"],
        ):
            raise ExecutorError(
                EXIT_STALE, "STALE_SNAPSHOT", "Additional dependency impact is invalid"
            )
    if (
        aggregate_impact([item["impact"] for item in dependencies])
        != candidate["observedAggregateImpact"]
    ):
        raise ExecutorError(
            EXIT_STALE, "STALE_SNAPSHOT", "Live aggregate impact differs from the plan"
        )


def _validate_live_source_metadata(
    pr: Mapping[str, Any], candidate: Mapping[str, Any]
) -> None:
    """Backward-compatible singleton live metadata validation."""

    _contract(
        len(candidate["sources"]) == 1,
        "Multi-source candidates require per-source manifests",
    )
    _validate_live_sources([(pr, candidate["manifestPaths"])], candidate)


def _live_source_manifests(
    runner: Runner, repository: Mapping[str, Any], number: int
) -> list[str]:
    files_raw = _page_api(
        runner,
        repository["host"],
        f"repos/{repository['nameWithOwner']}/pulls/{number}/files",
    )
    files = sorted(
        {
            _safe_path(str(item["filename"]))
            for item in files_raw
            if isinstance(item, dict) and "filename" in item
        }
    )
    manifests, _ = _dependency_paths(files)
    if not manifests:
        raise ExecutorError(
            EXIT_STALE,
            "STALE_SNAPSHOT",
            f"Source PR #{number} no longer contains a dependency manifest",
        )
    return manifests


_CLOSE_MARKER_RE = re.compile(
    r"<!-- resolve-dependabot-prs:v1 action=close source=([^ ]+) reason=([^ ]+) evidence=([^ >]+)(?: replacement=([^ >]+))? -->"
)


def _comments(
    runner: Runner, repository: Mapping[str, Any], number: int
) -> list[dict[str, Any]]:
    values = _page_api(
        runner,
        repository["host"],
        f"repos/{repository['nameWithOwner']}/issues/{number}/comments",
    )
    return [item for item in values if isinstance(item, dict)]


def _marker_status(
    comments: Sequence[Mapping[str, Any]], source_ref: str, expected: str
) -> tuple[bool, bool]:
    seen_expected = False
    conflicting = False
    for comment in comments:
        body = str(comment.get("body") or "")
        for match in _CLOSE_MARKER_RE.finditer(body):
            if match.group(1) != source_ref:
                continue
            if match.group(0) == expected:
                seen_expected = True
            else:
                conflicting = True
    return seen_expected, conflicting


def _closure_marker(candidate: Mapping[str, Any], source: Mapping[str, Any]) -> str:
    evidence = next(
        item
        for item in candidate["closureEvidence"]
        if item["sourceNumber"] == source["number"]
    )
    digest = canonical_digest(evidence)
    return (
        "<!-- resolve-dependabot-prs:v1 action=close "
        f"source={source['number']}@{source['headSha']} reason={candidate['closureReason']} evidence={digest} -->"
    )


def _replacement_close_marker(
    plan: Mapping[str, Any],
    source: Mapping[str, Any],
    replacement_number: int,
    merge_sha: str,
) -> str:
    return (
        "<!-- resolve-dependabot-prs:v1 action=close "
        f"source={source['number']}@{source['headSha']} reason=superseded-merged "
        f"evidence={plan['planDigest']} replacement={replacement_number}@{merge_sha} -->"
    )


def _replacement_marker(plan: Mapping[str, Any]) -> str:
    candidate = plan["candidate"]
    header = (
        "<!-- resolve-dependabot-prs:v1 "
        f"key={plan['sourceHash']} plan={plan['planDigest']} "
        f"tree={candidate['treeSha']} -->"
    )
    source_markers = [
        (
            "<!-- resolve-dependabot-prs:v1 source="
            f"{source['number']}@{source['headSha']} "
            f"plan={plan['planDigest']} tree={candidate['treeSha']} -->"
        )
        for source in candidate["sources"]
    ]
    return "\n".join([header, *source_markers])


def _legacy_replacement_marker(plan: Mapping[str, Any]) -> str | None:
    sources = plan["candidate"]["sources"]
    if len(sources) != 1:
        return None
    source = sources[0]
    return (
        f"<!-- resolve-dependabot-prs:v1 key={plan['sourceHash']} "
        f"source={source['number']}@{source['headSha']} -->"
    )


def _replacement_body(plan: Mapping[str, Any]) -> str:
    candidate = plan["candidate"]
    versions = "\n".join(
        f"- `{version['name']}`: `{version['from']}` → `{version['to']}`"
        for version in candidate["versions"]
    )
    validations = "\n".join(
        f"- `{check['command']}`" for check in candidate["validation"]
    )
    release_review = "\n".join(
        f"- `{item['subject']}`: {item['summary']} ({item['url']})"
        for item in candidate["stabilityEvidence"]
    )
    return (
        f"{_replacement_marker(plan)}\n\n"
        "Consolidated Dependabot dependency update.\n\n"
        f"## Versions\n\n{versions}\n\n"
        f"## Release review\n\n{release_review}\n\n"
        f"## Validation\n\n{validations}"
    )


class _Mutations:
    def __init__(self, runner: Runner, dry_run: bool) -> None:
        self.runner = runner
        self.dry_run = dry_run
        self.commands: list[list[str]] = []

    def run(
        self, args: Sequence[str], *, cwd: str | Path | None = None
    ) -> CommandResult:
        command = list(args)
        self.commands.append(command)
        if self.dry_run:
            return CommandResult(0, "", "")
        return _checked(
            self.runner,
            command,
            cwd=cwd,
            mutating=True,
            exit_code=EXIT_BLOCKED,
            code="TRANSIENT",
        )


def _revalidate_base(runner: Runner, candidate: Mapping[str, Any]) -> None:
    current = _current_ref_sha(
        runner, candidate["repository"], candidate["base"]["ref"]
    )
    if current != candidate["base"]["sha"]:
        raise ExecutorError(
            EXIT_STALE, "STALE_SNAPSHOT", "Base branch moved since planning"
        )


def _validate_closure_predicate(
    runner: Runner,
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> None:
    predicate = evidence["predicate"]
    if predicate == "version-prerelease":
        versions = [
            item for item in candidate["versions"] if item["prerelease"] is True
        ]
        if not versions or not all(
            classify_version(item["ecosystem"], item["from"], item["to"])[1] is True
            for item in versions
        ):
            raise ExecutorError(
                EXIT_STALE,
                "STALE_SNAPSHOT",
                "Prerelease closure predicate no longer holds",
            )
    elif predicate == "replacement-merged":
        replacement = _get_pr(
            runner, candidate["repository"], evidence["replacementPrNumber"]
        )
        merge_sha = replacement.get("merge_commit_sha")
        if (
            not replacement.get("merged_at")
            or merge_sha != evidence["replacementMergeSha"]
        ):
            raise ExecutorError(
                EXIT_STALE,
                "STALE_SNAPSHOT",
                "Replacement evidence no longer identifies the merged PR",
            )
        observed_url = replacement.get("html_url") or replacement.get("url")
        if observed_url != evidence["url"]:
            raise ExecutorError(
                EXIT_STALE,
                "STALE_SNAPSHOT",
                "Replacement evidence URL no longer matches the PR",
            )
        base_repo, base_ref, _ = _pr_base(replacement)
        expected_repo = candidate["repository"]
        actor = replacement.get("user")
        if (
            not isinstance(base_repo, str)
            or base_repo.lower() != expected_repo["nameWithOwner"].lower()
            or base_ref != candidate["base"]["ref"]
            or not isinstance(actor, dict)
            or actor.get("login") != expected_repo["actorLogin"]
        ):
            raise ExecutorError(
                EXIT_STALE,
                "STALE_SNAPSHOT",
                "Merged replacement identity no longer matches the plan",
            )
        source = next(
            item
            for item in candidate["sources"]
            if item["number"] == evidence["sourceNumber"]
        )
        required = re.compile(
            r"<!-- resolve-dependabot-prs:v1 source="
            + re.escape(f"{source['number']}@{source['headSha']}")
            + r" plan=[0-9a-f]{64} tree=[0-9a-f]{40} -->"
        )
        legacy_required = re.compile(
            r"<!-- resolve-dependabot-prs:v1 key=[0-9a-f]{12} source="
            + re.escape(f"{source['number']}@{source['headSha']}")
            + r" -->"
        )
        body = str(replacement.get("body") or "")
        legacy_matches = len(candidate["sources"]) == 1 and legacy_required.search(body)
        if required.search(body) is None and not legacy_matches:
            raise ExecutorError(
                EXIT_STALE,
                "STALE_SNAPSHOT",
                "Merged replacement lacks the exact source marker",
            )


def _close_one_source(
    runner: Runner,
    mutations: _Mutations,
    plan: Mapping[str, Any],
    state: dict[str, Any],
    source: Mapping[str, Any],
    marker: str,
    *,
    allow_preclosed: bool,
    state_path: str | Path,
    now: str | None,
) -> None:
    candidate = plan["candidate"]
    repository = candidate["repository"]
    number = source["number"]
    target = f"source:{number}@{source['headSha']}"
    operation = _operation(state, "close-source", target)
    pr = _get_pr(runner, repository, number)
    _verify_source_pr(pr, candidate, source)
    source_ref = f"{number}@{source['headSha']}"
    exact, conflict = _marker_status(
        _comments(runner, repository, number), source_ref, marker
    )
    if conflict:
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            f"Source PR #{number} has a conflicting executor marker",
        )
    merged = bool(pr.get("merged_at"))
    state_name = str(pr.get("state") or "").lower()
    source_state = next(item for item in state["sources"] if item["number"] == number)
    if (
        operation["status"] == "confirmed"
        and source_state["status"] == "closed"
        and state_name != "closed"
    ):
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            f"Source PR #{number} changed after its confirmed closure",
        )
    if merged:
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            f"Source PR #{number} was merged concurrently",
        )
    if state_name == "closed" and not exact:
        context = "after replacement merge" if allow_preclosed else "before closure"
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            f"Source PR #{number} closed {context} without the expected marker",
        )
    if not exact:
        _attempt_operation(state, "close-source", target)
        mutations.run(
            [
                "gh",
                "pr",
                "comment",
                str(number),
                "--repo",
                _gh_repo_arg(repository),
                "--body",
                marker,
            ]
        )
        if not mutations.dry_run:
            exact, conflict = _marker_status(
                _comments(runner, repository, number), source_ref, marker
            )
            if not exact or conflict:
                raise ExecutorError(
                    EXIT_BLOCKED,
                    "TRANSIENT",
                    f"Could not confirm marker on source PR #{number}",
                )
            _save_state(state_path, state, now, dry_run=False)
    if state_name != "closed":
        mutations.run(
            ["gh", "pr", "close", str(number), "--repo", _gh_repo_arg(repository)]
        )
        if mutations.dry_run:
            return
        pr = _get_pr(runner, repository, number)
        if str(pr.get("state") or "").lower() != "closed" or pr.get("merged_at"):
            raise ExecutorError(
                EXIT_BLOCKED,
                "TRANSIENT",
                f"Could not confirm closure of source PR #{number}",
            )
    operation["status"] = "confirmed"
    operation["lastObserved"] = "closed-with-exact-marker"
    source_state["status"] = "closed"
    _save_state(state_path, state, now, dry_run=mutations.dry_run)


def _find_replacements(
    runner: Runner,
    plan: Mapping[str, Any],
) -> list[dict[str, Any]]:
    candidate = plan["candidate"]
    repository = candidate["repository"]
    owner = repository["nameWithOwner"].split("/", 1)[0]
    branch = plan["destinationBranch"]
    values = _page_api(
        runner,
        repository["host"],
        f"repos/{repository['nameWithOwner']}/pulls?state=all&head={urllib.parse.quote(owner + ':' + branch, safe=':')}",
    )
    identity_marker = f"<!-- resolve-dependabot-prs:v1 key={plan['sourceHash']} "
    pull_requests = [item for item in values if isinstance(item, dict)]
    marked = [
        item for item in pull_requests if identity_marker in str(item.get("body") or "")
    ]
    if len(marked) != len(pull_requests):
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            "Replacement branch is also used by an unmarked PR",
        )
    expected_sources = {
        f"{source['number']}@{source['headSha']}" for source in candidate["sources"]
    }
    for replacement in marked:
        body = str(replacement.get("body") or "")
        observed_sources = set(REPLACEMENT_SOURCE_MARKER_RE.findall(body))
        observed_sources.update(
            source_ref
            for source_hash, source_ref in LEGACY_REPLACEMENT_MARKER_RE.findall(body)
            if source_hash == plan["sourceHash"]
        )
        if observed_sources != expected_sources:
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "Replacement PR source markers differ from the current plan",
            )
    return marked


def _validate_replacement_pr(
    plan: Mapping[str, Any],
    pr: Mapping[str, Any],
    *,
    require_current_marker: bool = False,
) -> None:
    candidate = plan["candidate"]
    repository = candidate["repository"]
    head = pr.get("head")
    base = pr.get("base")
    user = pr.get("user")
    if not isinstance(head, dict) or head.get("ref") != plan["destinationBranch"]:
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            "Replacement PR uses an unexpected head branch",
        )
    head_repo = head.get("repo")
    if (
        not isinstance(head_repo, dict)
        or str(head_repo.get("full_name", "")).lower()
        != repository["nameWithOwner"].lower()
    ):
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            "Replacement PR head belongs to another repository",
        )
    if not isinstance(base, dict) or base.get("ref") != candidate["base"]["ref"]:
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            "Replacement PR uses an unexpected base branch",
        )
    base_repo = base.get("repo")
    if (
        not isinstance(base_repo, dict)
        or str(base_repo.get("full_name", "")).lower()
        != repository["nameWithOwner"].lower()
    ):
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            "Replacement PR base belongs to another repository",
        )
    if not isinstance(user, dict) or user.get("login") != repository["actorLogin"]:
        raise ExecutorError(
            EXIT_BLOCKED, "AMBIGUOUS_REMOTE", "Replacement PR is owned by another actor"
        )
    if require_current_marker:
        body = str(pr.get("body") or "")
        legacy_marker = _legacy_replacement_marker(plan)
        legacy_merged_recovery = (
            bool(pr.get("merged_at"))
            and legacy_marker is not None
            and legacy_marker in body
        )
        if _replacement_marker(plan) not in body and not legacy_merged_recovery:
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "Replacement PR body is stale for the current plan",
            )


def _publish_replacement(
    runner: Runner,
    mutations: _Mutations,
    plan: dict[str, Any],
    state: dict[str, Any],
    candidate_root: Path,
    state_path: str | Path,
    now: str | None,
) -> None:
    candidate = plan["candidate"]
    repository = candidate["repository"]
    branch = plan["destinationBranch"]
    commit = candidate["commitSha"]
    body = _replacement_body(plan)
    existing = _find_replacements(runner, plan)
    if len(existing) > 1:
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            "Multiple replacement PRs share the exact marker",
        )
    pr = existing[0] if existing else None
    if pr is not None:
        _validate_replacement_pr(plan, pr)
        if str(pr.get("state") or "").lower() == "closed" and not pr.get("merged_at"):
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "Exact replacement PR was closed without merge",
            )

    branch_sha = _current_ref_sha(runner, repository, branch)
    branch_was_absent = branch_sha is None
    needs_push = branch_sha != commit
    if branch_sha is not None and branch_sha != commit:
        if pr is None or str(pr.get("state") or "").lower() != "open":
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "Existing replacement branch is not owned by an exact open PR",
            )
        exists = _run(
            runner,
            ["git", "cat-file", "-e", f"{branch_sha}^{{commit}}"],
            cwd=candidate_root,
        )
        if (
            exists.returncode
            or _run(
                runner,
                ["git", "merge-base", "--is-ancestor", branch_sha, commit],
                cwd=candidate_root,
            ).returncode
        ):
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "Replacement update is not a fast-forward",
            )
    push_target = f"branch:{branch}"
    if (
        branch_sha == commit
        and pr is None
        and _operation(state, "push", push_target)["status"] != "confirmed"
    ):
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            "Exact branch without a marked PR is not confirmed by this plan state",
        )
    if needs_push:
        _attempt_operation(state, "push", push_target)
        try:
            mutations.run(
                ["git", "push", "origin", f"{commit}:refs/heads/{branch}"],
                cwd=candidate_root,
            )
        except ExecutorError:
            # A lost acknowledgement is safe only when the exact ref is now visible.
            if (
                mutations.dry_run
                or _current_ref_sha(runner, repository, branch) != commit
            ):
                raise
        if not mutations.dry_run:
            branch_sha = _current_ref_sha(runner, repository, branch)
            if branch_sha != commit:
                raise ExecutorError(
                    EXIT_BLOCKED,
                    "TRANSIENT",
                    "Could not confirm exact replacement branch head",
                )
        _confirm_operation(state, "push", push_target, f"head={commit}")
        _save_state(state_path, state, now, dry_run=mutations.dry_run)
        if pr is not None and not mutations.dry_run:
            existing = _find_replacements(runner, plan)
            if len(existing) != 1:
                raise ExecutorError(
                    EXIT_BLOCKED,
                    "TRANSIENT",
                    "Could not refresh replacement PR after push",
                )
            pr = existing[0]
            _validate_replacement_pr(plan, pr)
    elif pr is not None or not branch_was_absent:
        _confirm_operation(state, "push", push_target, f"head={commit}")

    if pr is None:
        _attempt_operation(state, "create-replacement", "replacement")
        title = (
            "Consolidate Dependabot dependency updates"
            if len(candidate["sources"]) > 1
            else f"Resolve Dependabot PR #{candidate['sources'][0]['number']}"
        )
        command = [
            "gh",
            "pr",
            "create",
            "--repo",
            _gh_repo_arg(repository),
            "--base",
            candidate["base"]["ref"],
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        ]
        try:
            mutations.run(command)
        except ExecutorError:
            if mutations.dry_run:
                raise
            existing = _find_replacements(runner, plan)
            if len(existing) != 1:
                raise
        if mutations.dry_run:
            return
        existing = _find_replacements(runner, plan)
        if len(existing) != 1:
            raise ExecutorError(
                EXIT_BLOCKED,
                "TRANSIENT",
                "Could not confirm unique replacement PR creation",
            )
        pr = existing[0]
        _validate_replacement_pr(plan, pr)
    if str(pr.get("body") or "") != body:
        number = pr.get("number")
        if not isinstance(number, int):
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "Replacement PR number is unavailable for body update",
            )
        mutations.run(
            [
                "gh",
                "pr",
                "edit",
                str(number),
                "--repo",
                _gh_repo_arg(repository),
                "--body",
                body,
            ]
        )
        if mutations.dry_run:
            return
        existing = _find_replacements(runner, plan)
        if len(existing) != 1:
            raise ExecutorError(
                EXIT_BLOCKED,
                "TRANSIENT",
                "Could not confirm replacement PR body update",
            )
        pr = existing[0]
        _validate_replacement_pr(plan, pr, require_current_marker=True)
    number = pr.get("number")
    url = pr.get("html_url") or pr.get("url")
    head_sha = _pr_head_sha(pr)
    if (
        not isinstance(number, int)
        or not isinstance(url, str)
        or head_sha != commit
        or _replacement_marker(plan) not in str(pr.get("body") or "")
    ):
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            "Replacement PR identity is incomplete or stale",
        )
    state["replacement"] = {"number": number, "url": url, "headSha": head_sha}
    _confirm_operation(state, "create-replacement", "replacement", f"pr={number}")
    if pr.get("merged_at"):
        merge_sha = pr.get("merge_commit_sha")
        if not isinstance(merge_sha, str) or not SHA40_RE.fullmatch(merge_sha):
            raise ExecutorError(
                EXIT_BLOCKED, "AMBIGUOUS_REMOTE", "Merged replacement lacks a merge SHA"
            )
        state["mergeCommitSha"] = merge_sha
        state["status"] = "merged"
        _confirm_operation(state, "merge", "replacement", f"merge={merge_sha}")
    else:
        state["status"] = "published"
    _save_state(state_path, state, now, dry_run=mutations.dry_run)


def _protection_requirements(
    runner: Runner,
    repository: Mapping[str, Any],
    base_ref: str,
) -> tuple[set[str], int, bool]:
    host = repository["host"]
    repo = repository["nameWithOwner"]
    encoded = urllib.parse.quote(base_ref, safe="")
    try:
        rules = _gh_api(
            runner, host, f"repos/{repo}/rules/branches/{encoded}", allow_404=True
        )
        classic = _gh_api(
            runner, host, f"repos/{repo}/branches/{encoded}/protection", allow_404=True
        )
    except ExecutorError as exc:
        if exc.exit_code == EXIT_INCOMPLETE and "403" in exc.message:
            raise ExecutorError(
                EXIT_PROTECTION,
                "PROTECTION",
                "Branch protection rules are not readable",
            ) from exc
        if exc.exit_code == EXIT_INCOMPLETE:
            raise ExecutorError(
                EXIT_BLOCKED, "TRANSIENT", "Could not read branch protection rules"
            ) from exc
        raise
    required: set[str] = set()
    approvals = 0
    merge_queue = False
    if rules is not None:
        if not isinstance(rules, list):
            raise ExecutorError(
                EXIT_PROTECTION,
                "PROTECTION",
                "Repository rules response has an unknown shape",
            )
        for rule in rules:
            if not isinstance(rule, dict) or not isinstance(rule.get("type"), str):
                raise ExecutorError(
                    EXIT_PROTECTION,
                    "PROTECTION",
                    "Repository rule has an unknown shape",
                )
            kind = rule["type"]
            parameters = rule.get("parameters", {})
            if kind == "required_status_checks":
                if not isinstance(parameters, dict) or not isinstance(
                    parameters.get("required_status_checks"), list
                ):
                    raise ExecutorError(
                        EXIT_PROTECTION,
                        "PROTECTION",
                        "Required-check rule has an unknown shape",
                    )
                for check in parameters["required_status_checks"]:
                    if not isinstance(check, dict) or not isinstance(
                        check.get("context"), str
                    ):
                        raise ExecutorError(
                            EXIT_PROTECTION,
                            "PROTECTION",
                            "Required-check entry has an unknown shape",
                        )
                    required.add(check["context"])
            elif kind == "pull_request":
                if not isinstance(parameters, dict):
                    raise ExecutorError(
                        EXIT_PROTECTION,
                        "PROTECTION",
                        "Pull-request rule has an unknown shape",
                    )
                count = parameters.get("required_approving_review_count", 0)
                if not isinstance(count, int) or count < 0:
                    raise ExecutorError(
                        EXIT_PROTECTION, "PROTECTION", "Review requirement is invalid"
                    )
                approvals = max(approvals, count)
            elif kind == "merge_queue":
                merge_queue = True
    if classic is not None:
        if not isinstance(classic, dict):
            raise ExecutorError(
                EXIT_PROTECTION,
                "PROTECTION",
                "Classic protection response has an unknown shape",
            )
        checks = classic.get("required_status_checks")
        if checks is not None:
            if not isinstance(checks, dict):
                raise ExecutorError(
                    EXIT_PROTECTION,
                    "PROTECTION",
                    "Classic required checks have an unknown shape",
                )
            contexts = checks.get("contexts", [])
            entries = checks.get("checks", [])
            if not isinstance(contexts, list) or not isinstance(entries, list):
                raise ExecutorError(
                    EXIT_PROTECTION,
                    "PROTECTION",
                    "Classic required checks have an unknown shape",
                )
            for context in contexts:
                if not isinstance(context, str):
                    raise ExecutorError(
                        EXIT_PROTECTION,
                        "PROTECTION",
                        "Classic check context is invalid",
                    )
                required.add(context)
            for check in entries:
                if not isinstance(check, dict) or not isinstance(
                    check.get("context"), str
                ):
                    raise ExecutorError(
                        EXIT_PROTECTION, "PROTECTION", "Classic check entry is invalid"
                    )
                required.add(check["context"])
        reviews = classic.get("required_pull_request_reviews")
        if reviews is not None:
            if not isinstance(reviews, dict) or not isinstance(
                reviews.get("required_approving_review_count", 0), int
            ):
                raise ExecutorError(
                    EXIT_PROTECTION,
                    "PROTECTION",
                    "Classic review protection is invalid",
                )
            approvals = max(
                approvals, reviews.get("required_approving_review_count", 0)
            )
    return required, approvals, merge_queue


def _check_runs(
    runner: Runner, repository: Mapping[str, Any], head_sha: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page = 1
    while True:
        value = _gh_api(
            runner,
            repository["host"],
            f"repos/{repository['nameWithOwner']}/commits/{head_sha}/check-runs?per_page=100&page={page}",
        )
        if not isinstance(value, dict) or not isinstance(value.get("check_runs"), list):
            raise ExecutorError(
                EXIT_PROTECTION,
                "PROTECTION",
                "Check-runs response has an unknown shape",
            )
        runs = value["check_runs"]
        if not all(isinstance(item, dict) for item in runs):
            raise ExecutorError(
                EXIT_PROTECTION,
                "PROTECTION",
                "Check-runs response contains an invalid entry",
            )
        result.extend(runs)
        if len(runs) < 100:
            return result
        page += 1


def _reviews(
    runner: Runner, repository: Mapping[str, Any], number: int
) -> list[dict[str, Any]]:
    return [
        item
        for item in _page_api(
            runner,
            repository["host"],
            f"repos/{repository['nameWithOwner']}/pulls/{number}/reviews",
        )
        if isinstance(item, dict)
    ]


def _wait_for_checks(
    runner: Runner,
    repository: Mapping[str, Any],
    number: int,
    head_sha: str,
    required: set[str],
    required_approvals: int,
    author_login: str,
) -> None:
    max_polls = 60
    for attempt in range(max_polls + 1):
        runs = _check_runs(runner, repository, head_sha)
        pending = [item for item in runs if item.get("status") != "completed"]
        if pending:
            if attempt == max_polls:
                raise ExecutorError(
                    EXIT_BLOCKED, "TIMEOUT", "Checks did not complete within 30 minutes"
                )
            runner.sleep(30)
            continue
        by_name: dict[str, dict[str, Any]] = {}
        for run in runs:
            name = run.get("name")
            conclusion = run.get("conclusion")
            if not isinstance(name, str) or not isinstance(conclusion, str):
                raise ExecutorError(
                    EXIT_PROTECTION,
                    "PROTECTION",
                    "Completed check run lacks name or conclusion",
                )
            by_name[name] = run
            allowed = (
                {"success"} if name in required else {"success", "neutral", "skipped"}
            )
            if conclusion.lower() not in allowed:
                raise ExecutorError(
                    EXIT_PROTECTION,
                    "PROTECTION",
                    f"Check {name!r} concluded {conclusion!r}",
                )
        missing = sorted(required - set(by_name))
        if missing:
            raise ExecutorError(
                EXIT_PROTECTION,
                "PROTECTION",
                "Required checks are missing",
                {"missing": missing},
            )
        break

    latest: dict[str, tuple[str, str]] = {}
    for review in _reviews(runner, repository, number):
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        state = str(review.get("state") or "").upper()
        timestamp = str(review.get("submitted_at") or "")
        if not isinstance(login, str) or state == "DISMISSED":
            continue
        if login not in latest or timestamp >= latest[login][0]:
            latest[login] = (timestamp, state)
    if any(state == "CHANGES_REQUESTED" for _, state in latest.values()):
        raise ExecutorError(
            EXIT_PROTECTION, "PROTECTION", "A latest review requests changes"
        )
    approved = {
        login
        for login, (_, state) in latest.items()
        if state == "APPROVED" and login != author_login
    }
    if len(approved) < required_approvals:
        raise ExecutorError(
            EXIT_PROTECTION,
            "PROTECTION",
            "Required approving reviews are missing",
            {"required": required_approvals, "observed": len(approved)},
        )


def _merge_capabilities(
    runner: Runner, repository: Mapping[str, Any]
) -> dict[str, bool]:
    result = _checked(
        runner,
        [
            "gh",
            "repo",
            "view",
            _gh_repo_arg(repository),
            "--json",
            "mergeCommitAllowed,rebaseMergeAllowed,squashMergeAllowed",
        ],
        exit_code=EXIT_PROTECTION,
        code="PROTECTION",
    )
    value = _json_result(result, code="PROTECTION")
    if not isinstance(value, dict) or not all(
        isinstance(value.get(key), bool)
        for key in ("mergeCommitAllowed", "rebaseMergeAllowed", "squashMergeAllowed")
    ):
        raise ExecutorError(
            EXIT_PROTECTION, "PROTECTION", "Merge capability response is invalid"
        )
    return value


def _merge_pr(
    runner: Runner,
    mutations: _Mutations,
    plan: Mapping[str, Any],
    state: dict[str, Any],
    number: int,
    head_sha: str,
    author_login: str,
    state_path: str | Path,
    now: str | None,
    pre_merge_check: Callable[[], None] | None = None,
) -> tuple[str, bool]:
    candidate = plan["candidate"]
    repository = candidate["repository"]
    pr = _get_pr(runner, repository, number)
    if _pr_head_sha(pr) != head_sha:
        raise ExecutorError(EXIT_STALE, "STALE_SNAPSHOT", "Merge target head changed")
    if pr.get("merged_at"):
        merge_sha = pr.get("merge_commit_sha")
        if not isinstance(merge_sha, str) or not SHA40_RE.fullmatch(merge_sha):
            raise ExecutorError(
                EXIT_BLOCKED, "AMBIGUOUS_REMOTE", "Merged PR has no valid merge SHA"
            )
        return merge_sha, False
    if str(pr.get("state") or "").lower() != "open":
        raise ExecutorError(EXIT_STALE, "STALE_SNAPSHOT", "Merge target is not open")
    required, approvals, queue = _protection_requirements(
        runner, repository, candidate["base"]["ref"]
    )
    if queue and len(candidate["sources"]) > 1:
        raise ExecutorError(
            EXIT_PROTECTION,
            "PROTECTION",
            "Multi-source replacements cannot be submitted to a merge queue safely",
        )
    state["status"] = "waiting-checks"
    _save_state(state_path, state, now, dry_run=mutations.dry_run)
    _wait_for_checks(
        runner, repository, number, head_sha, required, approvals, author_login
    )
    command = [
        "gh",
        "pr",
        "merge",
        str(number),
        "--repo",
        _gh_repo_arg(repository),
        "--match-head-commit",
        head_sha,
    ]
    if not queue:
        capabilities = _merge_capabilities(runner, repository)
        if capabilities["squashMergeAllowed"]:
            command.append("--squash")
        elif capabilities["rebaseMergeAllowed"]:
            command.append("--rebase")
        elif capabilities["mergeCommitAllowed"]:
            command.append("--merge")
        else:
            raise ExecutorError(
                EXIT_PROTECTION,
                "PROTECTION",
                "Repository permits no supported merge method",
            )
    _revalidate_base(runner, candidate)
    if pre_merge_check is not None:
        pre_merge_check()
    target = (
        "replacement"
        if candidate["mode"] == "replacement"
        else f"source:{number}@{head_sha}"
    )
    _attempt_operation(state, "merge", target)
    mutations.run(command)
    if mutations.dry_run:
        return "", queue
    if queue:
        state["status"] = "queued"
        _save_state(state_path, state, now, dry_run=False)
        for _ in range(61):
            pr = _get_pr(runner, repository, number)
            if pr.get("merged_at"):
                break
            runner.sleep(30)
        else:
            raise ExecutorError(
                EXIT_BLOCKED,
                "TIMEOUT",
                "Merge queue did not merge the PR within 30 minutes",
            )
    else:
        pr = _get_pr(runner, repository, number)
    merge_sha = pr.get("merge_commit_sha")
    if (
        not pr.get("merged_at")
        or not isinstance(merge_sha, str)
        or not SHA40_RE.fullmatch(merge_sha)
    ):
        raise ExecutorError(
            EXIT_BLOCKED, "TRANSIENT", "Merge command did not produce a confirmed merge"
        )
    return merge_sha, queue


def _publish(
    runner: Runner,
    mutations: _Mutations,
    plan: dict[str, Any],
    state: dict[str, Any],
    candidate_root: Path,
    state_path: str | Path,
    now: str | None,
) -> None:
    candidate = plan["candidate"]
    repository = candidate["repository"]
    _revalidate_base(runner, candidate)
    live_sources: list[tuple[Mapping[str, Any], Sequence[str]]] = []
    for source in candidate["sources"]:
        pr = _get_pr(runner, repository, source["number"])
        direct_update = (
            candidate["decision"] == "update" and candidate["mode"] == "direct"
        )
        replacement_update = (
            candidate["decision"] == "update" and candidate["mode"] == "replacement"
        )
        _verify_source_pr(
            pr,
            candidate,
            source,
            require_open=replacement_update,
            allow_merged=direct_update,
        )
        manifests = (
            candidate["manifestPaths"]
            if len(candidate["sources"]) == 1
            else _live_source_manifests(runner, repository, source["number"])
        )
        live_sources.append((pr, manifests))
    _validate_live_sources(live_sources, candidate)
    if candidate["decision"] != "update":
        for evidence in candidate["closureEvidence"]:
            _validate_closure_predicate(runner, candidate, evidence)
        for source in candidate["sources"]:
            _close_one_source(
                runner,
                mutations,
                plan,
                state,
                source,
                _closure_marker(candidate, source),
                allow_preclosed=False,
                state_path=state_path,
                now=now,
            )
        if not mutations.dry_run:
            state["status"] = "closed"
        _save_state(state_path, state, now, dry_run=mutations.dry_run)
        return
    if candidate["mode"] == "direct":
        source = candidate["sources"][0]
        pr = _get_pr(runner, repository, source["number"])
        if pr.get("merged_at"):
            merge_sha = pr.get("merge_commit_sha")
            if not isinstance(merge_sha, str) or not SHA40_RE.fullmatch(merge_sha):
                raise ExecutorError(
                    EXIT_BLOCKED,
                    "AMBIGUOUS_REMOTE",
                    "Merged direct source lacks merge SHA",
                )
            state["mergeCommitSha"] = merge_sha
            state["status"] = "merged"
            state["sources"][0]["status"] = "merged"
            _confirm_operation(
                state,
                "merge",
                f"source:{source['number']}@{source['headSha']}",
                f"merge={merge_sha}",
            )
        elif str(pr.get("state") or "").lower() == "open":
            state["status"] = "published"
        else:
            raise ExecutorError(
                EXIT_STALE, "STALE_SNAPSHOT", "Direct source is closed without merge"
            )
        _save_state(state_path, state, now, dry_run=mutations.dry_run)
        return
    _publish_replacement(
        runner, mutations, plan, state, candidate_root, state_path, now
    )


def _finalize(
    runner: Runner,
    mutations: _Mutations,
    plan: dict[str, Any],
    state: dict[str, Any],
    state_path: str | Path,
    now: str | None,
) -> None:
    candidate = plan["candidate"]
    if candidate["decision"] != "update":
        raise ExecutorError(
            EXIT_CONTRACT, "CONTRACT", "Only update plans can be finalized"
        )
    repository = candidate["repository"]
    if candidate["mode"] == "direct":
        source = candidate["sources"][0]
        pr = _get_pr(runner, repository, source["number"])
        _verify_source_pr(
            pr,
            candidate,
            source,
            allow_merged=True,
        )
        _validate_live_source_metadata(pr, candidate)
        if pr.get("merged_at"):
            merge_sha = pr.get("merge_commit_sha")
            if not isinstance(merge_sha, str) or not SHA40_RE.fullmatch(merge_sha):
                raise ExecutorError(
                    EXIT_BLOCKED,
                    "AMBIGUOUS_REMOTE",
                    "Merged direct PR lacks a valid merge SHA",
                )
            if state["mergeCommitSha"] not in {None, merge_sha}:
                raise ExecutorError(
                    EXIT_BLOCKED,
                    "AMBIGUOUS_REMOTE",
                    "Recorded direct merge no longer matches GitHub",
                )
            state["mergeCommitSha"] = merge_sha
            state["status"] = "merged"
            state["sources"][0]["status"] = "merged"
            _confirm_operation(
                state,
                "merge",
                f"source:{source['number']}@{source['headSha']}",
                f"merge={merge_sha}",
            )
            _save_state(state_path, state, now, dry_run=mutations.dry_run)
            return
        if state["status"] == "merged" or state["mergeCommitSha"] is not None:
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "State records a direct merge that GitHub does not confirm",
            )
        _revalidate_base(runner, candidate)
        merge_sha, _ = _merge_pr(
            runner,
            mutations,
            plan,
            state,
            source["number"],
            source["headSha"],
            "dependabot[bot]",
            state_path,
            now,
        )
        if mutations.dry_run:
            return
        state["mergeCommitSha"] = merge_sha
        state["status"] = "merged"
        state["sources"][0]["status"] = "merged"
        _confirm_operation(
            state,
            "merge",
            f"source:{source['number']}@{source['headSha']}",
            f"merge={merge_sha}",
        )
        _save_state(state_path, state, now, dry_run=False)
        return

    replacements = _find_replacements(runner, plan)
    if len(replacements) != 1:
        raise ExecutorError(
            EXIT_BLOCKED,
            "AMBIGUOUS_REMOTE",
            "Finalize requires exactly one marked replacement PR",
        )
    replacement = replacements[0]
    _validate_replacement_pr(plan, replacement, require_current_marker=True)
    number = replacement.get("number")
    head_sha = _pr_head_sha(replacement)
    if not isinstance(number, int) or head_sha != candidate["commitSha"]:
        raise ExecutorError(
            EXIT_STALE, "STALE_SNAPSHOT", "Replacement identity changed"
        )
    live_sources = []
    replacement_is_merged = bool(replacement.get("merged_at"))
    for source in candidate["sources"]:
        source_pr = _get_pr(runner, repository, source["number"])
        _verify_source_pr(
            source_pr,
            candidate,
            source,
            require_open=not replacement_is_merged,
        )
        manifests = (
            candidate["manifestPaths"]
            if len(candidate["sources"]) == 1
            else _live_source_manifests(runner, repository, source["number"])
        )
        live_sources.append((source_pr, manifests))
    _validate_live_sources(live_sources, candidate)
    state["replacement"] = {
        "number": number,
        "url": str(replacement.get("html_url") or replacement.get("url") or ""),
        "headSha": head_sha,
    }
    if replacement_is_merged:
        merge_sha = replacement.get("merge_commit_sha")
        if not isinstance(merge_sha, str) or not SHA40_RE.fullmatch(merge_sha):
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "Merged replacement lacks a valid merge SHA",
            )
        if state["mergeCommitSha"] not in {None, merge_sha}:
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "Recorded replacement merge no longer matches GitHub",
            )
        state["mergeCommitSha"] = merge_sha
        state["status"] = "merged"
        _confirm_operation(state, "merge", "replacement", f"merge={merge_sha}")
        _save_state(state_path, state, now, dry_run=mutations.dry_run)
    else:
        if (
            state["status"] in {"merged", "sources-closed"}
            or state["mergeCommitSha"] is not None
        ):
            raise ExecutorError(
                EXIT_BLOCKED,
                "AMBIGUOUS_REMOTE",
                "State records a replacement merge that GitHub does not confirm",
            )
        _revalidate_base(runner, candidate)

        def verify_sources_immediately_before_merge() -> None:
            for planned_source in candidate["sources"]:
                live_source = _get_pr(runner, repository, planned_source["number"])
                _verify_source_pr(
                    live_source,
                    candidate,
                    planned_source,
                    require_open=True,
                )

        merge_sha, _ = _merge_pr(
            runner,
            mutations,
            plan,
            state,
            number,
            head_sha,
            repository["actorLogin"],
            state_path,
            now,
            pre_merge_check=verify_sources_immediately_before_merge,
        )
        if mutations.dry_run:
            return
        state["mergeCommitSha"] = merge_sha
        state["status"] = "merged"
        _confirm_operation(state, "merge", "replacement", f"merge={merge_sha}")
        _save_state(state_path, state, now, dry_run=False)
    for source in candidate["sources"]:
        _close_one_source(
            runner,
            mutations,
            plan,
            state,
            source,
            _replacement_close_marker(plan, source, number, merge_sha),
            allow_preclosed=True,
            state_path=state_path,
            now=now,
        )
    if mutations.dry_run:
        return
    state["status"] = "sources-closed"
    _save_state(state_path, state, now, dry_run=False)


def apply_plan(
    root: str | Path,
    candidate_root: str | Path,
    plan: dict[str, Any],
    state_path: str | Path,
    phase: str,
    approval_token: str | None = None,
    parent_plan: dict[str, Any] | None = None,
    dry_run: bool = False,
    runner: Runner | None = None,
    now: str | None = None,
) -> ApplyOutcome:
    """Apply one immutable plan phase after revalidating every safety guard."""

    runner = runner or Runner()
    _contract(
        phase in {"publish", "finalize"}, "Apply phase must be publish or finalize"
    )
    _verify_plan_structure(plan)
    _approval_guard(plan, approval_token, parent_plan)
    candidate = plan["candidate"]
    observed_repository = _resolve_repository(root, runner)
    if _repository_runtime_identity(
        observed_repository
    ) != _repository_runtime_identity(candidate["repository"]):
        raise ExecutorError(
            EXIT_STALE,
            "STALE_SNAPSHOT",
            "Current repository identity differs from the plan",
        )
    candidate_path = _verify_candidate_git(candidate_root, candidate, runner)
    state = _load_state(state_path, plan, now)
    mutations = _Mutations(runner, dry_run)
    if state["status"] == "blocked":
        state["blocked"] = None
        if state.get("mergeCommitSha"):
            state["status"] = "merged"
        elif state.get("replacement"):
            state["status"] = "published"
        else:
            state["status"] = "planned"
        for operation in state["operations"]:
            if operation["status"] == "blocked":
                operation["status"] = "pending"
    try:
        if phase == "publish":
            _publish(runner, mutations, plan, state, candidate_path, state_path, now)
        else:
            _finalize(runner, mutations, plan, state, state_path, now)
    except ExecutorError as caught:
        exc = caught
        if exc.exit_code == EXIT_INCOMPLETE:
            exc = ExecutorError(
                EXIT_BLOCKED,
                "TRANSIENT",
                exc.message,
                exc.details,
            )
        if exc.exit_code in {EXIT_STALE, EXIT_PROTECTION, EXIT_BLOCKED}:
            reason = {
                EXIT_STALE: "stale-snapshot",
                EXIT_PROTECTION: "protection",
                EXIT_BLOCKED: "timeout"
                if exc.code == "TIMEOUT"
                else (
                    "ambiguous-remote"
                    if exc.code == "AMBIGUOUS_REMOTE"
                    else "transient"
                ),
            }[exc.exit_code]
            state["status"] = "blocked"
            state["blocked"] = {"reason": reason, "action": exc.message}
            for operation in state["operations"]:
                if operation["status"] == "pending":
                    operation["status"] = "blocked"
                    operation["lastObserved"] = exc.message
                    break
            _save_state(state_path, state, now, dry_run=dry_run)
            exc.details.setdefault("state", state)
        raise exc
    return ApplyOutcome(state=state, commands=mutations.commands, dry_run=dry_run)


def _read_json(path: str | Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutorError(
            EXIT_CONTRACT, "CONTRACT", f"{label} is unreadable or malformed"
        ) from exc
    if not isinstance(value, dict):
        raise ExecutorError(
            EXIT_CONTRACT, "CONTRACT", f"{label} must contain a JSON object"
        )
    return value


def _write_stdout(value: Any) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    sys.stdout.write("\n")


def _absolute_path(value: str, label: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ExecutorError(
            EXIT_CONTRACT, "CONTRACT", f"{label} must be an absolute path"
        )
    return str(path.resolve())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve Dependabot pull requests safely"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Build a read-only Dependabot inventory"
    )
    inspect_parser.add_argument("--root", required=True)
    inspect_parser.add_argument("--now")

    plan_parser = subparsers.add_parser(
        "plan", help="Validate a candidate and create an immutable plan"
    )
    plan_parser.add_argument("--inventory", required=True)
    plan_parser.add_argument("--candidate", required=True)
    plan_parser.add_argument("--output", required=True)

    apply_parser = subparsers.add_parser("apply", help="Apply one plan phase")
    apply_parser.add_argument("--root", required=True)
    apply_parser.add_argument("--candidate-root", required=True)
    apply_parser.add_argument("--plan", required=True)
    apply_parser.add_argument("--state", required=True)
    apply_parser.add_argument("--phase", choices=("publish", "finalize"), required=True)
    apply_parser.add_argument("--parent-plan")
    apply_parser.add_argument("--approval-token")
    apply_parser.add_argument("--dry-run", action="store_true")
    return parser


def _inspect_exit(inventory: Mapping[str, Any]) -> int:
    if inventory.get("complete") is True:
        return EXIT_OK
    codes = {
        item.get("code")
        for item in inventory.get("errors", [])
        if isinstance(item, dict)
    }
    if codes & {"REPO_MISMATCH", "CONTRACT"}:
        return EXIT_CONTRACT
    if inventory.get("repository") is None and codes & {"ENV", "AUTH"}:
        return EXIT_ENV
    return EXIT_INCOMPLETE


def main(argv: Sequence[str] | None = None, runner: Runner | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    runner = runner or Runner()
    try:
        if args.command == "inspect":
            root = _absolute_path(args.root, "--root")
            inventory = inspect_repository(root, args.now, runner)
            _write_stdout(inventory)
            return _inspect_exit(inventory)
        if args.command == "plan":
            inventory = _read_json(args.inventory, "inventory")
            candidate = _read_json(args.candidate, "candidate")
            plan = build_plan(inventory, candidate)
            _atomic_json(args.output, plan)
            _write_stdout(plan)
            return EXIT_OK
        root = _absolute_path(args.root, "--root")
        candidate_root = _absolute_path(args.candidate_root, "--candidate-root")
        plan = _read_json(args.plan, "plan")
        parent = (
            _read_json(args.parent_plan, "parent plan") if args.parent_plan else None
        )
        outcome = apply_plan(
            root,
            candidate_root,
            plan,
            args.state,
            args.phase,
            approval_token=args.approval_token,
            parent_plan=parent,
            dry_run=args.dry_run,
            runner=runner,
        )
        if outcome.dry_run:
            _write_stdout({"state": outcome.state, "commands": outcome.commands})
        else:
            _write_stdout(outcome.state)
        return EXIT_OK
    except ExecutorError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        if "state" in exc.details:
            _write_stdout(exc.details["state"])
        else:
            _write_stdout(exc.as_json())
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
