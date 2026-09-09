from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
VALID = '''## ADDED Requirements

### Requirement: Scoped membership
The API SHALL preserve the active tenant scope.

#### Scenario: Authorized member
- **WHEN** an authorized member reads its tenant
- **THEN** the response contains only that tenant
'''


class OpenSpecWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        shutil.copy(ROOT / 'scripts/openspec.mjs', self.root / 'scripts/openspec.mjs')
        (self.root / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
        self.change = self.root / 'openspec/changes/test-membership'
        self.spec = self.change / 'specs/membership/spec.md'
        self.spec.parent.mkdir(parents=True)
        self.spec.write_text(VALID)
        (self.change / 'proposal.md').write_text('## Why\nPreserve scope\n\n## What Changes\nCheck scope\n')

    def run_cli(self, *args):
        return subprocess.run(['node', str(self.root / 'scripts/openspec.mjs'), *args], cwd=self.root, capture_output=True, text=True)

    def test_valid_invalid_and_missing_change(self):
        result = self.run_cli('check', 'test-membership')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.run_cli('status', 'test-membership').returncode, 0)
        self.spec.write_text('invalid delta')
        self.assertNotEqual(self.run_cli('check', 'test-membership').returncode, 0)
        self.assertNotEqual(self.run_cli('check', 'not-present').returncode, 0)
        self.assertNotEqual(self.run_cli('status', 'not-present').returncode, 0)

    def test_invalid_kind_and_path_escape_do_not_invoke_cli(self):
        for item, kind in [('test-membership', 'other'), ('../test-membership', 'change')]:
            result = self.run_cli('check', item, kind)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Usage:', result.stderr)


if __name__ == '__main__':
    unittest.main()
