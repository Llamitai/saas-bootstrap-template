from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

from fake_cli import FakeRunner


NOW = "2026-07-13T18:00:00Z"
LATER = "2026-07-13T19:00:00Z"
BASE_SHA = "1" * 40
PATCH_HEAD_SHA = "2" * 40
MAJOR_HEAD_SHA = "3" * 40
PATCH_TREE_SHA = "4" * 40
MAJOR_TREE_SHA = "5" * 40
MERGE_SHA = "6" * 40
CONTENT_SHA = "7" * 64
REPO_ROOT = "/workspace/wise"
NAME_WITH_OWNER = "Llamitai/wise"
GH_REPO = f"github.com/{NAME_WITH_OWNER}"


def load_executor() -> ModuleType:
    script = Path(__file__).parents[1] / "scripts" / "dependabot_prs.py"
    spec = importlib.util.spec_from_file_location(
        "resolve_dependabot_prs_executor", script
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


executor = load_executor()


def repository() -> dict[str, Any]:
    return {
        "host": "github.com",
        "nameWithOwner": NAME_WITH_OWNER,
        "remote": "origin",
        "root": REPO_ROOT,
        "defaultBranch": "main",
        "defaultBranchSha": BASE_SHA,
        "actorLogin": "automation-user",
    }


def dependency(
    *,
    name: str,
    from_version: str,
    to_version: str,
    impact: str,
    prerelease: bool = False,
    ecosystem: str = "npm",
) -> dict[str, Any]:
    return {
        "name": name,
        "ecosystem": ecosystem,
        "fromVersion": from_version,
        "toVersion": to_version,
        "rawUpdateType": f"version-update:semver-{impact}",
        "dependencyType": "direct",
        "impact": impact,
        "prerelease": prerelease,
    }


def pull_request(
    *,
    number: int,
    head_sha: str,
    dependency_value: dict[str, Any],
    manifest: str = "frontend/package.json",
    lockfile: str = "frontend/pnpm-lock.yaml",
    security_update: bool = False,
) -> dict[str, Any]:
    return {
        "number": number,
        "url": f"https://github.com/{NAME_WITH_OWNER}/pull/{number}",
        "title": (
            f"Bump {dependency_value['name']} from "
            f"{dependency_value['fromVersion']} to {dependency_value['toVersion']}"
        ),
        "body": (
            f"Bumps [{dependency_value['name']}](https://example.test/release) from "
            f"{dependency_value['fromVersion']} to {dependency_value['toVersion']}."
        ),
        "author": {
            "login": "dependabot[bot]",
            "type": "Bot",
            "sourceLogin": "app/dependabot",
        },
        "base": {"repo": NAME_WITH_OWNER, "ref": "main", "sha": BASE_SHA},
        "head": {
            "repo": NAME_WITH_OWNER,
            "ref": f"dependabot/npm_and_yarn/{dependency_value['name']}",
            "sha": head_sha,
        },
        "maintainerCanModify": True,
        "files": sorted([manifest, lockfile]),
        "manifests": [manifest],
        "lockfiles": [lockfile],
        "dependencies": [dependency_value],
        "observedAggregateImpact": dependency_value["impact"],
        "securityUpdate": security_update,
    }


def group_key(*prs: dict[str, Any]) -> str:
    ordered = sorted(prs, key=lambda item: item["number"])
    first = ordered[0]
    payload = (
        "v1\n"
        f"{first['base']['repo']}\n"
        f"{first['base']['ref']}@{BASE_SHA}\n"
        + "".join(f"{pr['number']}@{pr['head']['sha']}\n" for pr in ordered)
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def group(*prs: dict[str, Any]) -> dict[str, Any]:
    ordered = sorted(prs, key=lambda item: item["number"])
    first = ordered[0]
    return {
        "groupKey": group_key(*ordered),
        "base": {
            "repo": first["base"]["repo"],
            "ref": first["base"]["ref"],
            "sha": BASE_SHA,
        },
        "prNumbers": [pr["number"] for pr in ordered],
        "manifestPaths": sorted({path for pr in ordered for path in pr["manifests"]}),
        "observedAggregateImpact": executor.aggregate_impact(
            [pr["observedAggregateImpact"] for pr in ordered]
        ),
    }


def inventory(
    *prs: dict[str, Any],
    overlaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    safe: dict[tuple[str, str], list[dict[str, Any]]] = {}
    singleton: list[list[dict[str, Any]]] = []
    for pr in prs:
        if pr["observedAggregateImpact"] in {"patch", "minor"} and all(
            item["prerelease"] is False for item in pr["dependencies"]
        ):
            safe.setdefault((pr["base"]["repo"], pr["base"]["ref"]), []).append(pr)
        else:
            singleton.append([pr])
    grouped = [*safe.values(), *singleton]
    return {
        "schemaVersion": 1,
        "complete": True,
        "generatedAt": NOW,
        "repository": repository(),
        "pullRequests": sorted(deepcopy(prs), key=lambda item: item["number"]),
        "overlaps": overlaps or [],
        "groups": sorted(
            (group(*items) for items in grouped),
            key=lambda item: item["groupKey"],
        ),
        "errors": [],
    }


def fatal_inventory() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "complete": False,
        "generatedAt": NOW,
        "repository": None,
        "pullRequests": [],
        "overlaps": [],
        "groups": [],
        "errors": [
            {
                "code": "AUTH",
                "message": "authentication unavailable",
                "prNumber": None,
                "transient": True,
            }
        ],
    }


def release_evidence(subject: str) -> dict[str, Any]:
    return {
        "kind": "release",
        "subject": subject,
        "url": f"https://example.invalid/releases/{subject}",
        "summary": "breaking=none; adaptation=not-required",
        "contentSha256": CONTENT_SHA,
    }


def update_candidate(
    pr: dict[str, Any],
    *,
    effective_impact: str,
    tree_sha: str,
    mode: str = "direct",
    commit_sha: str | None = None,
) -> dict[str, Any]:
    dep = pr["dependencies"][0]
    return {
        "schemaVersion": 1,
        "repository": repository(),
        "base": deepcopy(pr["base"]),
        "groupKey": group_key(pr),
        "sources": [{"number": pr["number"], "headSha": pr["head"]["sha"]}],
        "manifestPaths": list(pr["manifests"]),
        "versions": [
            {
                "name": dep["name"],
                "ecosystem": dep["ecosystem"],
                "from": dep["fromVersion"],
                "to": dep["toVersion"],
                "impact": dep["impact"],
                "prerelease": dep["prerelease"],
            }
        ],
        "additionalDependencies": [],
        "observedAggregateImpact": pr["observedAggregateImpact"],
        "effectiveImpact": effective_impact,
        "impactRationale": "Derived from the version transition.",
        "decision": "update",
        "closureReason": None,
        "parentPlanDigest": None,
        "stabilityEvidence": [
            release_evidence(
                executor._release_subject(
                    {
                        "name": dep["name"],
                        "ecosystem": dep["ecosystem"],
                        "to": dep["toVersion"],
                    }
                )
            )
        ],
        "closureEvidence": [],
        "mode": mode,
        "targetPrNumber": pr["number"] if mode == "direct" else None,
        "commitSha": commit_sha or pr["head"]["sha"],
        "treeSha": tree_sha,
        "validation": [
            {
                "command": "pnpm -C frontend verify",
                "exitCode": 0,
                "treeSha": tree_sha,
                "finishedAt": NOW,
            }
        ],
    }


def batch_candidate(
    group_prs: list[dict[str, Any]],
    *,
    selected_prs: list[dict[str, Any]] | None = None,
    tree_sha: str = PATCH_TREE_SHA,
    commit_sha: str = PATCH_HEAD_SHA,
) -> dict[str, Any]:
    selected = sorted(selected_prs or group_prs, key=lambda item: item["number"])
    versions = sorted(
        [
            {
                "name": dep["name"],
                "ecosystem": dep["ecosystem"],
                "from": dep["fromVersion"],
                "to": dep["toVersion"],
                "impact": dep["impact"],
                "prerelease": dep["prerelease"],
            }
            for pr in selected
            for dep in pr["dependencies"]
        ],
        key=executor._version_key,
    )
    evidence_subjects = sorted({executor._release_subject(item) for item in versions})
    observed_impact = executor.aggregate_impact(
        [pr["observedAggregateImpact"] for pr in selected]
    )
    return {
        "schemaVersion": 1,
        "repository": repository(),
        "base": deepcopy(group(*group_prs)["base"]),
        "groupKey": group_key(*group_prs),
        "sources": [
            {"number": pr["number"], "headSha": pr["head"]["sha"]} for pr in selected
        ],
        "manifestPaths": sorted({path for pr in selected for path in pr["manifests"]}),
        "versions": versions,
        "additionalDependencies": [],
        "observedAggregateImpact": observed_impact,
        "effectiveImpact": (
            observed_impact if observed_impact in {"patch", "minor"} else "major"
        ),
        "impactRationale": "Derived from all selected stable source transitions.",
        "decision": "update",
        "closureReason": None,
        "parentPlanDigest": None,
        "stabilityEvidence": [
            release_evidence(subject) for subject in evidence_subjects
        ],
        "closureEvidence": [],
        "mode": "replacement",
        "targetPrNumber": None,
        "commitSha": commit_sha,
        "treeSha": tree_sha,
        "validation": [
            {
                "command": "just verify",
                "exitCode": 0,
                "treeSha": tree_sha,
                "finishedAt": NOW,
            }
        ],
    }


def close_candidate(
    pr: dict[str, Any],
    *,
    reason: str,
    evidence: dict[str, Any],
    decision: str = "close-nonapplicable",
    parent_plan_digest: str | None = None,
) -> dict[str, Any]:
    dep = pr["dependencies"][0]
    return {
        "schemaVersion": 1,
        "repository": repository(),
        "base": deepcopy(pr["base"]),
        "groupKey": group_key(pr),
        "sources": [{"number": pr["number"], "headSha": pr["head"]["sha"]}],
        "manifestPaths": list(pr["manifests"]),
        "versions": [
            {
                "name": dep["name"],
                "ecosystem": dep["ecosystem"],
                "from": dep["fromVersion"],
                "to": dep["toVersion"],
                "impact": dep["impact"],
                "prerelease": dep["prerelease"],
            }
        ],
        "additionalDependencies": [],
        "observedAggregateImpact": pr["observedAggregateImpact"],
        "effectiveImpact": "major" if dep["impact"] == "major" else dep["impact"],
        "impactRationale": "Closure is decided before update authorization.",
        "decision": decision,
        "closureReason": reason,
        "parentPlanDigest": parent_plan_digest,
        "stabilityEvidence": [],
        "closureEvidence": [evidence],
        "mode": None,
        "targetPrNumber": None,
        "commitSha": None,
        "treeSha": None,
        "validation": [],
    }


def version_prerelease_evidence(pr: dict[str, Any]) -> dict[str, Any]:
    dep = pr["dependencies"][0]
    return {
        "sourceNumber": pr["number"],
        "predicate": "version-prerelease",
        "subject": dep["name"],
        "observed": dep["toVersion"],
        "url": None,
        "contentSha256": None,
        "replacementPrNumber": None,
        "replacementMergeSha": None,
    }


def human_reviewed_evidence(pr: dict[str, Any]) -> dict[str, Any]:
    dep = pr["dependencies"][0]
    return {
        "sourceNumber": pr["number"],
        "predicate": "human-reviewed",
        "subject": dep["name"],
        "observed": "The supported runtime is incompatible with this release.",
        "url": "https://example.invalid/compatibility",
        "contentSha256": CONTENT_SHA,
        "replacementPrNumber": None,
        "replacementMergeSha": None,
    }


def replacement_merged_evidence(pr: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceNumber": pr["number"],
        "predicate": "replacement-merged",
        "subject": "Replacement PR",
        "observed": "The replacement merged successfully.",
        "url": f"https://github.com/{NAME_WITH_OWNER}/pull/99",
        "contentSha256": None,
        "replacementPrNumber": 99,
        "replacementMergeSha": MERGE_SHA,
    }


def user_decision_evidence(pr: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceNumber": pr["number"],
        "predicate": "user-decision",
        "subject": "Major update decision",
        "observed": "The exact major proposal was declined.",
        "url": None,
        "contentSha256": None,
        "replacementPrNumber": None,
        "replacementMergeSha": None,
    }


def assert_contract_error(
    case: unittest.TestCase,
    callback: Any,
) -> executor.ExecutorError:
    with case.assertRaises(executor.ExecutorError) as raised:
        callback()
    case.assertEqual(raised.exception.exit_code, 4)
    case.assertEqual(raised.exception.code, "CONTRACT")
    return raised.exception


class FixtureBuilderTests(unittest.TestCase):
    """Keep the shared fixtures honest before exercising the executor."""

    def test_group_key__matches_normative_singleton_payload(self) -> None:
        pr = pull_request(
            number=12,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )

        expected = hashlib.sha256(
            (f"v1\n{NAME_WITH_OWNER}\nmain@{BASE_SHA}\n12@{PATCH_HEAD_SHA}\n").encode()
        ).hexdigest()

        self.assertEqual(group_key(pr), expected)

    def test_gh_repo_arg__always_includes_the_verified_host(self) -> None:
        self.assertEqual(executor._gh_repo_arg(repository()), GH_REPO)


class VersionClassificationTests(unittest.TestCase):
    def test_classify_version__supported_version_families(self) -> None:
        cases = [
            ("npm", "1.2.3", "1.2.4", None, ("patch", False)),
            ("npm", "1.2.3", "1.3.0", None, ("minor", False)),
            ("npm", "1.2.3", "2.0.0", None, ("major", False)),
            ("npm", "1.2.3", "2.0.0-rc.1", None, ("major", True)),
            ("uv", "1.2.3", "1.2.3.post1", None, ("patch", False)),
            ("uv", "1.2.3", "1.3.0rc1", None, ("minor", True)),
            (
                "docker",
                "node:24.1.0@sha256:old",
                "node:24.1.0@sha256:new",
                None,
                ("patch", False),
            ),
            (
                "docker",
                "python:3.13-slim-bookworm@sha256:old",
                "python:3.13-slim-bookworm@sha256:new",
                None,
                ("patch", False),
            ),
            (
                "docker",
                "node:2.0.0-rc.1@sha256:old",
                "node:2.0.0-rc.1@sha256:new",
                None,
                ("patch", True),
            ),
            (
                "docker",
                "node:nightly@sha256:old",
                "node:nightly@sha256:new",
                None,
                ("patch", True),
            ),
            (
                "docker",
                "node:latest@sha256:old",
                "node:latest@sha256:new",
                None,
                ("unknown", None),
            ),
            (
                "docker",
                "node:2.0.0-experimental.1@sha256:old",
                "node:2.0.0-experimental.1@sha256:new",
                None,
                ("unknown", None),
            ),
            ("github-actions", "v4.0.0", "v4.1.0", None, ("minor", False)),
            (
                "github-actions",
                "8" * 40,
                "9" * 40,
                "version-update:semver-patch",
                ("patch", False),
            ),
        ]

        for ecosystem, old, new, raw_type, expected in cases:
            with self.subTest(ecosystem=ecosystem, old=old, new=new):
                self.assertEqual(
                    executor.classify_version(ecosystem, old, new, raw_type),
                    expected,
                )

    def test_classify_version__uncertain_versions_are_not_downgraded(self) -> None:
        cases = [
            ("npm", "2026.01", "rolling"),
            ("uv", "1!2.0.0", "1!2.0.1"),
            ("uv", "1.0.0", "1.0.0+local"),
            ("unknown", "one", "two"),
        ]

        for ecosystem, old, new in cases:
            with self.subTest(ecosystem=ecosystem, old=old, new=new):
                impact, prerelease = executor.classify_version(ecosystem, old, new)
                self.assertIn(impact, {"non-semver", "unknown"})
                self.assertIsNone(prerelease)


class DependencyParsingTests(unittest.TestCase):
    def test_trusted_body_surface__preserves_only_separated_top_level_text(
        self,
    ) -> None:
        body = (
            "before<DETAILS open><details>nested</details>hidden</DETAILS>after\n"
            '<details>first</details><details class="notes">second</details>end'
        )

        surface, balanced = executor._trusted_body_surface(body)

        self.assertTrue(balanced)
        self.assertEqual(surface, "before\nafter\n\n\nend")

    def test_trusted_body_surface__rejects_unbalanced_tags(self) -> None:
        for body in ("before<details>hidden", "before</details>after"):
            with self.subTest(body=body):
                self.assertEqual(executor._trusted_body_surface(body), ("", False))

    def test_parse_dependencies__ignores_upstream_bumps_in_details(self) -> None:
        body = """Bumps [axios](https://example.test/axios) from 1.18.1 to 1.19.0.
<details>
<summary>Commits</summary>
bump actions/setup-node from 6.4.0 to 7.0.0
</details>
"""

        dependencies = executor._parse_dependencies(
            "Bump axios from 1.18.1 to 1.19.0", body, "npm", "dependabot/axios"
        )

        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0]["name"], "axios")
        self.assertEqual(dependencies[0]["fromVersion"], "1.18.1")
        self.assertEqual(dependencies[0]["toVersion"], "1.19.0")
        self.assertEqual(dependencies[0]["impact"], "minor")

    def test_parse_dependencies__parses_grouped_updates_around_details(self) -> None:
        body = """Bumps [react](https://example.test/react) and [@types/react](https://example.test/types). These dependencies needed to be updated together.
Updates `react` from 19.2.7 to 19.2.8
<details><summary>Release notes</summary>hidden</details>
Updates `@types/react` from 19.2.17 to 19.2.18
<details>Updates `angular` from 20.0.0 to 21.0.0</details>
"""

        dependencies = executor._parse_dependencies(
            "Bump react and @types/react in /docs",
            body,
            "npm",
            "dependabot/npm_and_yarn/docs/multi",
        )

        self.assertEqual(
            [(item["name"], item["impact"]) for item in dependencies],
            [("@types/react", "patch"), ("react", "patch")],
        )

    def test_parse_dependencies__does_not_join_fragments_across_details(self) -> None:
        body = "Updates `invented` from 1<details>upstream</details> to 2"

        dependencies = executor._parse_dependencies(
            "Bump grouped dependencies", body, "npm", "dependabot/multi"
        )

        self.assertEqual(len(dependencies), 1)
        self.assertIsNone(dependencies[0]["fromVersion"])
        self.assertIsNone(dependencies[0]["toVersion"])

    def test_parse_dependencies__falls_back_to_title_for_unbalanced_body(self) -> None:
        dependencies = executor._parse_dependencies(
            "Bump axios from 1.18.1 to 1.19.0",
            "Bumps [wrong](https://example.test) from 1.0.0 to 2.0.0<details>",
            "npm",
            "dependabot/axios",
        )

        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0]["name"], "axios")
        self.assertEqual(dependencies[0]["impact"], "minor")

    def test_parse_dependencies__conflicting_identity_discards_body(self) -> None:
        body = """Updates `React` from 19.2.7 to 19.2.8
Updates `react` from 19.2.7 to 20.0.0
"""

        dependencies = executor._parse_dependencies(
            "Bump grouped dependencies", body, "npm", "dependabot/multi"
        )

        self.assertEqual(len(dependencies), 1)
        self.assertIsNone(dependencies[0]["fromVersion"])
        self.assertIsNone(dependencies[0]["toVersion"])

    def test_parse_dependencies__deduplicates_equivalent_names_deterministically(
        self,
    ) -> None:
        body = """Updates `Foo.Bar` from 1.0.0 to 1.1.0
Updates `foo_bar` from 1.0.0 to 1.1.0
"""

        dependencies = executor._parse_dependencies(
            "Bump grouped dependencies", body, "uv", "dependabot/uv/multi"
        )

        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0]["name"], "Foo.Bar")
        self.assertEqual(dependencies[0]["impact"], "minor")

    def test_parse_dependencies__raw_semver_signal_is_unique_and_singleton_only(
        self,
    ) -> None:
        old_sha = "8" * 40
        new_sha = "9" * 40
        single = executor._parse_dependencies(
            f"Bump actions/checkout from {old_sha} to {new_sha}",
            (
                f"Bumps [actions/checkout](https://example.test) from {old_sha} "
                f"to {new_sha}\nversion-update:semver-patch\n"
                "<details>version-update:semver-major</details>"
            ),
            "github-actions",
            "dependabot/github_actions/checkout",
        )
        conflicting = executor._parse_dependencies(
            f"Bump actions/checkout from {old_sha} to {new_sha}",
            (
                f"Bumps [actions/checkout](https://example.test) from {old_sha} "
                f"to {new_sha}\nversion-update:semver-patch\n"
                "version-update:semver-minor"
            ),
            "github-actions",
            "dependabot/github_actions/checkout",
        )
        grouped = executor._parse_dependencies(
            "Bump action group",
            (
                f"Updates `actions/checkout` from {old_sha} to {new_sha}\n"
                f"Updates `actions/setup-node` from {old_sha} to {new_sha}\n"
                "version-update:semver-patch"
            ),
            "github-actions",
            "dependabot/github_actions/group",
        )

        self.assertEqual(single[0]["rawUpdateType"], "version-update:semver-patch")
        self.assertEqual(single[0]["impact"], "patch")
        self.assertIsNone(conflicting[0]["rawUpdateType"])
        self.assertEqual(conflicting[0]["impact"], "unknown")
        self.assertTrue(all(item["rawUpdateType"] is None for item in grouped))
        self.assertTrue(all(item["impact"] == "unknown" for item in grouped))


class InspectTests(unittest.TestCase):
    def test_inspect_repository__fatal_git_error_returns_unplanable_envelope(
        self,
    ) -> None:
        runner = FakeRunner(executor.CommandResult)
        runner.expect(
            ["git", "rev-parse", "--show-toplevel"],
            returncode=128,
            stderr="not a git repository",
        )

        result = executor.inspect_repository(REPO_ROOT, now=NOW, runner=runner)

        self.assertFalse(result["complete"])
        self.assertIsNone(result["repository"])
        self.assertEqual(result["pullRequests"], [])
        self.assertEqual(result["overlaps"], [])
        self.assertEqual(result["groups"], [])
        self.assertEqual(result["errors"][0]["code"], "REPO_MISMATCH")
        self.assertEqual(runner.mutating_calls, [])
        runner.assert_exhausted()

    def test_non_default_base_api_failure_is_reported_as_incomplete_data(self) -> None:
        pr = pull_request(
            number=14,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )
        pr["base"]["ref"] = "maintenance"
        errors: list[dict[str, Any]] = []

        with mock.patch.object(
            executor,
            "_current_ref_sha",
            side_effect=executor.ExecutorError(
                executor.EXIT_INCOMPLETE,
                "API",
                "maintenance branch lookup failed",
            ),
        ):
            branch_shas = executor._resolve_group_branch_shas(
                [pr], repository(), FakeRunner(executor.CommandResult), errors
            )

        self.assertEqual(branch_shas, {})
        self.assertEqual(
            errors,
            [
                {
                    "code": "API",
                    "message": (
                        "Could not resolve base branch maintenance: "
                        "maintenance branch lookup failed"
                    ),
                    "prNumber": 14,
                    "transient": True,
                }
            ],
        )

    def test_inspect_repository__shared_lockfile_keeps_singleton_groups(self) -> None:
        runner = FakeRunner(executor.CommandResult)
        runner.expect(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=f"{REPO_ROOT}\n",
        )
        runner.expect(
            ["git", "remote", "get-url", "origin"],
            stdout=f"https://github.com/{NAME_WITH_OWNER}.git\n",
        )
        runner.expect(
            ["git", "remote", "get-url", "--push", "origin"],
            stdout=f"git@github.com:{NAME_WITH_OWNER}.git\n",
        )
        runner.expect(["gh", "auth", "status", "--hostname", "github.com"])
        runner.expect(
            [
                "gh",
                "repo",
                "view",
                GH_REPO,
                "--json",
                "nameWithOwner,isFork,parent,defaultBranchRef",
            ],
            stdout=json.dumps(
                {
                    "nameWithOwner": NAME_WITH_OWNER,
                    "isFork": False,
                    "parent": None,
                    "defaultBranchRef": {"name": "main"},
                }
            ),
        )
        runner.expect(
            ["gh", "api", "--hostname", "github.com", "--method", "GET", "user"],
            stdout=json.dumps({"login": "automation-user"}),
        )
        runner.expect(
            [
                "gh",
                "api",
                "--hostname",
                "github.com",
                "--method",
                "GET",
                f"repos/{NAME_WITH_OWNER}/git/ref/heads/main",
            ],
            stdout=json.dumps({"object": {"sha": BASE_SHA}}),
        )
        raw_prs = [
            {
                "number": 12,
                "html_url": f"https://github.com/{NAME_WITH_OWNER}/pull/12",
                "title": "Bump react from 19.1.0 to 19.1.1",
                "body": "Bumps [react](https://npmjs.com/react) from 19.1.0 to 19.1.1.",
                "user": {"login": "dependabot[bot]", "type": "Bot"},
                "base": {
                    "repo": {"full_name": NAME_WITH_OWNER},
                    "ref": "main",
                    "sha": BASE_SHA,
                },
                "head": {
                    "repo": {"full_name": NAME_WITH_OWNER},
                    "ref": "dependabot/npm_and_yarn/react-19.1.1",
                    "sha": PATCH_HEAD_SHA,
                },
                "maintainer_can_modify": True,
                "labels": [],
            },
            {
                "number": 13,
                "html_url": f"https://github.com/{NAME_WITH_OWNER}/pull/13",
                "title": "Bump next from 15.4.0 to 16.0.0",
                "body": "Bumps [next](https://npmjs.com/next) from 15.4.0 to 16.0.0.",
                "user": {"login": "dependabot[bot]", "type": "Bot"},
                "base": {
                    "repo": {"full_name": NAME_WITH_OWNER},
                    "ref": "main",
                    "sha": BASE_SHA,
                },
                "head": {
                    "repo": {"full_name": NAME_WITH_OWNER},
                    "ref": "dependabot/npm_and_yarn/next-16.0.0",
                    "sha": MAJOR_HEAD_SHA,
                },
                "maintainer_can_modify": True,
                "labels": [],
            },
        ]
        runner.expect(
            [
                "gh",
                "api",
                "--hostname",
                "github.com",
                "--method",
                "GET",
                f"repos/{NAME_WITH_OWNER}/pulls?state=open&per_page=100&page=1",
            ],
            stdout=json.dumps(raw_prs),
        )
        files = [
            {"filename": "frontend/package.json"},
            {"filename": "frontend/pnpm-lock.yaml"},
        ]
        for number in (12, 13):
            runner.expect(
                [
                    "gh",
                    "api",
                    "--hostname",
                    "github.com",
                    "--method",
                    "GET",
                    f"repos/{NAME_WITH_OWNER}/pulls/{number}/files?per_page=100&page=1",
                ],
                stdout=json.dumps(files),
            )

        result = executor.inspect_repository(REPO_ROOT, now=NOW, runner=runner)

        self.assertTrue(result["complete"])
        self.assertEqual(
            sorted(item["prNumbers"] for item in result["groups"]),
            [[12], [13]],
        )
        lock_overlap = next(
            item for item in result["overlaps"] if item["kind"] == "lockfile"
        )
        self.assertEqual(lock_overlap["prNumbers"], [12, 13])
        self.assertEqual(
            [item["observedAggregateImpact"] for item in result["pullRequests"]],
            ["patch", "major"],
        )
        self.assertEqual(runner.mutating_calls, [])
        runner.assert_exhausted()


class BatchResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.npm_pr = pull_request(
            number=20,
            head_sha="8" * 40,
            dependency_value=dependency(
                name="react",
                from_version="19.2.7",
                to_version="19.2.8",
                impact="patch",
            ),
        )
        self.uv_pr = pull_request(
            number=21,
            head_sha="9" * 40,
            dependency_value=dependency(
                name="vulture",
                from_version="2.14",
                to_version="2.16",
                impact="minor",
                ecosystem="uv",
            ),
            manifest="backend/pyproject.toml",
            lockfile="backend/uv.lock",
        )

    def test_inventory_groups_stable_sources_by_current_base_ref(self) -> None:
        self.uv_pr["base"]["sha"] = "a" * 40
        major = pull_request(
            number=22,
            head_sha="b" * 40,
            dependency_value=dependency(
                name="next",
                from_version="15.4.0",
                to_version="16.0.0",
                impact="major",
            ),
        )
        prerelease = pull_request(
            number=23,
            head_sha="c" * 40,
            dependency_value=dependency(
                name="vite",
                from_version="8.2.1",
                to_version="8.3.0-rc.1",
                impact="minor",
                prerelease=True,
            ),
        )
        parser_error = pull_request(
            number=24,
            head_sha="d" * 40,
            dependency_value=dependency(
                name="axios",
                from_version="1.19.0",
                to_version="1.19.1",
                impact="patch",
            ),
        )

        groups = executor._build_inventory_groups(
            [self.npm_pr, self.uv_pr, major, prerelease, parser_error],
            {parser_error["number"]},
            {(NAME_WITH_OWNER, "main"): BASE_SHA},
        )

        self.assertEqual(
            sorted(item["prNumbers"] for item in groups),
            [[20, 21], [22], [23], [24]],
        )
        batch = next(item for item in groups if item["prNumbers"] == [20, 21])
        self.assertEqual(batch["base"]["sha"], BASE_SHA)
        self.assertEqual(batch["observedAggregateImpact"], "minor")

    def test_build_plan_consolidates_sources_and_allows_safe_subset(self) -> None:
        snapshot = inventory(self.npm_pr, self.uv_pr)
        full = batch_candidate([self.npm_pr, self.uv_pr])

        plan = executor.build_plan(snapshot, full, created_at=NOW)

        self.assertEqual(plan["approval"]["kind"], "none")
        self.assertEqual(
            plan["operations"][-2:],
            [
                {
                    "name": "close-source",
                    "target": f"source:20@{self.npm_pr['head']['sha']}",
                },
                {
                    "name": "close-source",
                    "target": f"source:21@{self.uv_pr['head']['sha']}",
                },
            ],
        )
        executor._verify_plan_structure(plan)

        subset = batch_candidate([self.npm_pr, self.uv_pr], selected_prs=[self.npm_pr])
        subset_plan = executor.build_plan(snapshot, subset, created_at=NOW)
        self.assertEqual(len(subset_plan["candidate"]["sources"]), 1)
        self.assertEqual(
            subset_plan["candidate"]["manifestPaths"], ["frontend/package.json"]
        )

    def test_build_plan_rejects_direct_batch_and_incomplete_evidence(self) -> None:
        snapshot = inventory(self.npm_pr, self.uv_pr)
        direct = batch_candidate([self.npm_pr, self.uv_pr])
        direct["mode"] = "direct"
        direct["targetPrNumber"] = self.npm_pr["number"]
        direct["commitSha"] = self.npm_pr["head"]["sha"]

        assert_contract_error(
            self, lambda: executor.build_plan(snapshot, direct, created_at=NOW)
        )

        missing = batch_candidate([self.npm_pr, self.uv_pr])
        missing["stabilityEvidence"] = missing["stabilityEvidence"][:1]
        assert_contract_error(
            self, lambda: executor.build_plan(snapshot, missing, created_at=NOW)
        )

    def test_release_evidence_requires_truthful_structured_summary(self) -> None:
        candidate = batch_candidate([self.npm_pr, self.uv_pr])
        candidate["stabilityEvidence"][0]["summary"] = (
            "breaking=applicable; adaptation=not-required"
        )

        assert_contract_error(
            self,
            lambda: executor.build_plan(
                inventory(self.npm_pr, self.uv_pr), candidate, created_at=NOW
            ),
        )

        evidence = deepcopy(candidate["stabilityEvidence"][0])
        evidence["summary"] = "breaking=not-applicable; adaptation=not-required"
        self.assertEqual(
            executor._validate_release_evidence([evidence], structured_summary=True),
            [evidence],
        )
        evidence["summary"] = "breaking=none; adaptation=updated configuration"
        self.assertEqual(
            executor._validate_release_evidence([evidence], structured_summary=True),
            [evidence],
        )

    def test_singleton_v1_keeps_legacy_release_summary_compatibility(self) -> None:
        candidate = update_candidate(
            self.npm_pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
        )
        candidate["stabilityEvidence"][0]["summary"] = (
            "Stable patch release with no migration required."
        )
        candidate["stabilityEvidence"][0]["subject"] = "react"

        plan = executor.build_plan(inventory(self.npm_pr), candidate, created_at=NOW)

        executor._verify_plan_structure(plan)

    def test_plan_rejects_conflicting_targets_in_same_manifest(self) -> None:
        other = pull_request(
            number=25,
            head_sha="e" * 40,
            dependency_value=dependency(
                name="React",
                from_version="19.2.7",
                to_version="19.3.0",
                impact="minor",
            ),
        )
        candidate = batch_candidate([self.npm_pr, other])

        assert_contract_error(
            self,
            lambda: executor.build_plan(
                inventory(self.npm_pr, other), candidate, created_at=NOW
            ),
        )

    def test_live_revalidation_uses_each_source_ecosystem(self) -> None:
        action = pull_request(
            number=26,
            head_sha="f" * 40,
            dependency_value=dependency(
                name="actions/checkout",
                from_version="a" * 40,
                to_version="b" * 40,
                impact="patch",
                ecosystem="github-actions",
            ),
            manifest=".github/workflows/ci.yml",
            lockfile=".github/dependabot.yml",
        )
        action["body"] += "\nversion-update:semver-patch"
        candidate = batch_candidate([self.npm_pr, self.uv_pr, action])

        executor._validate_live_sources(
            [
                (self.npm_pr, self.npm_pr["manifests"]),
                (self.uv_pr, self.uv_pr["manifests"]),
                (action, action["manifests"]),
            ],
            candidate,
        )

    def test_source_revalidation_ignores_historical_base_sha(self) -> None:
        candidate = batch_candidate([self.npm_pr, self.uv_pr])
        live = {
            "head": {"sha": self.npm_pr["head"]["sha"]},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
                "sha": "a" * 40,
            },
            "user": {"login": "dependabot[bot]", "type": "Bot"},
        }

        executor._verify_source_pr(live, candidate, candidate["sources"][0])

    def test_state_tracks_partial_and_complete_source_closure(self) -> None:
        plan = executor.build_plan(
            inventory(self.npm_pr, self.uv_pr),
            batch_candidate([self.npm_pr, self.uv_pr]),
            created_at=NOW,
        )
        state = executor._new_state(plan, NOW)
        state["replacement"] = {
            "number": 99,
            "url": f"https://github.com/{NAME_WITH_OWNER}/pull/99",
            "headSha": plan["candidate"]["commitSha"],
        }
        state["mergeCommitSha"] = MERGE_SHA
        state["status"] = "merged"
        state["sources"][0]["status"] = "closed"

        executor._validate_state_shape(deepcopy(state))
        state["status"] = "sources-closed"
        assert_contract_error(self, lambda: executor._validate_state_shape(state))
        state["sources"][1]["status"] = "closed"
        executor._validate_state_shape(state)

    def test_replacement_marker_binds_plan_tree_and_every_source(self) -> None:
        plan = executor.build_plan(
            inventory(self.npm_pr, self.uv_pr),
            batch_candidate([self.npm_pr, self.uv_pr]),
            created_at=NOW,
        )

        marker = executor._replacement_marker(plan)

        self.assertIn(f"plan={plan['planDigest']}", marker)
        self.assertIn(f"tree={plan['candidate']['treeSha']}", marker)
        for source in plan["candidate"]["sources"]:
            self.assertIn(f"source={source['number']}@{source['headSha']}", marker)

    def test_publish_migrates_legacy_singleton_replacement_marker(self) -> None:
        candidate = update_candidate(
            self.npm_pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
            mode="replacement",
        )
        plan = executor.build_plan(inventory(self.npm_pr), candidate, created_at=NOW)
        legacy_marker = executor._legacy_replacement_marker(plan)
        self.assertIsNotNone(legacy_marker)
        remote_pr = {
            "number": 99,
            "state": "open",
            "merged_at": None,
            "html_url": f"https://github.com/{NAME_WITH_OWNER}/pull/99",
            "body": legacy_marker,
            "user": {"login": "automation-user", "type": "User"},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
                "sha": BASE_SHA,
            },
            "head": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": plan["destinationBranch"],
                "sha": candidate["commitSha"],
            },
        }
        runner = FakeRunner(executor.CommandResult)

        def edit_body(call: Any) -> object:
            remote_pr["body"] = call.args[call.args.index("--body") + 1]
            return runner.result()

        runner.when(
            lambda call: call.args[:4] == ("gh", "pr", "edit", "99"),
            edit_body,
            description="migrate legacy replacement body",
            times=1,
        )
        state = executor._new_state(plan, NOW)
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                executor,
                "_page_api",
                side_effect=lambda *_args, **_kwargs: [deepcopy(remote_pr)],
            ),
            mock.patch.object(
                executor,
                "_current_ref_sha",
                return_value=candidate["commitSha"],
            ),
        ):
            executor._publish_replacement(
                runner,
                executor._Mutations(runner, False),
                plan,
                state,
                Path(temporary),
                Path(temporary) / "state.json",
                NOW,
            )

        self.assertEqual(remote_pr["body"], executor._replacement_body(plan))
        self.assertEqual(state["status"], "published")
        self.assertEqual(state["replacement"]["number"], 99)
        runner.assert_exhausted()

    def test_legacy_singleton_marker_still_proves_merged_replacement(self) -> None:
        evidence = replacement_merged_evidence(self.npm_pr)
        candidate = close_candidate(
            self.npm_pr,
            reason="duplicate-merged",
            evidence=evidence,
        )
        source = candidate["sources"][0]
        replacement = {
            "merged_at": NOW,
            "merge_commit_sha": MERGE_SHA,
            "html_url": evidence["url"],
            "body": (
                "<!-- resolve-dependabot-prs:v1 key=aaaaaaaaaaaa "
                f"source={source['number']}@{source['headSha']} -->"
            ),
            "user": {"login": "automation-user", "type": "User"},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
            },
        }

        with mock.patch.object(executor, "_get_pr", return_value=replacement):
            executor._validate_closure_predicate(
                FakeRunner(executor.CommandResult), candidate, evidence
            )

    def test_finalize_rejects_open_legacy_singleton_marker(self) -> None:
        candidate = update_candidate(
            self.npm_pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
            mode="replacement",
        )
        plan = executor.build_plan(inventory(self.npm_pr), candidate, created_at=NOW)
        replacement = {
            "number": 99,
            "state": "open",
            "merged_at": None,
            "html_url": f"https://github.com/{NAME_WITH_OWNER}/pull/99",
            "body": executor._legacy_replacement_marker(plan),
            "user": {"login": "automation-user", "type": "User"},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
                "sha": BASE_SHA,
            },
            "head": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": plan["destinationBranch"],
                "sha": candidate["commitSha"],
            },
        }
        state = executor._new_state(plan, NOW)
        state["status"] = "published"
        state["replacement"] = {
            "number": 99,
            "url": replacement["html_url"],
            "headSha": candidate["commitSha"],
        }

        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                executor, "_find_replacements", return_value=[replacement]
            ),
            self.assertRaises(executor.ExecutorError) as caught,
        ):
            executor._finalize(
                FakeRunner(executor.CommandResult),
                executor._Mutations(FakeRunner(executor.CommandResult), False),
                plan,
                state,
                Path(temporary) / "state.json",
                NOW,
            )

        self.assertEqual(caught.exception.code, "AMBIGUOUS_REMOTE")

    def test_replacement_lookup_rejects_same_key_with_different_sources(self) -> None:
        plan = executor.build_plan(
            inventory(self.npm_pr, self.uv_pr),
            batch_candidate([self.npm_pr, self.uv_pr]),
            created_at=NOW,
        )
        omitted = plan["candidate"]["sources"][1]
        stale_body = executor._replacement_body(plan).replace(
            (
                "<!-- resolve-dependabot-prs:v1 "
                f"source={omitted['number']}@{omitted['headSha']} "
                f"plan={plan['planDigest']} tree={plan['candidate']['treeSha']} -->\n"
            ),
            "",
        )

        with mock.patch.object(
            executor,
            "_page_api",
            return_value=[{"number": 99, "body": stale_body}],
        ):
            with self.assertRaises(executor.ExecutorError) as caught:
                executor._find_replacements(FakeRunner(executor.CommandResult), plan)

        self.assertEqual(caught.exception.code, "AMBIGUOUS_REMOTE")

    def test_pending_batch_sources_must_remain_open_and_unmerged(self) -> None:
        candidate = batch_candidate([self.npm_pr, self.uv_pr])
        source = candidate["sources"][0]
        live = {
            "state": "closed",
            "merged_at": None,
            "head": {"sha": source["headSha"]},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
            },
            "user": {"login": "dependabot[bot]", "type": "Bot"},
        }

        with self.assertRaises(executor.ExecutorError) as closed:
            executor._verify_source_pr(live, candidate, source, require_open=True)
        self.assertEqual(closed.exception.code, "AMBIGUOUS_REMOTE")

        live["state"] = "open"
        live["merged_at"] = NOW
        with self.assertRaises(executor.ExecutorError) as merged:
            executor._verify_source_pr(live, candidate, source, require_open=True)
        self.assertEqual(merged.exception.code, "AMBIGUOUS_REMOTE")

    def test_multi_source_replacement_never_enters_merge_queue(self) -> None:
        candidate = batch_candidate([self.npm_pr, self.uv_pr])
        plan = executor.build_plan(
            inventory(self.npm_pr, self.uv_pr), candidate, created_at=NOW
        )
        state = executor._new_state(plan, NOW)
        replacement = {
            "state": "open",
            "merged_at": None,
            "head": {"sha": candidate["commitSha"]},
        }
        pre_merge_check = mock.Mock()
        runner = FakeRunner(executor.CommandResult)

        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(executor, "_get_pr", return_value=replacement),
            mock.patch.object(
                executor,
                "_protection_requirements",
                return_value=(set(), 0, True),
            ),
            self.assertRaises(executor.ExecutorError) as caught,
        ):
            executor._merge_pr(
                runner,
                executor._Mutations(runner, False),
                plan,
                state,
                99,
                candidate["commitSha"],
                "automation-user",
                Path(temporary) / "state.json",
                NOW,
                pre_merge_check=pre_merge_check,
            )

        self.assertEqual(caught.exception.code, "PROTECTION")
        pre_merge_check.assert_not_called()
        self.assertEqual(runner.mutating_calls, [])

    def test_closed_source_without_executor_marker_is_never_claimed(self) -> None:
        plan = executor.build_plan(
            inventory(self.npm_pr, self.uv_pr),
            batch_candidate([self.npm_pr, self.uv_pr]),
            created_at=NOW,
        )
        state = executor._new_state(plan, NOW)
        state["status"] = "merged"
        state["mergeCommitSha"] = MERGE_SHA
        source = plan["candidate"]["sources"][0]
        live = {
            "state": "closed",
            "merged_at": None,
            "head": {"sha": source["headSha"]},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
            },
            "user": {"login": "dependabot[bot]", "type": "Bot"},
        }
        runner = FakeRunner(executor.CommandResult)

        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(executor, "_get_pr", return_value=live),
            mock.patch.object(executor, "_comments", return_value=[]),
            self.assertRaises(executor.ExecutorError) as caught,
        ):
            executor._close_one_source(
                runner,
                executor._Mutations(runner, False),
                plan,
                state,
                source,
                "expected marker",
                allow_preclosed=True,
                state_path=Path(temporary) / "state.json",
                now=NOW,
            )

        self.assertEqual(caught.exception.code, "AMBIGUOUS_REMOTE")
        self.assertEqual(runner.mutating_calls, [])

    def test_publish_fast_forward_updates_existing_replacement_body(self) -> None:
        first_candidate = batch_candidate(
            [self.npm_pr, self.uv_pr],
            commit_sha="a" * 40,
            tree_sha="b" * 40,
        )
        first_plan = executor.build_plan(
            inventory(self.npm_pr, self.uv_pr), first_candidate, created_at=NOW
        )
        next_candidate = batch_candidate(
            [self.npm_pr, self.uv_pr],
            commit_sha="c" * 40,
            tree_sha="d" * 40,
        )
        next_plan = executor.build_plan(
            inventory(self.npm_pr, self.uv_pr), next_candidate, created_at=LATER
        )
        self.assertEqual(first_plan["sourceHash"], next_plan["sourceHash"])
        old_pr = {
            "number": 99,
            "state": "open",
            "merged_at": None,
            "html_url": f"https://github.com/{NAME_WITH_OWNER}/pull/99",
            "body": executor._replacement_body(first_plan),
            "user": {"login": "automation-user", "type": "User"},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
                "sha": BASE_SHA,
            },
            "head": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": next_plan["destinationBranch"],
                "sha": first_candidate["commitSha"],
            },
        }
        pushed_pr = deepcopy(old_pr)
        pushed_pr["head"]["sha"] = next_candidate["commitSha"]
        current_pr = deepcopy(pushed_pr)
        current_pr["body"] = executor._replacement_body(next_plan)
        runner = FakeRunner(executor.CommandResult)
        runner.expect(
            ["git", "cat-file", "-e", f"{first_candidate['commitSha']}^{{commit}}"]
        )
        runner.expect(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                first_candidate["commitSha"],
                next_candidate["commitSha"],
            ]
        )
        runner.expect(
            [
                "git",
                "push",
                "origin",
                f"{next_candidate['commitSha']}:refs/heads/{next_plan['destinationBranch']}",
            ],
            mutating=True,
        )
        runner.expect(
            [
                "gh",
                "pr",
                "edit",
                "99",
                "--repo",
                GH_REPO,
                "--body",
                executor._replacement_body(next_plan),
            ],
            mutating=True,
        )
        state = executor._new_state(next_plan, NOW)
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                executor,
                "_find_replacements",
                side_effect=[[old_pr], [pushed_pr], [current_pr]],
            ),
            mock.patch.object(
                executor,
                "_current_ref_sha",
                side_effect=[first_candidate["commitSha"], next_candidate["commitSha"]],
            ),
        ):
            executor._publish_replacement(
                runner,
                executor._Mutations(runner, False),
                next_plan,
                state,
                Path(temporary),
                Path(temporary) / "state.json",
                NOW,
            )

        self.assertEqual(state["status"], "published")
        self.assertEqual(state["replacement"]["headSha"], next_candidate["commitSha"])
        runner.assert_exhausted()

    def test_finalize_closes_every_source_only_after_confirmed_batch_merge(
        self,
    ) -> None:
        candidate = batch_candidate([self.npm_pr, self.uv_pr])
        plan = executor.build_plan(
            inventory(self.npm_pr, self.uv_pr), candidate, created_at=NOW
        )
        state = executor._new_state(plan, NOW)
        state["status"] = "published"
        state["replacement"] = {
            "number": 99,
            "url": f"https://github.com/{NAME_WITH_OWNER}/pull/99",
            "headSha": candidate["commitSha"],
        }
        replacement = {
            "number": 99,
            "state": "closed",
            "merged_at": NOW,
            "merge_commit_sha": MERGE_SHA,
            "html_url": f"https://github.com/{NAME_WITH_OWNER}/pull/99",
            "body": executor._replacement_body(plan),
            "user": {"login": "automation-user", "type": "User"},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
                "sha": MERGE_SHA,
            },
            "head": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": plan["destinationBranch"],
                "sha": candidate["commitSha"],
            },
        }
        live_prs = []
        for pr in (self.npm_pr, self.uv_pr):
            live = deepcopy(pr)
            live["state"] = "open"
            live["merged_at"] = None
            live["user"] = {"login": "dependabot[bot]", "type": "Bot"}
            live["base"] = {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
                "sha": "a" * 40,
            }
            live_prs.append(live)
        closed: list[int] = []

        def close_source(
            _runner: Any,
            _mutations: Any,
            _plan: Any,
            observed_state: dict[str, Any],
            source: dict[str, Any],
            _marker: str,
            **_kwargs: Any,
        ) -> None:
            self.assertEqual(observed_state["status"], "merged")
            closed.append(source["number"])
            next(
                item
                for item in observed_state["sources"]
                if item["number"] == source["number"]
            )["status"] = "closed"

        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                executor, "_find_replacements", return_value=[replacement]
            ),
            mock.patch.object(executor, "_get_pr", side_effect=live_prs),
            mock.patch.object(
                executor,
                "_live_source_manifests",
                side_effect=[self.npm_pr["manifests"], self.uv_pr["manifests"]],
            ),
            mock.patch.object(executor, "_close_one_source", side_effect=close_source),
        ):
            executor._finalize(
                FakeRunner(executor.CommandResult),
                executor._Mutations(FakeRunner(executor.CommandResult), False),
                plan,
                state,
                Path(temporary) / "state.json",
                NOW,
            )

        self.assertEqual(closed, [20, 21])
        self.assertEqual(state["status"], "sources-closed")
        self.assertTrue(all(item["status"] == "closed" for item in state["sources"]))


class CanonicalPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patch_pr = pull_request(
            number=12,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )
        self.major_pr = pull_request(
            number=13,
            head_sha=MAJOR_HEAD_SHA,
            dependency_value=dependency(
                name="next",
                from_version="15.4.0",
                to_version="16.0.0",
                impact="major",
            ),
        )

    def test_canonical_json__sorts_keys_and_uses_compact_utf8(self) -> None:
        value = {"z": "á", "nested": {"b": 2, "a": 1}}

        serialized = executor.canonical_json(value)

        self.assertEqual(serialized, '{"nested":{"a":1,"b":2},"z":"á"}')
        self.assertEqual(
            executor.canonical_digest(value),
            hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        )

    def test_build_plan__patch_is_autonomous_and_digest_ignores_timestamp(self) -> None:
        snapshot = inventory(self.patch_pr)
        candidate = update_candidate(
            self.patch_pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
        )

        first = executor.build_plan(snapshot, candidate, created_at=NOW)
        second = executor.build_plan(snapshot, candidate, created_at=LATER)

        self.assertEqual(first["planDigest"], second["planDigest"])
        self.assertNotEqual(first["createdAt"], second["createdAt"])
        self.assertIsNone(first["destinationBranch"])
        self.assertEqual(
            first["operations"],
            [
                {
                    "name": "merge",
                    "target": f"source:{self.patch_pr['number']}@{PATCH_HEAD_SHA}",
                }
            ],
        )
        self.assertEqual(
            first["approval"],
            {
                "kind": "none",
                "required": False,
                "approveToken": None,
                "rejectToken": None,
                "closeToken": None,
                "parentPlanDigest": None,
            },
        )

    def test_build_plan__major_tokens_bind_the_exact_plan_digest(self) -> None:
        snapshot = inventory(self.major_pr)
        candidate = update_candidate(
            self.major_pr,
            effective_impact="major",
            tree_sha=MAJOR_TREE_SHA,
        )

        plan = executor.build_plan(snapshot, candidate, created_at=NOW)

        self.assertTrue(plan["approval"]["required"])
        self.assertEqual(plan["approval"]["kind"], "update-major")
        self.assertEqual(
            plan["approval"]["approveToken"],
            f"approve:{plan['planDigest']}",
        )
        self.assertEqual(
            plan["approval"]["rejectToken"],
            f"reject:{plan['planDigest']}",
        )
        changed = deepcopy(candidate)
        changed["impactRationale"] = "A different reviewed rationale."
        changed_plan = executor.build_plan(snapshot, changed, created_at=NOW)
        self.assertNotEqual(plan["planDigest"], changed_plan["planDigest"])

    def test_build_plan__replacement_identity_and_operations_are_deterministic(
        self,
    ) -> None:
        snapshot = inventory(self.patch_pr)
        candidate = update_candidate(
            self.patch_pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
            mode="replacement",
            commit_sha="a" * 40,
        )
        identity = (
            f"v1\n{NAME_WITH_OWNER}\nmain@{BASE_SHA}\n"
            f"frontend/package.json\n12@{PATCH_HEAD_SHA}\n"
        )
        source_hash = hashlib.sha256(identity.encode()).hexdigest()[:12]
        branch = f"automation/dependabot/frontend-package-json-{source_hash}"

        plan = executor.build_plan(snapshot, candidate, created_at=NOW)

        self.assertEqual(plan["sourceHash"], source_hash)
        self.assertEqual(plan["destinationBranch"], branch)
        self.assertEqual(
            plan["operations"],
            [
                {"name": "push", "target": f"branch:{branch}"},
                {"name": "create-replacement", "target": "replacement"},
                {"name": "merge", "target": "replacement"},
                {
                    "name": "close-source",
                    "target": f"source:12@{PATCH_HEAD_SHA}",
                },
            ],
        )

    def test_build_plan__rejects_effective_impact_that_downgrades_major(self) -> None:
        snapshot = inventory(self.major_pr)
        candidate = update_candidate(
            self.major_pr,
            effective_impact="minor",
            tree_sha=MAJOR_TREE_SHA,
        )

        assert_contract_error(
            self,
            lambda: executor.build_plan(snapshot, candidate, created_at=NOW),
        )

    def test_build_plan__rejects_fatal_inventory(self) -> None:
        candidate = update_candidate(
            self.patch_pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
        )

        assert_contract_error(
            self,
            lambda: executor.build_plan(fatal_inventory(), candidate, created_at=NOW),
        )

    def test_build_plan__requires_a_source_from_the_inventory_group(self) -> None:
        snapshot = inventory(self.patch_pr)
        candidate = update_candidate(
            self.patch_pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
        )
        candidate["sources"] = [
            {"number": self.major_pr["number"], "headSha": MAJOR_HEAD_SHA}
        ]

        assert_contract_error(
            self,
            lambda: executor.build_plan(snapshot, candidate, created_at=NOW),
        )

    def test_build_plan__shared_lockfile_major_does_not_gate_patch_group(self) -> None:
        snapshot = inventory(
            self.patch_pr,
            self.major_pr,
            overlaps=[
                {
                    "kind": "lockfile",
                    "key": "frontend/pnpm-lock.yaml",
                    "prNumbers": [12, 13],
                }
            ],
        )
        candidate = update_candidate(
            self.patch_pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
        )

        plan = executor.build_plan(snapshot, candidate, created_at=NOW)

        self.assertEqual(
            sorted(item["prNumbers"] for item in snapshot["groups"]),
            [[12], [13]],
        )
        self.assertFalse(plan["approval"]["required"])
        self.assertEqual(
            plan["candidate"]["sources"],
            [{"number": 12, "headSha": PATCH_HEAD_SHA}],
        )


class ClosureEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prerelease_pr = pull_request(
            number=21,
            head_sha=MAJOR_HEAD_SHA,
            dependency_value=dependency(
                name="next",
                from_version="15.4.0",
                to_version="16.0.0-rc.1",
                impact="major",
                prerelease=True,
            ),
        )

    def test_build_plan__prerelease_close_is_autonomous_before_major_gate(self) -> None:
        snapshot = inventory(self.prerelease_pr)
        candidate = close_candidate(
            self.prerelease_pr,
            reason="prerelease",
            evidence=version_prerelease_evidence(self.prerelease_pr),
        )

        plan = executor.build_plan(snapshot, candidate, created_at=NOW)

        self.assertEqual(plan["approval"]["kind"], "none")
        self.assertFalse(plan["approval"]["required"])
        self.assertEqual(
            plan["operations"],
            [
                {
                    "name": "close-source",
                    "target": f"source:21@{MAJOR_HEAD_SHA}",
                }
            ],
        )

    def test_build_plan__human_reviewed_close_requires_exact_close_token(self) -> None:
        stable_pr = deepcopy(self.prerelease_pr)
        stable_pr["dependencies"][0]["toVersion"] = "16.0.0"
        stable_pr["dependencies"][0]["prerelease"] = False
        candidate = close_candidate(
            stable_pr,
            reason="unsupported-platform",
            evidence=human_reviewed_evidence(stable_pr),
        )

        plan = executor.build_plan(inventory(stable_pr), candidate, created_at=NOW)

        self.assertEqual(plan["approval"]["kind"], "close-reviewed")
        self.assertTrue(plan["approval"]["required"])
        self.assertEqual(
            plan["approval"]["closeToken"],
            f"close:{plan['planDigest']}",
        )

    def test_build_plan__rejects_closure_evidence_for_another_source(self) -> None:
        snapshot = inventory(self.prerelease_pr)
        evidence = version_prerelease_evidence(self.prerelease_pr)
        evidence["sourceNumber"] = 999
        candidate = close_candidate(
            self.prerelease_pr,
            reason="prerelease",
            evidence=evidence,
        )

        assert_contract_error(
            self,
            lambda: executor.build_plan(snapshot, candidate, created_at=NOW),
        )

    def test_build_plan__replacement_close_requires_typed_merge_identity(self) -> None:
        snapshot = inventory(self.prerelease_pr)
        evidence = replacement_merged_evidence(self.prerelease_pr)
        evidence["replacementMergeSha"] = None
        candidate = close_candidate(
            self.prerelease_pr,
            reason="superseded-merged",
            evidence=evidence,
        )

        assert_contract_error(
            self,
            lambda: executor.build_plan(snapshot, candidate, created_at=NOW),
        )

    def test_build_plan__declined_major_uses_parent_digest_reject_token(self) -> None:
        stable_pr = deepcopy(self.prerelease_pr)
        stable_pr["dependencies"][0]["toVersion"] = "16.0.0"
        stable_pr["dependencies"][0]["prerelease"] = False
        snapshot = inventory(stable_pr)
        update = update_candidate(
            stable_pr,
            effective_impact="major",
            tree_sha=MAJOR_TREE_SHA,
        )
        update_plan = executor.build_plan(snapshot, update, created_at=NOW)
        declined = close_candidate(
            stable_pr,
            reason="major-declined",
            evidence=user_decision_evidence(stable_pr),
            decision="close-declined-major",
            parent_plan_digest=update_plan["planDigest"],
        )

        close_plan = executor.build_plan(snapshot, declined, created_at=LATER)

        self.assertEqual(close_plan["approval"]["kind"], "reject-major")
        self.assertEqual(
            close_plan["approval"]["rejectToken"],
            f"reject:{update_plan['planDigest']}",
        )


class ApplyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.state_path = self.root / "state.json"
        self.major_pr = pull_request(
            number=31,
            head_sha=MAJOR_HEAD_SHA,
            dependency_value=dependency(
                name="next",
                from_version="15.4.0",
                to_version="16.0.0",
                impact="major",
            ),
        )
        self.plan = executor.build_plan(
            inventory(self.major_pr),
            update_candidate(
                self.major_pr,
                effective_impact="major",
                tree_sha=MAJOR_TREE_SHA,
            ),
            created_at=NOW,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_apply_plan__major_without_token_stops_before_any_command(self) -> None:
        runner = FakeRunner(executor.CommandResult)

        with self.assertRaises(executor.ExecutorError) as raised:
            executor.apply_plan(
                self.root,
                self.root,
                self.plan,
                self.state_path,
                "publish",
                runner=runner,
                now=NOW,
            )

        self.assertEqual(raised.exception.exit_code, 5)
        self.assertEqual(raised.exception.code, "APPROVAL_REQUIRED")
        self.assertEqual(runner.calls, [])
        self.assertEqual(runner.mutating_calls, [])

    def test_apply_plan__wrong_major_token_stops_before_any_command(self) -> None:
        runner = FakeRunner(executor.CommandResult)

        with self.assertRaises(executor.ExecutorError) as raised:
            executor.apply_plan(
                self.root,
                self.root,
                self.plan,
                self.state_path,
                "publish",
                approval_token=f"approve:{'0' * 64}",
                runner=runner,
                now=NOW,
            )

        self.assertEqual(raised.exception.exit_code, 5)
        self.assertEqual(raised.exception.code, "APPROVAL_REQUIRED")
        self.assertEqual(runner.calls, [])

    def test_apply_plan__confirmed_close_state_prevents_duplicate_mutations(
        self,
    ) -> None:
        prerelease_pr = pull_request(
            number=32,
            head_sha=MAJOR_HEAD_SHA,
            dependency_value=dependency(
                name="next",
                from_version="15.4.0",
                to_version="16.0.0-rc.1",
                impact="major",
                prerelease=True,
            ),
        )
        plan = executor.build_plan(
            inventory(prerelease_pr),
            close_candidate(
                prerelease_pr,
                reason="prerelease",
                evidence=version_prerelease_evidence(prerelease_pr),
            ),
            created_at=NOW,
        )
        remote = {"closed": False, "comments": []}
        runner = FakeRunner(executor.CommandResult)

        def respond(call: Any) -> object:
            args = call.args
            if args == ("git", "rev-parse", "--show-toplevel"):
                return runner.result(stdout=f"{REPO_ROOT}\n")
            if args == ("git", "remote", "get-url", "origin"):
                return runner.result(
                    stdout=f"https://github.com/{NAME_WITH_OWNER}.git\n"
                )
            if args == ("git", "remote", "get-url", "--push", "origin"):
                return runner.result(stdout=f"git@github.com:{NAME_WITH_OWNER}.git\n")
            if args == ("gh", "auth", "status", "--hostname", "github.com"):
                return runner.result()
            if args[:3] == ("gh", "repo", "view"):
                self.assertEqual(args[3], GH_REPO)
                return runner.result(
                    stdout=json.dumps(
                        {
                            "nameWithOwner": NAME_WITH_OWNER,
                            "isFork": False,
                            "parent": None,
                            "defaultBranchRef": {"name": "main"},
                        }
                    )
                )
            if args[:2] == ("gh", "api"):
                endpoint = args[-1]
                if endpoint == "user":
                    return runner.result(
                        stdout=json.dumps({"login": "automation-user"})
                    )
                if endpoint == f"repos/{NAME_WITH_OWNER}/git/ref/heads/main":
                    return runner.result(
                        stdout=json.dumps({"object": {"sha": BASE_SHA}})
                    )
                if endpoint == f"repos/{NAME_WITH_OWNER}/pulls/32":
                    return runner.result(
                        stdout=json.dumps(
                            {
                                "number": 32,
                                "state": "closed" if remote["closed"] else "open",
                                "merged_at": None,
                                "title": prerelease_pr["title"],
                                "body": prerelease_pr["body"],
                                "user": {
                                    "login": "dependabot[bot]",
                                    "type": "Bot",
                                },
                                "base": {
                                    "repo": {"full_name": NAME_WITH_OWNER},
                                    "ref": "main",
                                    "sha": BASE_SHA,
                                },
                                "head": {
                                    "sha": MAJOR_HEAD_SHA,
                                    "ref": prerelease_pr["head"]["ref"],
                                },
                            }
                        )
                    )
                if endpoint == (
                    f"repos/{NAME_WITH_OWNER}/issues/32/comments?per_page=100&page=1"
                ):
                    return runner.result(stdout=json.dumps(remote["comments"]))
            if args[:4] == ("gh", "pr", "comment", "32"):
                marker = args[args.index("--body") + 1]
                remote["comments"].append({"body": marker})
                return runner.result()
            if args[:4] == ("gh", "pr", "close", "32"):
                remote["closed"] = True
                return runner.result()
            raise AssertionError(f"Unexpected stateful command: {' '.join(args)}")

        runner.when(
            lambda _call: True,
            respond,
            description="stateful closure remote",
            times=None,
        )

        preview = executor.apply_plan(
            REPO_ROOT,
            REPO_ROOT,
            plan,
            self.state_path,
            "publish",
            dry_run=True,
            runner=runner,
            now=NOW,
        )
        self.assertTrue(preview.dry_run)
        self.assertEqual(preview.commands[0][:4], ["gh", "pr", "comment", "32"])
        self.assertEqual(runner.mutating_calls, [])
        self.assertFalse(self.state_path.exists())

        first = executor.apply_plan(
            REPO_ROOT,
            REPO_ROOT,
            plan,
            self.state_path,
            "publish",
            runner=runner,
            now=NOW,
        )
        mutations_after_first = list(runner.mutating_calls)
        second = executor.apply_plan(
            REPO_ROOT,
            REPO_ROOT,
            plan,
            self.state_path,
            "publish",
            runner=runner,
            now=LATER,
        )

        self.assertEqual(first.state["status"], "closed")
        self.assertEqual(second.state["status"], "closed")
        self.assertEqual(first.state["sources"][0]["status"], "closed")
        self.assertEqual(len(mutations_after_first), 2)
        self.assertEqual(runner.mutating_calls, mutations_after_first)
        persisted = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted, second.state)


class CliTests(unittest.TestCase):
    def test_main__plan_writes_the_same_json_to_file_and_stdout(self) -> None:
        pr = pull_request(
            number=41,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory_path = root / "inventory.json"
            candidate_path = root / "candidate.json"
            output_path = root / "plan.json"
            inventory_path.write_text(json.dumps(inventory(pr)), encoding="utf-8")
            candidate_path.write_text(
                json.dumps(
                    update_candidate(
                        pr,
                        effective_impact="patch",
                        tree_sha=PATCH_TREE_SHA,
                    )
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = executor.main(
                    [
                        "plan",
                        "--inventory",
                        str(inventory_path),
                        "--candidate",
                        str(candidate_path),
                        "--output",
                        str(output_path),
                    ],
                    runner=FakeRunner(executor.CommandResult),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                json.loads(stdout.getvalue()),
                json.loads(output_path.read_text(encoding="utf-8")),
            )


class HardeningRegressionTests(unittest.TestCase):
    def test_verify_plan__cannot_disguise_declined_major_as_autonomous_close(
        self,
    ) -> None:
        pr = pull_request(
            number=51,
            head_sha=MAJOR_HEAD_SHA,
            dependency_value=dependency(
                name="next",
                from_version="15.4.0",
                to_version="16.0.0",
                impact="major",
            ),
        )
        parent = executor.build_plan(
            inventory(pr),
            update_candidate(pr, effective_impact="major", tree_sha=MAJOR_TREE_SHA),
            created_at=NOW,
        )
        plan = executor.build_plan(
            inventory(pr),
            close_candidate(
                pr,
                reason="major-declined",
                evidence=user_decision_evidence(pr),
                decision="close-declined-major",
                parent_plan_digest=parent["planDigest"],
            ),
            created_at=NOW,
        )
        plan["candidate"]["decision"] = "close-nonapplicable"
        plan["approval"] = {
            "kind": "none",
            "required": False,
            "approveToken": None,
            "rejectToken": None,
            "closeToken": None,
            "parentPlanDigest": None,
        }
        plan["planDigest"] = executor.canonical_digest(
            executor._plan_digest_payload(plan)
        )

        assert_contract_error(self, lambda: executor._verify_plan_structure(plan))

    def test_build_plan__rejects_duplicate_validation_results(self) -> None:
        pr = pull_request(
            number=52,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )
        candidate = update_candidate(
            pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
        )
        candidate["validation"].append(deepcopy(candidate["validation"][0]))

        assert_contract_error(
            self,
            lambda: executor.build_plan(inventory(pr), candidate, created_at=NOW),
        )

    def test_build_plan__preserves_pinned_action_patch_classification(self) -> None:
        pr = pull_request(
            number=53,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="actions/checkout",
                from_version="8" * 40,
                to_version="9" * 40,
                impact="patch",
                ecosystem="github-actions",
            ),
            manifest=".github/workflows/ci.yml",
            lockfile=".github/dependabot.yml",
        )
        candidate = update_candidate(
            pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
        )

        plan = executor.build_plan(inventory(pr), candidate, created_at=NOW)

        self.assertEqual(plan["approval"]["kind"], "none")
        executor._verify_plan_structure(plan)

    def test_live_source_metadata__rejects_major_described_as_patch(self) -> None:
        pr = pull_request(
            number=54,
            head_sha=MAJOR_HEAD_SHA,
            dependency_value=dependency(
                name="next",
                from_version="15.4.0",
                to_version="16.0.0",
                impact="major",
            ),
        )
        candidate = update_candidate(
            pr,
            effective_impact="patch",
            tree_sha=MAJOR_TREE_SHA,
        )
        candidate["versions"][0]["impact"] = "patch"
        live = {
            "title": pr["title"],
            "body": pr["body"],
            "head": {"ref": pr["head"]["ref"]},
        }

        with self.assertRaises(executor.ExecutorError) as raised:
            executor._validate_live_source_metadata(live, candidate)
        self.assertEqual(raised.exception.exit_code, executor.EXIT_STALE)

    def test_load_state__rejects_invalid_confirmed_operation(self) -> None:
        pr = pull_request(
            number=55,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )
        plan = executor.build_plan(
            inventory(pr),
            update_candidate(pr, effective_impact="patch", tree_sha=PATCH_TREE_SHA),
            created_at=NOW,
        )
        state = executor._new_state(plan, NOW)
        state["operations"][0]["status"] = "confirmed"
        state["operations"][0]["attempts"] = -1
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text(json.dumps(state), encoding="utf-8")
            assert_contract_error(
                self,
                lambda: executor._load_state(path, plan, NOW),
            )

    def test_is_404__requires_an_explicit_http_status(self) -> None:
        self.assertFalse(
            executor._is_404(executor.CommandResult(1, stderr="network host not found"))
        )
        self.assertTrue(
            executor._is_404(executor.CommandResult(1, stderr="HTTP 404: Not Found"))
        )

    def test_finalize__recovers_direct_merge_after_lost_ack(self) -> None:
        pr = pull_request(
            number=56,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )
        plan = executor.build_plan(
            inventory(pr),
            update_candidate(pr, effective_impact="patch", tree_sha=PATCH_TREE_SHA),
            created_at=NOW,
        )
        state = executor._new_state(plan, NOW)
        runner = FakeRunner(executor.CommandResult)
        live_pr = {
            "number": pr["number"],
            "state": "closed",
            "merged_at": NOW,
            "merge_commit_sha": MERGE_SHA,
            "title": pr["title"],
            "body": pr["body"],
            "user": {"login": "dependabot[bot]", "type": "Bot"},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
                "sha": MERGE_SHA,
            },
            "head": {"sha": PATCH_HEAD_SHA, "ref": pr["head"]["ref"]},
        }
        runner.expect(
            [
                "gh",
                "api",
                "--hostname",
                "github.com",
                "--method",
                "GET",
                f"repos/{NAME_WITH_OWNER}/pulls/{pr['number']}",
            ],
            stdout=json.dumps(live_pr),
        )
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            executor._finalize(
                runner,
                executor._Mutations(runner, False),
                plan,
                state,
                state_path,
                NOW,
            )
            persisted = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(persisted["status"], "merged")
        self.assertEqual(persisted["mergeCommitSha"], MERGE_SHA)
        self.assertEqual(runner.mutating_calls, [])
        runner.assert_exhausted()

    def test_finalize__recovers_replacement_merge_and_closes_source_idempotently(
        self,
    ) -> None:
        pr = pull_request(
            number=57,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )
        plan = executor.build_plan(
            inventory(pr),
            update_candidate(
                pr,
                effective_impact="patch",
                tree_sha=PATCH_TREE_SHA,
                mode="replacement",
            ),
            created_at=NOW,
        )
        state = executor._new_state(plan, NOW)
        state["status"] = "published"
        state["replacement"] = {
            "number": 99,
            "url": f"https://github.com/{NAME_WITH_OWNER}/pull/99",
            "headSha": PATCH_HEAD_SHA,
        }
        executor._confirm_operation(
            state,
            "push",
            f"branch:{plan['destinationBranch']}",
            f"head={PATCH_HEAD_SHA}",
        )
        executor._confirm_operation(
            state,
            "create-replacement",
            "replacement",
            "pr=99",
        )
        merge_operation = executor._operation(state, "merge", "replacement")
        merge_operation["attempts"] = 1
        merge_operation["lastObserved"] = "merge acknowledgement was lost"

        replacement = {
            "number": 99,
            "state": "closed",
            "merged_at": NOW,
            "merge_commit_sha": MERGE_SHA,
            "html_url": f"https://github.com/{NAME_WITH_OWNER}/pull/99",
            "body": executor._replacement_marker(plan),
            "user": {"login": "automation-user", "type": "User"},
            "base": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": "main",
                "sha": MERGE_SHA,
            },
            "head": {
                "repo": {"full_name": NAME_WITH_OWNER},
                "ref": plan["destinationBranch"],
                "sha": PATCH_HEAD_SHA,
            },
        }
        close_marker = executor._replacement_close_marker(
            plan, plan["candidate"]["sources"][0], 99, MERGE_SHA
        )
        remote: dict[str, Any] = {"sourceClosed": False, "comments": []}
        runner = FakeRunner(executor.CommandResult)

        def source_pr() -> dict[str, Any]:
            return {
                "number": pr["number"],
                "state": "closed" if remote["sourceClosed"] else "open",
                "merged_at": None,
                "merge_commit_sha": None,
                "title": pr["title"],
                "body": pr["body"],
                "user": {"login": "dependabot[bot]", "type": "Bot"},
                "base": {
                    "repo": {"full_name": NAME_WITH_OWNER},
                    "ref": "main",
                    "sha": MERGE_SHA,
                },
                "head": {"sha": PATCH_HEAD_SHA, "ref": pr["head"]["ref"]},
            }

        def respond(call: Any) -> object:
            args = call.args
            if args[:2] == ("gh", "api"):
                endpoint = args[-1]
                if endpoint.startswith(
                    f"repos/{NAME_WITH_OWNER}/pulls?state=all&head="
                ):
                    return runner.result(stdout=json.dumps([replacement]))
                if endpoint == f"repos/{NAME_WITH_OWNER}/pulls/{pr['number']}":
                    return runner.result(stdout=json.dumps(source_pr()))
                if endpoint.startswith(
                    f"repos/{NAME_WITH_OWNER}/issues/{pr['number']}/comments?"
                ):
                    return runner.result(stdout=json.dumps(remote["comments"]))
            if args[:4] == ("gh", "pr", "comment", str(pr["number"])):
                remote["comments"].append({"body": args[args.index("--body") + 1]})
                return runner.result()
            if args[:4] == ("gh", "pr", "close", str(pr["number"])):
                remote["sourceClosed"] = True
                return runner.result()
            raise AssertionError(f"Unexpected replacement command: {' '.join(args)}")

        runner.when(
            lambda _call: True,
            respond,
            description="merged replacement and source closure remote",
            times=None,
        )

        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            executor._finalize(
                runner,
                executor._Mutations(runner, False),
                plan,
                state,
                state_path,
                NOW,
            )
            mutation_count = len(runner.mutating_calls)
            executor._finalize(
                runner,
                executor._Mutations(runner, False),
                plan,
                state,
                state_path,
                LATER,
            )
            persisted = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(persisted["status"], "sources-closed")
        self.assertEqual(persisted["mergeCommitSha"], MERGE_SHA)
        self.assertEqual(persisted["sources"][0]["status"], "closed")
        self.assertEqual(
            executor._operation(persisted, "merge", "replacement")["status"],
            "confirmed",
        )
        self.assertEqual(
            executor._operation(
                persisted,
                "close-source",
                f"source:{pr['number']}@{PATCH_HEAD_SHA}",
            )["status"],
            "confirmed",
        )
        self.assertEqual(remote["comments"], [{"body": close_marker}])
        self.assertTrue(remote["sourceClosed"])
        self.assertEqual(mutation_count, 2)
        self.assertEqual(len(runner.mutating_calls), mutation_count)
        self.assertFalse(
            any(call.args[:3] == ("gh", "pr", "merge") for call in runner.calls)
        )

    def test_merge_pr__revalidates_base_immediately_before_mutation(self) -> None:
        pr = pull_request(
            number=58,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )
        plan = executor.build_plan(
            inventory(pr),
            update_candidate(pr, effective_impact="patch", tree_sha=PATCH_TREE_SHA),
            created_at=NOW,
        )
        state = executor._new_state(plan, NOW)
        events: list[str] = []
        runner = FakeRunner(executor.CommandResult)

        def merge_response(call: Any) -> object:
            self.assertEqual(call.args[4:6], ("--repo", GH_REPO))
            events.append("merge")
            return runner.result()

        runner.when(
            lambda call: call.args[:4] == ("gh", "pr", "merge", "58"),
            merge_response,
            description="merge mutation",
            times=1,
        )
        open_pr = {
            "number": 58,
            "state": "open",
            "merged_at": None,
            "merge_commit_sha": None,
            "head": {"sha": PATCH_HEAD_SHA},
        }
        merged_pr = {
            **open_pr,
            "state": "closed",
            "merged_at": NOW,
            "merge_commit_sha": MERGE_SHA,
        }

        def capabilities(*_args: Any, **_kwargs: Any) -> dict[str, bool]:
            events.append("capabilities")
            return {
                "mergeCommitAllowed": False,
                "rebaseMergeAllowed": False,
                "squashMergeAllowed": True,
            }

        def revalidate(*_args: Any, **_kwargs: Any) -> None:
            events.append("base")

        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            with (
                mock.patch.object(
                    executor, "_get_pr", side_effect=[open_pr, merged_pr]
                ),
                mock.patch.object(
                    executor,
                    "_protection_requirements",
                    return_value=(set(), 0, False),
                ),
                mock.patch.object(executor, "_wait_for_checks"),
                mock.patch.object(
                    executor, "_merge_capabilities", side_effect=capabilities
                ),
                mock.patch.object(executor, "_revalidate_base", side_effect=revalidate),
            ):
                merge_sha, queued = executor._merge_pr(
                    runner,
                    executor._Mutations(runner, False),
                    plan,
                    state,
                    58,
                    PATCH_HEAD_SHA,
                    "dependabot[bot]",
                    state_path,
                    NOW,
                    pre_merge_check=lambda: events.append("sources"),
                )

        self.assertEqual((merge_sha, queued), (MERGE_SHA, False))
        self.assertEqual(events, ["capabilities", "base", "sources", "merge"])
        runner.assert_exhausted()

    def test_emitted_contracts__validate_against_all_json_schemas(self) -> None:
        try:
            from jsonschema import Draft202012Validator
            from referencing import Registry, Resource
        except ImportError:
            self.skipTest("jsonschema validation libraries are unavailable")

        pr = pull_request(
            number=57,
            head_sha=PATCH_HEAD_SHA,
            dependency_value=dependency(
                name="react",
                from_version="19.1.0",
                to_version="19.1.1",
                impact="patch",
            ),
        )
        uv_pr = pull_request(
            number=59,
            head_sha="9" * 40,
            dependency_value=dependency(
                name="vulture",
                from_version="2.14",
                to_version="2.16",
                impact="minor",
                ecosystem="uv",
            ),
            manifest="backend/pyproject.toml",
            lockfile="backend/uv.lock",
        )
        observed_inventory = inventory(pr, uv_pr)
        candidate = batch_candidate([pr, uv_pr])
        plan = executor.build_plan(observed_inventory, candidate, created_at=NOW)
        state = executor._new_state(plan, NOW)
        schema_dir = Path(__file__).parents[1] / "schemas"
        schemas = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in schema_dir.glob("*.json")
        }
        registry = Registry()
        for schema in schemas.values():
            registry = registry.with_resource(
                schema["$id"], Resource.from_contents(schema)
            )
        cases = {
            "inventory-v1.schema.json": observed_inventory,
            "candidate-v1.schema.json": candidate,
            "plan-v1.schema.json": plan,
            "state-v1.schema.json": state,
        }
        for schema_name, value in cases.items():
            with self.subTest(schema=schema_name):
                errors = list(
                    Draft202012Validator(
                        schemas[schema_name], registry=registry
                    ).iter_errors(value)
                )
                self.assertEqual(errors, [])

        invalid_batch = deepcopy(candidate)
        invalid_batch["stabilityEvidence"][0]["summary"] = (
            "breaking=applicable; adaptation=not-required"
        )
        candidate_validator = Draft202012Validator(
            schemas["candidate-v1.schema.json"], registry=registry
        )
        self.assertTrue(list(candidate_validator.iter_errors(invalid_batch)))

        legacy_candidate = update_candidate(
            pr,
            effective_impact="patch",
            tree_sha=PATCH_TREE_SHA,
        )
        legacy_candidate["stabilityEvidence"][0]["summary"] = (
            "Legacy v1 stable release summary."
        )
        legacy_candidate["stabilityEvidence"][0]["subject"] = "react"
        legacy_plan = executor.build_plan(
            inventory(pr), legacy_candidate, created_at=NOW
        )
        legacy_cases = {
            "candidate-v1.schema.json": legacy_candidate,
            "plan-v1.schema.json": legacy_plan,
        }
        for schema_name, value in legacy_cases.items():
            with self.subTest(schema=schema_name, compatibility="singleton-v1"):
                errors = list(
                    Draft202012Validator(
                        schemas[schema_name], registry=registry
                    ).iter_errors(value)
                )
                self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
