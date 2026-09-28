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
        self.write('AGENTS.md', '# Working map\n')
        for name in ('docs/content/docs/equipo/perfil-del-proyecto.md', 'docs/content/docs/equipo/verificacion.md'):
            self.write(name, '---\ntitle: Contract\n---\n\nBody.\n')
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

    def test_agents_md_is_the_only_instruction_file(self):
        self.write('frontend/AGENTS.md', 'Notes. [Gone](missing.md)\n')
        self.write('CLAUDE.md', '@AGENTS.md\n')
        self.write('frontend/CLAUDE.md', '@AGENTS.md\n')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('CLAUDE.md: AGENTS.md is the single instruction file', errors)
        self.assertIn('frontend/CLAUDE.md: AGENTS.md is the single instruction file', errors)
        self.assertIn('frontend/AGENTS.md: missing/external local link missing.md', errors)
        (self.root / 'CLAUDE.md').unlink()
        (self.root / 'frontend/CLAUDE.md').unlink()
        self.write('frontend/AGENTS.md', 'Notes.\n')
        self.assertEqual(checker.check(self.root), [])

    def test_docs_pages_need_title_and_resolvable_links(self):
        self.write('docs/content/docs/guias/untitled.mdx', 'No frontmatter.\n')
        self.write('docs/content/docs/guias/linked.md', '---\ntitle: Linked\n---\n\n[Gone](../missing.md) [Ok](untitled.mdx)\n')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('untitled.mdx: docs page needs frontmatter title', errors)
        self.assertIn('linked.md: missing/external local link ../missing.md', errors)
        self.assertNotIn('untitled.mdx: missing', errors)

    def test_broken_resource_and_import_are_reported(self):
        self.write('.claude/skills/define-change/SKILL.md', '---\nname: define-change\ndescription: Define\n---\n[Evidence](missing.md)\n')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('missing.md', errors)

    def test_malformed_metadata_and_unportable_config_fail(self):
        self.write('.claude/skills/backend-change/SKILL.md', 'no frontmatter')
        self.write('.codex/config.toml', '[project]\nroot = "/Users/example/project"\n')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('frontmatter', errors)
        self.assertIn('private path', errors)
        self.assertIn('unsupported', errors)

    def test_skill_spec_violations_are_reported(self):
        long_description = 'x' * (checker.MAX_DESCRIPTION + 1)
        self.write('.claude/skills/define-change/SKILL.md', f'---\nname: define-change\ndescription: >\n  {long_description}\nmodel: opus\n---\n')
        self.write('.claude/skills/define-change/references/hidden.md', '# Hidden\n')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('description exceeds', errors)
        self.assertIn("unsupported frontmatter keys ['model']", errors)
        self.assertIn('references/hidden.md is not referenced directly', errors)

    def test_referenced_folded_description_passes(self):
        self.write('.claude/skills/define-change/SKILL.md', '---\nname: define-change\ndescription: >\n  Define a change.\n  Use when scope is open.\n---\nRead [guide](references/guide.md).\n')
        self.write('.claude/skills/define-change/references/guide.md', '# Guide\n')
        self.assertEqual(checker.check(self.root), [])

    def test_manual_invocation_must_match_across_clients(self):
        self.write('.claude/skills/define-change/SKILL.md', '---\nname: define-change\ndescription: Define\ndisable-model-invocation: true\n---\n')
        self.write('.claude/skills/review-change/agents/openai.yaml', 'policy:\n  allow_implicit_invocation: false\n')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('define-change/SKILL.md: manual-only skill needs policy', errors)
        self.assertIn('review-change/SKILL.md: Codex policy is manual-only', errors)

    def test_manual_invocation_declared_for_both_clients_passes(self):
        self.write('.claude/skills/define-change/SKILL.md', '---\nname: define-change\ndescription: Define\ndisable-model-invocation: true\n---\n')
        self.write('.claude/skills/define-change/agents/openai.yaml', 'policy:\n  allow_implicit_invocation: false\n')
        self.assertEqual(checker.check(self.root), [])

    def test_duplicate_client_skill_roots_fail(self):
        self.write('scripts/skill_inventory.json', json.dumps({'targets': {
            '.agents/skills': list(checker.WORKFLOWS), '.opencode/skills': list(checker.WORKFLOWS)}}))
        self.write('.codex/skills/define-change/SKILL.md', '---\nname: define-change\ndescription: Define\n---\n')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('.opencode/skills: only .agents/skills is a distribution target', errors)
        self.assertIn('.codex/skills: duplicates .agents/skills', errors)

    def test_opencode_instructions_repeating_agents_md_fail(self):
        self.write('.opencode/opencode.json', '{"instructions": ["./AGENTS.md", "docs/extra.md"]}')
        errors = '\n'.join(checker.check(self.root))
        self.assertIn('OpenCode already loads the root AGENTS.md', errors)

    def test_removed_workflow_in_inventory_fails(self):
        self.write('scripts/skill_inventory.json', json.dumps({'targets': {'.agents/skills': ['define-change']}}))
        self.assertTrue(checker.check(self.root))


if __name__ == '__main__':
    unittest.main()
