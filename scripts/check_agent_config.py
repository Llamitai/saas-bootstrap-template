#!/usr/bin/env python3
"""Check agent metadata, concrete local links and portable client configuration.

Checks explicit file links, not prose semantics or client discovery. Skill-tree
content equality and path safety belong to sync_skills.py, invoked separately.
"""
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ('define-change', 'backend-change', 'frontend-change', 'schema-change', 'verify-change', 'review-change', 'validate-change')


def local_links(path: Path, root: Path) -> list[str]:
    errors = []
    # Code examples are illustrative, not navigable documentation links.
    body = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
    body = re.sub(r'`[^`]+`', '', body)
    for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)', body):
        target = target.split('#', 1)[0].strip('<>')
        if not target or re.match(r'\w+://', target) or any(c in target for c in '*<>` '):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
            errors.append(f'{path.relative_to(root)}: missing/external local link {target}')
    return errors


def check(root: Path = ROOT) -> list[str]:
    errors = []
    skills = root / '.claude/skills'
    for path in sorted(skills.glob('*/SKILL.md')):
        content = path.read_text()
        front = re.match(r'\A---\n(.*?)\n---(?:\n|$)', content, re.S)
        if not front:
            errors.append(f'{path.relative_to(root)}: missing frontmatter')
            continue
        name = re.search(r'^name:\s*(.+)$', front[1], re.M)
        description = re.search(r'^description:\s*(.+)$', front[1], re.M)
        if not name or name[1].strip('\"\'') != path.parent.name:
            errors.append(f'{path.relative_to(root)}: name must match directory')
        if not description or not description[1].strip('\"\''):
            errors.append(f'{path.relative_to(root)}: description required')
    inventory = json.loads((root / 'scripts/skill_inventory.json').read_text())
    project_skills = inventory.get('project_skills', list(WORKFLOWS))
    if not isinstance(project_skills, list) or not all(isinstance(name, str) for name in project_skills):
        raise ValueError('project_skills must be a list of skill names')
    if any(not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) for name in project_skills):
        raise ValueError('project_skills contains an invalid skill name')
    if len(project_skills) != len(set(project_skills)) or set(WORKFLOWS) - set(project_skills):
        errors.append('project_skills must be unique and include the required workflows')
    for name in sorted(set(project_skills) | set(WORKFLOWS)):
        folder = skills / name
        if not (folder / 'SKILL.md').is_file():
            errors.append(f'missing project skill: {name}')
        for path in folder.rglob('*.md'):
            errors.extend(local_links(path, root))
    for name in ('AGENTS.md', 'CLAUDE.md', 'docs/internal/project-profile.md', 'docs/internal/verification.md'):
        path = root / name
        if not path.is_file():
            errors.append(f'missing instruction source: {name}')
        else:
            errors.extend(local_links(path, root))
    claude = root / 'CLAUDE.md'
    if claude.exists() and '@AGENTS.md' not in claude.read_text().splitlines():
        errors.append('CLAUDE.md must import @AGENTS.md')
    native_names = set(inventory['targets'].get('.agents/skills', []))
    compatibility_names = set(inventory['targets'].get('.codex/skills', []))
    duplicates = native_names & compatibility_names & set(project_skills)
    if duplicates:
        errors.append(f'Codex discovers duplicate project skills across .agents and .codex: {sorted(duplicates)}')
    if 'project_skills' in inventory and set(project_skills) - native_names:
        errors.append('project skills must be distributed to the native .agents/skills root')
    for target, names in inventory['targets'].items():
        effective_names = set(names) | (native_names if target == '.codex/skills' else set())
        if set(WORKFLOWS) - effective_names:
            errors.append(f'{target}: required workflows absent from inventory')
        for name in set(names) & set(project_skills):
            for path in (root / target / name).rglob('*.md'):
                errors.extend(local_links(path, root))
    for name in ('.codex/config.toml', '.opencode/opencode.json', '.mcp.json'):
        path = root / name
        content = path.read_text()
        config = tomllib.loads(content) if path.suffix == '.toml' else json.loads(content)
        if re.search(r'/Users/|/home/[^/$\s]+|trust_level\s*=', content):
            errors.append(f'{name}: private path/trust state is not portable')
        if name == '.codex/config.toml' and set(config) & {'project', 'agent', 'rules'}:
            errors.append(f'{name}: unsupported project instruction/discovery fields; use native discovery')
    return errors


if __name__ == '__main__':
    try:
        errors = check()
    except (OSError, ValueError, KeyError) as error:
        errors = [str(error)]
    for error in errors:
        print(f'error: {error}', file=sys.stderr)
    if not errors:
        print('Agent metadata, project skill links, discovery inventory and portable configuration passed (not a client smoke).')
    sys.exit(bool(errors))
