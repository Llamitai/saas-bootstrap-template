from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType
from typing import Sequence


def load_release_module() -> ModuleType:
    script = Path(__file__).parents[1] / "scripts" / "release_template.py"
    spec = importlib.util.spec_from_file_location(
        "release_template_skill_script", script
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release = load_release_module()


def git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed:\n{completed.stdout}\n{completed.stderr}"
        )
    return completed.stdout.strip()


class RejectPushRunner(release.SubprocessGitRunner):
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        check: bool = True,
    ) -> object:
        if args and args[0] == "push":
            return release.CommandResult(1, "", "simulated push rejection")
        return super().run(args, cwd=cwd, check=check)


class RecordingRunner(release.SubprocessGitRunner):
    def __init__(self) -> None:
        self.push_args: list[str] | None = None

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        check: bool = True,
    ) -> object:
        if args and args[0] == "push":
            self.push_args = list(args)
        return super().run(args, cwd=cwd, check=check)


class LostAcknowledgementRunner(release.SubprocessGitRunner):
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        check: bool = True,
    ) -> object:
        result = super().run(args, cwd=cwd, check=check)
        if args and args[0] == "push":
            raise release.ReleaseError(
                release.EXIT_GIT_FAILURE,
                "git-execution-failed",
                "simulated lost push acknowledgement",
                "retry safely",
            )
        return result


class ReleaseTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.work = self.root / "work"
        self.origin = self.root / "origin.git"
        self.mirror = self.root / "mirror.git"

        self.work.mkdir()
        git(self.work, "init", "-b", "main")
        git(self.work, "config", "user.name", "Release Test")
        git(self.work, "config", "user.email", "release@test.invalid")
        (self.work / "template.txt").write_text("release one\n")
        git(self.work, "add", "template.txt")
        git(self.work, "commit", "-m", "feat: initial template")
        self.previous_sha = git(self.work, "rev-parse", "HEAD")
        git(self.work, "tag", "v1.2.3")

        git(self.root, "init", "--bare", str(self.origin))
        git(self.work, "remote", "add", "origin", str(self.origin))
        git(self.work, "push", "-u", "origin", "main")
        git(self.work, "push", "origin", "refs/tags/v1.2.3")
        git(self.root, "clone", "--bare", str(self.work), str(self.mirror))

        (self.work / "template.txt").write_text("release two\n")
        git(self.work, "add", "template.txt")
        git(self.work, "commit", "-m", "fix: update template")
        git(self.work, "push", "origin", "main")
        self.head_sha = git(self.work, "rev-parse", "HEAD")

        self.runner = release.SubprocessGitRunner()
        self.config = release.ReleaseConfig(
            expected_github_repo=None,
            canonical_origin_url=str(self.origin),
            mirror_remote=str(self.mirror),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def inspect(self) -> object:
        return release.inspect_repository(self.runner, self.work, self.config)

    def publish(
        self, tag: str = "v1.2.4", runner: object | None = None
    ) -> dict[str, object]:
        return release.publish_release(
            runner or self.runner,
            self.work,
            expected_previous_tag="v1.2.3",
            tag=tag,
            expected_head=self.head_sha,
            confirm_tag=tag,
            config=self.config,
        )

    def test_semver_parsing_order_and_candidates(self) -> None:
        output = "\n".join(
            [
                f"{'1' * 40}\trefs/tags/v1.9.99",
                f"{'2' * 40}\trefs/tags/v1.10.0",
                f"{'3' * 40}\trefs/tags/v01.2.3",
                f"{'4' * 40}\trefs/tags/v2.0.0-rc.1",
                f"{'5' * 40}\trefs/tags/latest",
            ]
        )
        tags = release.parse_remote_tags(output)
        self.assertEqual(max(tags, key=release.parse_semver_tag), "v1.10.0")
        self.assertEqual(
            release.next_version_candidates("v1.2.3"),
            {"patch": "v1.2.4", "minor": "v1.3.0", "major": "v2.0.0"},
        )

    def test_github_remote_normalization_rejects_unsafe_schemes(self) -> None:
        self.assertIsNone(
            release.normalize_github_repo("file://github.com/Llamitai/wise")
        )
        self.assertIsNone(
            release.normalize_github_repo(
                "git://github.com/Llamitai/wise.git", for_push=True
            )
        )
        self.assertEqual(
            release.normalize_github_repo(
                "ssh://git@github.com/Llamitai/wise.git", for_push=True
            ),
            ("llamitai", "wise"),
        )

    def test_cli_argument_errors_use_json_contract(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            release.build_parser().parse_args(["publish", "--tag", "v1.2.4"])
        self.assertEqual(raised.exception.code, 2)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "invalid-arguments")

    def test_annotated_remote_tag_uses_peeled_commit(self) -> None:
        output = "\n".join(
            [
                f"{'a' * 40}\trefs/tags/v1.2.3",
                f"{'b' * 40}\trefs/tags/v1.2.3^{{}}",
            ]
        )
        self.assertEqual(release.parse_remote_tags(output), {"v1.2.3": "b" * 40})

    def test_inspect_returns_remote_snapshot_and_candidates(self) -> None:
        inspection = self.inspect()
        self.assertEqual(inspection.previous_tag, "v1.2.3")
        self.assertEqual(inspection.previous_sha, self.previous_sha)
        self.assertEqual(inspection.head_sha, self.head_sha)
        self.assertTrue(inspection.previous_tag_is_ancestor)
        self.assertEqual(inspection.candidates["patch"], "v1.2.4")

    def test_inspect_rejects_dirty_worktree_without_creating_tag(self) -> None:
        (self.work / "untracked.txt").write_text("dirty\n")
        with self.assertRaises(release.ReleaseError) as raised:
            self.inspect()
        self.assertEqual(raised.exception.exit_code, release.EXIT_LOCAL_GUARD)
        self.assertEqual(raised.exception.code, "dirty-worktree")
        self.assertIsNone(release.local_tag_commit(self.runner, self.work, "v1.2.4"))

    def test_inspect_rejects_wrong_branch(self) -> None:
        git(self.work, "switch", "-c", "release-candidate")
        with self.assertRaises(release.ReleaseError) as raised:
            self.inspect()
        self.assertEqual(raised.exception.exit_code, release.EXIT_LOCAL_GUARD)
        self.assertEqual(raised.exception.code, "wrong-branch")

    def test_repository_rejects_noncanonical_pushurl(self) -> None:
        git(
            self.work,
            "remote",
            "set-url",
            "origin",
            "https://github.com/Llamitai/wise.git",
        )
        git(
            self.work,
            "remote",
            "set-url",
            "--add",
            "--push",
            "origin",
            "https://github.com/example/not-wise.git",
        )
        with self.assertRaises(release.ReleaseError) as raised:
            release.find_repository(self.runner, self.work, release.ReleaseConfig())
        self.assertEqual(raised.exception.exit_code, release.EXIT_LOCAL_GUARD)
        self.assertEqual(raised.exception.code, "wrong-origin-push-url")

    def test_inspect_rejects_unsynchronized_previous_tag(self) -> None:
        git(self.work, "tag", "-d", "v1.2.3")
        with self.assertRaises(release.ReleaseError) as raised:
            self.inspect()
        self.assertEqual(raised.exception.exit_code, release.EXIT_LOCAL_GUARD)
        self.assertEqual(raised.exception.code, "previous-tag-not-synchronized")

    def test_inspect_rejects_previous_tag_missing_from_mirror(self) -> None:
        empty_mirror = self.root / "empty-mirror.git"
        git(self.root, "init", "--bare", str(empty_mirror))
        config = release.ReleaseConfig(
            expected_github_repo=None,
            canonical_origin_url=str(self.origin),
            mirror_remote=str(empty_mirror),
        )
        with self.assertRaises(release.ReleaseError) as raised:
            release.inspect_repository(self.runner, self.work, config)
        self.assertEqual(raised.exception.exit_code, release.EXIT_REMOTE_GUARD)
        self.assertEqual(raised.exception.code, "previous-tag-missing-from-mirror")

    def test_inspect_accepts_non_ancestor_previous_tag(self) -> None:
        git(self.work, "switch", "--orphan", "unrelated-release")
        git(self.work, "rm", "-rf", "--ignore-unmatch", ".")
        (self.work / "unrelated.txt").write_text("unrelated release\n")
        git(self.work, "add", "unrelated.txt")
        git(self.work, "commit", "-m", "feat!: unrelated release history")
        git(self.work, "tag", "v2.0.0")
        git(self.work, "push", "origin", "refs/tags/v2.0.0")
        git(self.work, "push", str(self.mirror), "refs/tags/v2.0.0")
        git(self.work, "switch", "main")

        inspection = self.inspect()
        self.assertEqual(inspection.previous_tag, "v2.0.0")
        self.assertFalse(inspection.previous_tag_is_ancestor)

    def test_inspect_rejects_empty_tree_diff(self) -> None:
        git(self.work, "tag", "v2.0.0", self.head_sha)
        git(self.work, "push", "origin", "refs/tags/v2.0.0")
        git(self.work, "push", str(self.mirror), "refs/tags/v2.0.0")
        git(self.work, "commit", "--allow-empty", "-m", "chore: empty commit")
        git(self.work, "push", "origin", "main")

        with self.assertRaises(release.ReleaseError) as raised:
            self.inspect()
        self.assertEqual(raised.exception.exit_code, release.EXIT_LOCAL_GUARD)
        self.assertEqual(raised.exception.code, "no-release-changes")

    def test_publish_rejects_non_immediate_version_before_mutation(self) -> None:
        with self.assertRaises(release.ReleaseError) as raised:
            self.publish("v1.2.5")
        self.assertEqual(raised.exception.exit_code, 2)
        self.assertEqual(raised.exception.code, "invalid-next-version")
        self.assertIsNone(release.local_tag_commit(self.runner, self.work, "v1.2.5"))

    def test_publish_rejects_confirmation_mismatch(self) -> None:
        with self.assertRaises(release.ReleaseError) as raised:
            release.publish_release(
                self.runner,
                self.work,
                expected_previous_tag="v1.2.3",
                tag="v1.2.4",
                expected_head=self.head_sha,
                confirm_tag="v1.3.0",
                config=self.config,
            )
        self.assertEqual(raised.exception.exit_code, 2)
        self.assertEqual(raised.exception.code, "confirmation-mismatch")

    def test_publish_rejects_newer_tag_added_after_approval(self) -> None:
        git(self.work, "tag", "v1.3.0", self.head_sha)
        git(self.work, "push", "origin", "refs/tags/v1.3.0")
        git(self.work, "push", str(self.mirror), "refs/tags/v1.3.0")

        with self.assertRaises(release.ReleaseError) as raised:
            self.publish()
        self.assertEqual(raised.exception.exit_code, release.EXIT_REMOTE_GUARD)
        self.assertEqual(raised.exception.code, "previous-tag-changed")
        self.assertIsNone(release.local_tag_commit(self.runner, self.work, "v1.2.4"))

    def test_publish_pushes_only_approved_tag_and_is_idempotent(self) -> None:
        recording_runner = RecordingRunner()
        result = self.publish(runner=recording_runner)
        self.assertEqual(
            result,
            {
                "tag": "v1.2.4",
                "sha": self.head_sha,
                "pushed": True,
                "alreadyOnOrigin": False,
                "workflowTriggered": True,
            },
        )
        self.assertIn(
            f"{self.head_sha}:refs/tags/v1.2.4",
            recording_runner.push_args or [],
        )
        remote_tag = git(
            self.root,
            "--git-dir",
            str(self.origin),
            "rev-parse",
            "refs/tags/v1.2.4^{commit}",
        )
        self.assertEqual(remote_tag, self.head_sha)
        self.assertNotIn(
            "v1.2.4", release.ls_remote_tags(self.runner, self.work, str(self.mirror))
        )

        repeated = self.publish()
        self.assertEqual(repeated["pushed"], False)
        self.assertEqual(repeated["alreadyOnOrigin"], True)
        self.assertIsNone(repeated["workflowTriggered"])

    def test_lost_push_acknowledgement_returns_idempotent_result(self) -> None:
        result = self.publish(runner=LostAcknowledgementRunner())
        self.assertEqual(result["pushed"], False)
        self.assertEqual(result["alreadyOnOrigin"], True)
        self.assertIsNone(result["workflowTriggered"])
        self.assertEqual(
            release.ls_remote_tags(self.runner, self.work, "origin")["v1.2.4"],
            self.head_sha,
        )

    def test_publish_rejects_matching_annotated_local_tag(self) -> None:
        git(
            self.work,
            "tag",
            "-a",
            "v1.2.4",
            self.head_sha,
            "-m",
            "annotated candidate",
        )
        with self.assertRaises(release.ReleaseError) as raised:
            self.publish()
        self.assertEqual(raised.exception.exit_code, release.EXIT_LOCAL_GUARD)
        self.assertEqual(raised.exception.code, "local-tag-sha-conflict")

    def test_publish_reuses_matching_local_tag(self) -> None:
        git(self.work, "tag", "v1.2.4", self.head_sha)
        result = self.publish()
        self.assertTrue(result["pushed"])
        self.assertEqual(
            release.ls_remote_tags(self.runner, self.work, "origin")["v1.2.4"],
            self.head_sha,
        )

    def test_failed_push_preserves_local_tag_and_retry_succeeds(self) -> None:
        with self.assertRaises(release.ReleaseError) as raised:
            self.publish(runner=RejectPushRunner())
        self.assertEqual(raised.exception.exit_code, release.EXIT_GIT_FAILURE)
        self.assertEqual(raised.exception.code, "tag-push-failed")
        self.assertEqual(
            release.local_tag_commit(self.runner, self.work, "v1.2.4"),
            self.head_sha,
        )
        self.assertNotIn(
            "v1.2.4", release.ls_remote_tags(self.runner, self.work, "origin")
        )

        retried = self.publish()
        self.assertTrue(retried["pushed"])

    def test_publish_rejects_tag_that_exists_only_on_mirror(self) -> None:
        git(self.work, "tag", "v1.2.4", self.head_sha)
        git(self.work, "push", str(self.mirror), "refs/tags/v1.2.4")
        git(self.work, "tag", "-d", "v1.2.4")

        with self.assertRaises(release.ReleaseError) as raised:
            self.publish()
        self.assertEqual(raised.exception.exit_code, release.EXIT_REMOTE_GUARD)
        self.assertEqual(raised.exception.code, "tag-only-on-mirror")


if __name__ == "__main__":
    unittest.main()
