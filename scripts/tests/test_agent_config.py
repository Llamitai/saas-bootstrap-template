import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('check_agent_config', Path(__file__).parents[1] / 'check_agent_config.py')
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class AgentConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in checker.WORKFLOWS:
            self.write(f'.claude/skills/{name}/SKILL.md', f'---\nname: {name}\ndescription: Work on {name}\n---\n')
        for name in ('AGENTS.md', 'docs/internal/project-profile.md', 'docs/internal/verification.md'):
            self.write(name, '# Working map\n')
        self.write('CLAUDE.md', '@AGENTS.md\n')
        self.write('scripts/skill_inventory.json', json.dumps({'targets': {'.agents/skills': list(checker.WORKFLOWS)}}))
        self.write('.codex/config.toml', '')
        self.write('.opencode/opencode.json', '{}')
        self.write('.mcp.json', '{}')

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_valid_configuration(self):
        self.assertEqual(checker.check(self.root), [])

    def test_broken_resource_and_import_are_reported(self):
        self.write('.claude/skills/define-change/SKILL.md', '---\nname: define-change\ndescription: Define\n---\n[Evidence](missing.md)\n')
        self.write('CLAUDE.md', '# Duplicated instructions')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('missing.md', errors)
        self.assertIn('@AGENTS.md', errors)

    def test_malformed_metadata_and_unportable_config_fail(self):
        self.write('.claude/skills/backend-change/SKILL.md', 'no frontmatter')
        self.write('.codex/config.toml', '[project]\nroot = "/Users/example/project"\n')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('frontmatter', errors)
        self.assertIn('private path', errors)
        self.assertIn('unsupported', errors)

    def test_removed_workflow_in_inventory_fails(self):
        self.write('scripts/skill_inventory.json', json.dumps({'targets': {'.agents/skills': ['define-change']}}))
        self.assertTrue(checker.check(self.root))


if __name__ == '__main__':
    unittest.main()
