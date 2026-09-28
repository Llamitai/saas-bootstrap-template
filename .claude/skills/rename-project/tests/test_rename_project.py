from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "rename_project.py"
BRANDING = SKILL_DIR.parents[2] / "scripts" / "branding_tokens.json"


class RenameProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        shutil.copy(BRANDING, self.root / "scripts" / "branding_tokens.json")
        self.write(
            "README.md",
            "# SaaS Bootstrap\nRun saas-bootstrap-api with saas_bootstrap_db.\n"
            "Update from gh:Llamitai/saas-bootstrap-template.\n",
        )
        self.write("backend/pyproject.toml", 'name = "SaaS Bootstrap"\n')
        self.write("uv.lock", 'name = "saas-bootstrap"\n')
        self.write(".claude/skills/example/SKILL.md", "SaaS Bootstrap skill\n")

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read(self, name: str) -> str:
        return (self.root / name).read_text(encoding="utf-8")

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "Acme Portal", "--root", str(self.root), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_rename__replaces_display_slug_and_python_tokens(self) -> None:
        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.read("README.md"),
            "# Acme Portal\nRun acme-portal-api with acme_portal_db.\n"
            "Update from gh:Llamitai/saas-bootstrap-template.\n",
        )

    def test_rename__writes_slug_on_package_metadata_lines(self) -> None:
        self.run_script()

        self.assertEqual(self.read("backend/pyproject.toml"), 'name = "acme-portal"\n')

    def test_rename__skips_lockfiles_and_skill_folders(self) -> None:
        self.run_script()

        self.assertEqual(self.read("uv.lock"), 'name = "saas-bootstrap"\n')
        self.assertEqual(self.read(".claude/skills/example/SKILL.md"), "SaaS Bootstrap skill\n")

    def test_rename__dry_run_reports_without_writing(self) -> None:
        result = self.run_script("--dry-run")

        self.assertIn("Would update: README.md", result.stdout)
        self.assertEqual(self.read("backend/pyproject.toml"), 'name = "SaaS Bootstrap"\n')

    def test_rename__missing_branding_inventory_fails(self) -> None:
        (self.root / "scripts" / "branding_tokens.json").unlink()

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Branding config not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
