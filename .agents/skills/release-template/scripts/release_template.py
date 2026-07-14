#!/usr/bin/env python3
"""Inspect and publish immutable releases of the canonical Copier template."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn, Protocol, Sequence, TextIO
from urllib.parse import urlsplit

SEMVER_TAG_RE = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

EXIT_LOCAL_GUARD = 10
EXIT_REMOTE_GUARD = 20
EXIT_GIT_FAILURE = 30

CANONICAL_REPO = ("llamitai", "wise")
CANONICAL_ORIGIN_URL = "https://github.com/Llamitai/wise.git"
MIRROR_URL = "https://github.com/Llamitai/saas-bootstrap-template.git"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        check: bool = True,
    ) -> CommandResult: ...


class ReleaseError(RuntimeError):
    def __init__(
        self,
        exit_code: int,
        code: str,
        message: str,
        action: str,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code
        self.message = message
        self.action = action


class SubprocessGitRunner:
    """Run Git without a shell so refs and paths cannot become shell input."""

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        check: bool = True,
    ) -> CommandResult:
        command = ["git", *args]
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReleaseError(
                EXIT_GIT_FAILURE,
                "git-execution-failed",
                f"Git could not execute: {exc}",
                "Fix the local Git installation or connectivity, then inspect again.",
            ) from exc

        result = CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and result.returncode != 0:
            detail = (
                result.stderr.strip() or result.stdout.strip() or "unknown Git error"
            )
            raise ReleaseError(
                EXIT_GIT_FAILURE,
                "git-command-failed",
                f"Git command failed: {' '.join(command)}: {detail}",
                "Resolve the Git error, then restart with inspect.",
            )
        return result


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        print(
            json.dumps(
                {
                    "error": {
                        "code": "invalid-arguments",
                        "message": message,
                        "action": "Use --help and pass the exact inspect or publish arguments.",
                    }
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)


@dataclass(frozen=True)
class ReleaseConfig:
    origin_remote: str = "origin"
    expected_github_repo: tuple[str, str] | None = CANONICAL_REPO
    canonical_origin_url: str = CANONICAL_ORIGIN_URL
    mirror_remote: str = MIRROR_URL


@dataclass(frozen=True)
class RepositoryContext:
    root: Path
    origin_url: str
    push_url: str


@dataclass(frozen=True)
class Inspection:
    repo_root: Path
    origin_url: str
    head_sha: str
    head_subject: str
    previous_tag: str
    previous_sha: str
    previous_tag_is_ancestor: bool
    mirror_has_previous_tag: bool
    candidates: dict[str, str]
    origin_tags: dict[str, str] = field(repr=False)
    mirror_tags: dict[str, str] = field(repr=False)

    def as_json(self) -> dict[str, object]:
        return {
            "repoRoot": str(self.repo_root),
            "originUrl": self.origin_url,
            "headSha": self.head_sha,
            "headSubject": self.head_subject,
            "previousTag": self.previous_tag,
            "previousSha": self.previous_sha,
            "previousTagIsAncestor": self.previous_tag_is_ancestor,
            "mirrorHasPreviousTag": self.mirror_has_previous_tag,
            "candidates": self.candidates,
        }


def parse_semver_tag(tag: str) -> tuple[int, int, int]:
    match = SEMVER_TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"not a strict SemVer tag: {tag}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def next_version_candidates(previous_tag: str) -> dict[str, str]:
    major, minor, patch = parse_semver_tag(previous_tag)
    return {
        "patch": f"v{major}.{minor}.{patch + 1}",
        "minor": f"v{major}.{minor + 1}.0",
        "major": f"v{major + 1}.0.0",
    }


def parse_remote_tags(output: str) -> dict[str, str]:
    direct: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for raw_line in output.splitlines():
        parts = raw_line.split()
        if len(parts) != 2 or not FULL_SHA_RE.fullmatch(parts[0]):
            continue
        sha, ref = parts
        if not ref.startswith("refs/tags/"):
            continue
        if ref.endswith("^{}"):
            peeled[ref[:-3]] = sha.lower()
        else:
            direct[ref] = sha.lower()

    tags: dict[str, str] = {}
    for ref, sha in direct.items():
        tag = ref.removeprefix("refs/tags/")
        if SEMVER_TAG_RE.fullmatch(tag):
            tags[tag] = peeled.get(ref, sha)
    return tags


def normalize_github_repo(
    url: str,
    *,
    for_push: bool = False,
) -> tuple[str, str] | None:
    value = url.strip()
    if value.startswith("git@github.com:"):
        path = value.removeprefix("git@github.com:")
    else:
        parsed = urlsplit(value)
        allowed_schemes = {"https", "ssh"} if for_push else {"git", "https", "ssh"}
        if parsed.scheme.lower() not in allowed_schemes:
            return None
        if (parsed.hostname or "").lower() != "github.com":
            return None
        path = parsed.path.lstrip("/")
    path = path.removesuffix(".git").rstrip("/")
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0].lower(), parts[1].lower()


def find_repository(
    runner: CommandRunner,
    start: Path,
    config: ReleaseConfig,
) -> RepositoryContext:
    root_result = runner.run(["rev-parse", "--show-toplevel"], cwd=start, check=False)
    if root_result.returncode != 0 or not root_result.stdout.strip():
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "not-a-git-repository",
            "The current directory is not inside a Git repository.",
            "Run the skill from inside the canonical Llamitai/wise checkout.",
        )
    root = Path(root_result.stdout.strip()).resolve()

    remote_result = runner.run(
        ["remote", "get-url", config.origin_remote], cwd=root, check=False
    )
    if remote_result.returncode != 0 or not remote_result.stdout.strip():
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "origin-missing",
            "The repository has no usable origin remote.",
            "Configure origin for Llamitai/wise, then inspect again.",
        )
    origin_url = remote_result.stdout.strip().splitlines()[0]
    push_urls_result = runner.run(
        ["remote", "get-url", "--push", "--all", config.origin_remote],
        cwd=root,
        check=False,
    )
    push_urls = [
        line.strip() for line in push_urls_result.stdout.splitlines() if line.strip()
    ]
    if push_urls_result.returncode != 0 or not push_urls:
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "origin-push-url-missing",
            "The origin remote has no usable push URL.",
            "Configure origin to push only to Llamitai/wise, then inspect again.",
        )
    if config.expected_github_repo is not None:
        actual_repo = normalize_github_repo(origin_url)
        if actual_repo != config.expected_github_repo:
            raise ReleaseError(
                EXIT_LOCAL_GUARD,
                "wrong-origin",
                "The origin remote is not the canonical Llamitai/wise repository.",
                "Use the canonical checkout; do not publish a fork.",
            )
        if any(
            normalize_github_repo(push_url, for_push=True)
            != config.expected_github_repo
            for push_url in push_urls
        ):
            raise ReleaseError(
                EXIT_LOCAL_GUARD,
                "wrong-origin-push-url",
                "At least one effective origin push URL is not Llamitai/wise.",
                "Remove every noncanonical pushurl before inspecting or publishing.",
            )
    return RepositoryContext(
        root=root,
        origin_url=origin_url,
        push_url=push_urls[0],
    )


def ls_remote_tags(
    runner: CommandRunner,
    root: Path,
    remote: str,
) -> dict[str, str]:
    result = runner.run(["ls-remote", "--tags", remote], cwd=root)
    return parse_remote_tags(result.stdout)


def remote_main_sha(
    runner: CommandRunner,
    root: Path,
    origin_remote: str,
) -> str:
    result = runner.run(
        ["ls-remote", "--heads", origin_remote, "refs/heads/main"],
        cwd=root,
    )
    matches = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if (
            len(parts) == 2
            and FULL_SHA_RE.fullmatch(parts[0])
            and parts[1] == "refs/heads/main"
        ):
            matches.append(parts[0].lower())
    if len(matches) != 1:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "remote-main-missing",
            "origin/main could not be resolved to exactly one commit.",
            "Verify the canonical remote and its main branch, then inspect again.",
        )
    return matches[0]


def local_tag_commit(
    runner: CommandRunner,
    root: Path,
    tag: str,
) -> str | None:
    result = runner.run(
        ["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip().lower()
    return sha if FULL_SHA_RE.fullmatch(sha) else None


def local_tag_object(
    runner: CommandRunner,
    root: Path,
    tag: str,
) -> str | None:
    result = runner.run(
        ["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip().lower()
    return sha if FULL_SHA_RE.fullmatch(sha) else None


def validate_local_release_state(
    runner: CommandRunner,
    context: RepositoryContext,
    config: ReleaseConfig,
) -> tuple[str, str]:
    branch = runner.run(
        ["symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=context.root,
        check=False,
    )
    if branch.returncode != 0 or branch.stdout.strip() != "main":
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "wrong-branch",
            "Template releases must be created from the local main branch.",
            "Switch to main without discarding work, then inspect again.",
        )

    status = runner.run(["status", "--porcelain"], cwd=context.root)
    if status.stdout.strip():
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "dirty-worktree",
            "The worktree or index contains uncommitted changes.",
            "Commit or safely set aside all changes before releasing.",
        )

    head_sha = (
        runner.run(["rev-parse", "HEAD"], cwd=context.root).stdout.strip().lower()
    )
    remote_sha = remote_main_sha(runner, context.root, config.origin_remote)
    if head_sha != remote_sha:
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "head-not-on-origin-main",
            "Local HEAD does not match the commit published at origin/main.",
            "Push or synchronize main through the normal review flow, then inspect again.",
        )
    subject = runner.run(
        ["show", "-s", "--format=%s", head_sha], cwd=context.root
    ).stdout.strip()
    return head_sha, subject


def inspect_repository(
    runner: CommandRunner,
    start: Path,
    config: ReleaseConfig = ReleaseConfig(),
) -> Inspection:
    context = find_repository(runner, start, config)
    head_sha, head_subject = validate_local_release_state(runner, context, config)

    origin_tags = ls_remote_tags(runner, context.root, config.origin_remote)
    if not origin_tags:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "no-previous-semver-tag",
            "origin has no strict vX.Y.Z tag to increment.",
            "Create the initial release outside this skill, then use it for later releases.",
        )
    previous_tag = max(origin_tags, key=parse_semver_tag)
    previous_sha = origin_tags[previous_tag]

    local_previous_sha = local_tag_commit(runner, context.root, previous_tag)
    if local_previous_sha != previous_sha:
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "previous-tag-not-synchronized",
            f"Local {previous_tag} does not resolve to its origin commit.",
            "Synchronize tags from origin without moving published tags, then inspect again.",
        )

    mirror_tags = ls_remote_tags(runner, context.root, config.mirror_remote)
    if previous_tag not in mirror_tags:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "previous-tag-missing-from-mirror",
            f"{previous_tag} has not been published to the template mirror.",
            "Repair or rerun its publish-template workflow; do not create a newer tag.",
        )

    tree_diff = runner.run(
        ["diff", "--quiet", previous_sha, head_sha],
        cwd=context.root,
        check=False,
    )
    if tree_diff.returncode == 0:
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "no-release-changes",
            f"There are no tree changes between {previous_tag} and origin/main.",
            "Do not create a release until the template repository changes.",
        )
    if tree_diff.returncode != 1:
        raise ReleaseError(
            EXIT_GIT_FAILURE,
            "tree-diff-failed",
            "Git could not compare the previous release with origin/main.",
            "Repair the local Git objects, then inspect again.",
        )

    ancestor = runner.run(
        ["merge-base", "--is-ancestor", previous_sha, head_sha],
        cwd=context.root,
        check=False,
    )
    if ancestor.returncode not in (0, 1):
        raise ReleaseError(
            EXIT_GIT_FAILURE,
            "ancestry-check-failed",
            "Git could not determine whether the previous tag is an ancestor.",
            "Repair the local Git objects, then inspect again.",
        )

    display_origin = (
        config.canonical_origin_url
        if config.expected_github_repo is not None
        else context.origin_url
    )
    return Inspection(
        repo_root=context.root,
        origin_url=display_origin,
        head_sha=head_sha,
        head_subject=head_subject,
        previous_tag=previous_tag,
        previous_sha=previous_sha,
        previous_tag_is_ancestor=ancestor.returncode == 0,
        mirror_has_previous_tag=True,
        candidates=next_version_candidates(previous_tag),
        origin_tags=origin_tags,
        mirror_tags=mirror_tags,
    )


def validate_publish_arguments(
    expected_previous_tag: str,
    tag: str,
    expected_head: str,
    confirm_tag: str,
) -> str:
    try:
        candidates = next_version_candidates(expected_previous_tag)
    except ValueError as exc:
        raise ReleaseError(
            2,
            "invalid-previous-tag",
            str(exc),
            "Use the exact previousTag returned by inspect.",
        ) from exc
    if tag not in candidates.values():
        raise ReleaseError(
            2,
            "invalid-next-version",
            f"{tag} is not an immediate SemVer candidate after {expected_previous_tag}.",
            f"Choose one of: {', '.join(candidates.values())}.",
        )
    if confirm_tag != tag:
        raise ReleaseError(
            2,
            "confirmation-mismatch",
            "--confirm-tag does not exactly match --tag.",
            "Obtain explicit user approval and pass the approved tag unchanged.",
        )
    if not FULL_SHA_RE.fullmatch(expected_head):
        raise ReleaseError(
            2,
            "invalid-expected-head",
            "--expected-head must be a full 40-character commit SHA.",
            "Use the exact headSha returned by inspect.",
        )
    return expected_head.lower()


def already_on_origin_result(tag: str, sha: str) -> dict[str, object]:
    return {
        "tag": tag,
        "sha": sha,
        "pushed": False,
        "alreadyOnOrigin": True,
        "workflowTriggered": None,
    }


def handle_remote_target(
    origin_tags: dict[str, str],
    tag: str,
    expected_head: str,
) -> dict[str, object] | None:
    remote_sha = origin_tags.get(tag)
    if remote_sha is None:
        return None
    if remote_sha != expected_head:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "tag-sha-conflict",
            f"origin already has {tag} at an unexpected commit.",
            "Do not move the tag; investigate the immutable release history.",
        )
    return already_on_origin_result(tag, expected_head)


def revalidate_publish_snapshot(
    runner: CommandRunner,
    context: RepositoryContext,
    config: ReleaseConfig,
    *,
    expected_previous_tag: str,
    tag: str,
    expected_head: str,
) -> dict[str, object] | None:
    origin_tags = ls_remote_tags(runner, context.root, config.origin_remote)
    idempotent = handle_remote_target(origin_tags, tag, expected_head)
    if idempotent is not None:
        return idempotent
    if (
        not origin_tags
        or max(origin_tags, key=parse_semver_tag) != expected_previous_tag
    ):
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "previous-tag-changed",
            "The latest origin tag changed after the proposal was approved.",
            "Restart with inspect and obtain approval for a fresh proposal.",
        )
    if remote_main_sha(runner, context.root, config.origin_remote) != expected_head:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "remote-main-changed",
            "origin/main changed while the approved release was being prepared.",
            "Restart with inspect and obtain approval for the new SHA.",
        )

    mirror_tags = ls_remote_tags(runner, context.root, config.mirror_remote)
    if expected_previous_tag not in mirror_tags:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "previous-tag-missing-from-mirror",
            f"{expected_previous_tag} is no longer visible in the template mirror.",
            "Repair or rerun its publish-template workflow; do not push a newer tag.",
        )
    if tag in mirror_tags:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "tag-only-on-mirror",
            f"{tag} exists in the mirror but not on origin.",
            "Investigate the inconsistent release state; do not create or move tags.",
        )
    return None


def publish_release(
    runner: CommandRunner,
    start: Path,
    *,
    expected_previous_tag: str,
    tag: str,
    expected_head: str,
    confirm_tag: str,
    config: ReleaseConfig = ReleaseConfig(),
) -> dict[str, object]:
    expected_head = validate_publish_arguments(
        expected_previous_tag, tag, expected_head, confirm_tag
    )
    context = find_repository(runner, start, config)

    initial_origin_tags = ls_remote_tags(runner, context.root, config.origin_remote)
    if expected_previous_tag not in initial_origin_tags:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "expected-previous-tag-missing",
            f"origin no longer contains the approved previous tag {expected_previous_tag}.",
            "Restart with inspect and review the release history.",
        )
    idempotent = handle_remote_target(initial_origin_tags, tag, expected_head)
    if idempotent is not None:
        return idempotent
    if max(initial_origin_tags, key=parse_semver_tag) != expected_previous_tag:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "previous-tag-changed",
            "The latest origin tag changed after the proposal was approved.",
            "Restart with inspect and obtain approval for a fresh proposal.",
        )

    inspection = inspect_repository(runner, context.root, config)
    if inspection.previous_tag != expected_previous_tag:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "previous-tag-changed",
            "The latest origin tag changed after the proposal was approved.",
            "Restart with inspect and obtain approval for a fresh proposal.",
        )
    if inspection.head_sha != expected_head:
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "head-changed",
            "origin/main changed after the proposal was approved.",
            "Restart with inspect and obtain approval for the new SHA.",
        )
    if tag in inspection.mirror_tags:
        raise ReleaseError(
            EXIT_REMOTE_GUARD,
            "tag-only-on-mirror",
            f"{tag} exists in the mirror but not on origin.",
            "Investigate the inconsistent release state; do not create or move tags.",
        )

    local_object_sha = local_tag_object(runner, context.root, tag)
    if local_object_sha is not None and local_object_sha != expected_head:
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "local-tag-sha-conflict",
            f"Local {tag} is not a lightweight tag at the approved commit.",
            "Do not move, replace, or delete it automatically; investigate before retrying.",
        )

    idempotent = revalidate_publish_snapshot(
        runner,
        context,
        config,
        expected_previous_tag=expected_previous_tag,
        tag=tag,
        expected_head=expected_head,
    )
    if idempotent is not None:
        return idempotent

    if local_object_sha is None:
        runner.run(["tag", tag, expected_head], cwd=context.root)
    if local_tag_object(runner, context.root, tag) != expected_head:
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "local-tag-changed",
            f"Local {tag} changed while the release was being prepared.",
            "Do not push it. Investigate the local ref and restart with inspect.",
        )

    idempotent = revalidate_publish_snapshot(
        runner,
        context,
        config,
        expected_previous_tag=expected_previous_tag,
        tag=tag,
        expected_head=expected_head,
    )
    if idempotent is not None:
        return idempotent

    if local_tag_object(runner, context.root, tag) != expected_head:
        raise ReleaseError(
            EXIT_LOCAL_GUARD,
            "local-tag-changed",
            f"Local {tag} changed immediately before push.",
            "Do not push it. Investigate the local ref and restart with inspect.",
        )

    try:
        push = runner.run(
            [
                "push",
                "--porcelain",
                context.push_url,
                f"{expected_head}:refs/tags/{tag}",
            ],
            cwd=context.root,
            check=False,
        )
    except ReleaseError as push_error:
        try:
            ambiguous_tags = ls_remote_tags(runner, context.root, config.origin_remote)
            idempotent = handle_remote_target(ambiguous_tags, tag, expected_head)
        except ReleaseError:
            raise push_error
        if idempotent is not None:
            return idempotent
        raise push_error
    if push.returncode != 0:
        post_failure_tags = ls_remote_tags(runner, context.root, config.origin_remote)
        idempotent = handle_remote_target(post_failure_tags, tag, expected_head)
        if idempotent is not None:
            return idempotent
        detail = push.stderr.strip() or push.stdout.strip() or "unknown Git error"
        detail = re.sub(r"(://)[^/@\s]+@", r"\1***@", detail)
        raise ReleaseError(
            EXIT_GIT_FAILURE,
            "tag-push-failed",
            f"The local tag was preserved, but its push failed: {detail}",
            "Keep the local tag. Re-run inspect, present the same summary, and obtain fresh approval before retrying.",
        )

    verified_tags = ls_remote_tags(runner, context.root, config.origin_remote)
    if verified_tags.get(tag) != expected_head:
        raise ReleaseError(
            EXIT_GIT_FAILURE,
            "tag-push-not-verifiable",
            f"The push returned success, but origin/{tag} could not be verified.",
            "Inspect the remote and workflow state manually; never force or recreate the tag.",
        )
    push_lines = push.stdout.splitlines()
    created_remote_ref = any(line.startswith("*\t") for line in push_lines)
    unchanged_remote_ref = any(line.startswith("=\t") for line in push_lines)
    if unchanged_remote_ref and not created_remote_ref:
        return already_on_origin_result(tag, expected_head)
    if not created_remote_ref:
        raise ReleaseError(
            EXIT_GIT_FAILURE,
            "tag-push-result-ambiguous",
            "origin has the expected tag, but Git did not report creating its ref.",
            "Inspect the existing workflow run; do not push, force, or recreate the tag.",
        )
    return {
        "tag": tag,
        "sha": expected_head,
        "pushed": True,
        "alreadyOnOrigin": False,
        "workflowTriggered": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        description="Safely inspect or publish the canonical Copier template release.",
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=JsonArgumentParser,
    )
    subparsers.add_parser(
        "inspect",
        help="Run read-only release guards.",
        allow_abbrev=False,
    )

    publish = subparsers.add_parser(
        "publish",
        help="Create and push an explicitly approved release tag.",
        allow_abbrev=False,
    )
    publish.add_argument("--expected-previous-tag", required=True)
    publish.add_argument("--tag", required=True)
    publish.add_argument("--expected-head", required=True)
    publish.add_argument("--confirm-tag", required=True)
    return parser


def emit_json(payload: dict[str, object], *, stream: TextIO = sys.stdout) -> None:
    print(json.dumps(payload, sort_keys=True), file=stream)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runner = SubprocessGitRunner()
    try:
        if args.command == "inspect":
            emit_json(inspect_repository(runner, Path.cwd()).as_json())
        else:
            emit_json(
                publish_release(
                    runner,
                    Path.cwd(),
                    expected_previous_tag=args.expected_previous_tag,
                    tag=args.tag,
                    expected_head=args.expected_head,
                    confirm_tag=args.confirm_tag,
                )
            )
    except ReleaseError as exc:
        emit_json(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "action": exc.action,
                }
            },
            stream=sys.stderr,
        )
        return exc.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
