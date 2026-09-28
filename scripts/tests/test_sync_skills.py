import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("sync_skills", Path(__file__).parents[1] / "sync_skills.py")
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class SyncSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / ".claude/skills/example"
        self.source.mkdir(parents=True)
        (self.source / "SKILL.md").write_text("---\nname: example\ndescription: Example\n---\n")
        (self.source / "resource.txt").write_text("resource")
        (self.root / "scripts").mkdir()
        self.inventory = {"targets": {".agents/skills": ["example"]}}
        self.save_inventory()

    def save_inventory(self):
        (self.root / "scripts/skill_inventory.json").write_text(json.dumps(self.inventory))

    def run_sync(self, *args):
        return sync.main(list(args), root=self.root)

    def test_missing_required_copy_fails_without_writing_then_sync_is_idempotent(self):
        self.assertEqual(self.run_sync("--check"), 1)
        self.assertFalse((self.root / ".agents").exists())
        self.assertEqual(self.run_sync(), 0)
        target = self.root / ".agents/skills/example/SKILL.md"
        stamp = target.stat().st_mtime_ns
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(target.stat().st_mtime_ns, stamp)
        self.assertEqual(self.run_sync("--check"), 0)

    def test_changed_and_missing_resources_fail(self):
        self.run_sync()
        target = self.root / ".agents/skills/example/resource.txt"
        target.write_text("changed")
        self.assertEqual(self.run_sync("--check"), 1)
        self.assertEqual(target.read_text(), "changed")
        target.unlink()
        self.assertEqual(self.run_sync("--check"), 1)

    def test_claude_eval_suite_is_not_distributed(self):
        (self.source / "evals/case").mkdir(parents=True)
        (self.source / "evals/case/prompt.md").write_text("Trigger case")
        self.assertEqual(self.run_sync(), 0)
        self.assertFalse((self.root / ".agents/skills/example/evals").exists())
        self.assertEqual(self.run_sync("--check"), 0)

    def test_orphan_is_not_deleted(self):
        self.run_sync()
        orphan = self.root / ".agents/skills/unmanaged"
        orphan.mkdir()
        self.assertEqual(self.run_sync(), 1)
        self.assertTrue(orphan.exists())

    def test_unknown_name_and_path_escape_fail(self):
        self.assertEqual(self.run_sync("../example"), 1)
        self.inventory["targets"] = {"../outside": ["example"]}
        self.save_inventory()
        self.assertEqual(self.run_sync(), 1)

    def test_external_target_and_resource_symlinks_fail(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / ".agents").symlink_to(outside, target_is_directory=True)
            self.assertEqual(self.run_sync(), 1)
            self.assertEqual(list(Path(outside).iterdir()), [])
        (self.root / ".agents").unlink()
        (self.source / "escape").symlink_to("/tmp")
        self.assertEqual(self.run_sync(), 1)

    def test_missing_source_fails(self):
        (self.source / "SKILL.md").unlink()
        self.assertEqual(self.run_sync(), 1)


if __name__ == "__main__":
    unittest.main()
