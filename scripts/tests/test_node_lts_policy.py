from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import node_lts_policy as policy  # noqa: E402


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _package(*, types: bool = False) -> str:
    document: dict[str, object] = {
        "private": True,
        "engines": {"node": ">=24.0.0 <25.0.0"},
    }
    if types:
        document["devDependencies"] = {"@types/node": "^24"}
    return json.dumps(document, indent=2) + "\n"


def _fixture(root: Path, *, canonical: bool = False) -> None:
    _write(root, ".nvmrc", "24\n")
    _write(root, "README.md", "- **Node.js 24** (version pinned in `.nvmrc`).\n")
    _write(root, "package.json", _package())
    _write(root, "frontend/package.json", _package(types=True))
    _write(root, "docs/package.json", _package(types=True))
    _write(
        root,
        "frontend/Dockerfile",
        "FROM node:24-slim AS deps\nFROM node:24-slim AS builder\n"
        "FROM node:24-slim AS production\n",
    )
    _write(
        root,
        ".gitlab/ci/quality.gitlab-ci.yml",
        "quality:frontend:\n  image: node:24-slim\n",
    )
    _write(
        root,
        ".github/workflows/code_quality.yml",
        "jobs:\n  frontend:\n    steps:\n      - uses: actions/setup-node@v7\n"
        "        with:\n          node-version: 24\n",
    )
    _write(
        root,
        ".github/workflows/node-lts.yml",
        "jobs:\n  prepare:\n    steps:\n      - uses: actions/setup-node@v7\n"
        "        with:\n          node-version-file: .nvmrc\n",
    )
    _write(
        root,
        ".github/dependabot.yml",
        'ignore:\n  - dependency-name: "@types/node"\n'
        '    update-types: ["version-update:semver-major"]\n'
        '  - dependency-name: "@types/node"\n'
        '    update-types: ["version-update:semver-major"]\n'
        '  - dependency-name: "node"\n'
        '    update-types: ["version-update:semver-major"]\n',
    )
    if canonical:
        _write(root, "scripts/build_template.py", "# canonical marker\n")
        _write(
            root,
            ".github/workflows/publish-template.yml",
            "jobs:\n  publish:\n    steps:\n      - uses: actions/setup-node@v7\n"
            "        with:\n          node-version: 24\n",
        )


class ScheduleTests(unittest.TestCase):
    def test_selects_highest_major_that_has_entered_lts(self) -> None:
        schedule = {
            "v22": {"lts": "2024-10-29", "end": "2027-04-30"},
            "v24": {"lts": "2025-10-28", "end": "2028-04-30"},
            "v25": {"end": "2026-06-01"},
            "v26": {"lts": "2026-10-28", "end": "2029-04-30"},
        }

        before = policy.select_latest_lts(schedule, date(2026, 8, 15))
        after = policy.select_latest_lts(schedule, date(2026, 10, 28))

        self.assertEqual(before, policy.LTSRelease(24, date(2025, 10, 28)))
        self.assertEqual(after, policy.LTSRelease(26, date(2026, 10, 28)))

    def test_end_date_is_exclusive(self) -> None:
        schedule = {"v24": {"lts": "2025-10-28", "end": "2026-08-15"}}

        with self.assertRaisesRegex(policy.PolicyError, "no supported LTS"):
            policy.select_latest_lts(schedule, date(2026, 8, 15))

    def test_rejects_malformed_lts_entry(self) -> None:
        schedule = {"v24": {"lts": "soon", "end": "2028-04-30"}}

        with self.assertRaisesRegex(policy.PolicyError, "v24.lts"):
            policy.select_latest_lts(schedule, date(2026, 8, 15))

    def test_rejects_empty_schedule(self) -> None:
        with self.assertRaisesRegex(policy.PolicyError, "non-empty"):
            policy.select_latest_lts({}, date(2026, 8, 15))

    def test_rejects_local_major_newer_than_official_lts(self) -> None:
        official = policy.LTSRelease(24, date(2025, 10, 28))

        with self.assertRaisesRegex(policy.PolicyError, "newer than official"):
            policy.migration_required(26, official)

    def test_reports_when_an_lts_migration_is_required(self) -> None:
        official = policy.LTSRelease(26, date(2026, 10, 28))

        self.assertTrue(policy.migration_required(24, official))
        self.assertFalse(policy.migration_required(26, official))


class RepositoryPolicyTests(unittest.TestCase):
    def test_checks_generated_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root)

            self.assertEqual(policy.check_repository(root), (24, "generated"))

    def test_checks_canonical_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root, canonical=True)

            self.assertEqual(policy.check_repository(root), (24, "canonical"))

    def test_canonical_profile_requires_publish_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root, canonical=True)
            (root / ".github/workflows/publish-template.yml").unlink()

            with self.assertRaisesRegex(policy.PolicyError, "publish-template"):
                policy.check_repository(root)

    def test_rejects_readme_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root)
            _write(root, "README.md", "- **Node.js 22** (stale).\n")

            with self.assertRaisesRegex(policy.PolicyError, "README"):
                policy.check_repository(root)

    def test_rejects_gitlab_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root)
            _write(
                root,
                ".gitlab/ci/quality.gitlab-ci.yml",
                "quality:frontend:\n  image: node:22-slim\n",
            )

            with self.assertRaisesRegex(policy.PolicyError, "GitLab|gitlab"):
                policy.check_repository(root)

    def test_rejects_static_setup_node_drift_in_additional_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root)
            _write(
                root,
                ".github/workflows/extra.yml",
                "jobs:\n  extra:\n    steps:\n      - uses: actions/setup-node@v7\n"
                "        with:\n          node-version: 26\n",
            )

            with self.assertRaisesRegex(policy.PolicyError, "must use Node 24"):
                policy.check_repository(root)

    def test_dynamic_node_version_is_limited_to_lts_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root)
            _write(
                root,
                ".github/workflows/extra.yml",
                "jobs:\n  extra:\n    steps:\n      - uses: actions/setup-node@v7\n"
                "        with:\n          node-version-file: .nvmrc\n",
            )

            with self.assertRaisesRegex(policy.PolicyError, "may not use"):
                policy.check_repository(root)

    def test_updates_generated_profile_without_creating_canonical_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root)

            changed = policy.update_repository(root, 26)

            self.assertEqual(policy.check_repository(root), (26, "generated"))
            self.assertNotIn(Path(".github/workflows/publish-template.yml"), changed)
            self.assertFalse((root / ".github/workflows/publish-template.yml").exists())
            self.assertIn("node:26-slim", (root / "frontend/Dockerfile").read_text())
            self.assertIn("Node.js 26", (root / "README.md").read_text())

    def test_updates_canonical_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root, canonical=True)

            changed = policy.update_repository(root, 26)

            self.assertEqual(policy.check_repository(root), (26, "canonical"))
            self.assertIn(Path(".github/workflows/publish-template.yml"), changed)
            self.assertIn(
                "node-version: 26",
                (root / ".github/workflows/publish-template.yml").read_text(),
            )

    def test_update_rejects_unmanaged_static_workflow_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root)
            _write(
                root,
                ".github/workflows/extra.yml",
                "jobs:\n  extra:\n    steps:\n      - uses: actions/setup-node@v7\n"
                "        with:\n          node-version: 24\n",
            )

            with self.assertRaisesRegex(policy.PolicyError, "unmanaged"):
                policy.update_repository(root, 26)

            self.assertEqual((root / ".nvmrc").read_text(), "24\n")


if __name__ == "__main__":
    unittest.main()
