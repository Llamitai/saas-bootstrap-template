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
# Agent Skills spec fields plus the Claude Code extensions project skills may use.
# Other clients ignore the extensions; unknown keys are rejected to catch typos.
SKILL_KEYS = {
    'name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools',
    'disable-model-invocation', 'user-invocable', 'argument-hint', 'when_to_use',
}
MAX_DESCRIPTION = 1024
MAX_SKILL_LINES = 500
# Supporting content that is executed, templated or tested rather than read as guidance.
NON_REFERENCE_DIRS = {'evals', 'tests', 'templates', 'assets', 'scripts', 'agents'}


def frontmatter(content: str) -> tuple[dict[str, str], str] | None:
    """Parse top-level scalar keys; folded/literal and indented values are joined."""
    match = re.match(r'\A---\n(.*?)\n---(?:\n|$)', content, re.S)
    if not match:
        return None
    fields: dict[str, list[str]] = {}
    key = None
    for line in match[1].splitlines():
        top = re.match(r'([A-Za-z][\w-]*):\s*(.*)$', line)
        if top:
            key = top[1]
            value = top[2].strip()
            fields[key] = [] if value in {'>', '|', '>-', '|-'} else [value]
        elif key and line.strip():
            fields[key].append(line.strip())
    values = {name: ' '.join(parts).strip('"\'') for name, parts in fields.items()}
    return values, content[match.end():]


def project_skill_errors(folder: Path, root: Path) -> list[str]:
    """Check a maintained skill against the Agent Skills spec and invocation policy."""
    path = folder / 'SKILL.md'
    parsed = frontmatter(path.read_text())
    if parsed is None:
        return []
    fields, body = parsed
    label = path.relative_to(root)
    errors = []
    unknown = set(fields) - SKILL_KEYS
    if unknown:
        errors.append(f'{label}: unsupported frontmatter keys {sorted(unknown)}')
    description = fields.get('description', '')
    if len(description) > MAX_DESCRIPTION:
        errors.append(f'{label}: description exceeds {MAX_DESCRIPTION} characters')
    if re.search(r'<[^>]+>', description):
        errors.append(f'{label}: description must not contain XML tags')
    if body.count('\n') > MAX_SKILL_LINES:
        errors.append(f'{label}: body exceeds {MAX_SKILL_LINES} lines; move detail to references')
    for reference in sorted(folder.rglob('*.md')):
        relative = reference.relative_to(folder)
        if reference == path or NON_REFERENCE_DIRS & set(relative.parts[:-1]):
            continue
        if relative.as_posix() not in body:
            errors.append(f'{label}: {relative.as_posix()} is not referenced directly from SKILL.md')
    manual = fields.get('disable-model-invocation') == 'true'
    codex = folder / 'agents/openai.yaml'
    implicit = re.search(r'^\s*allow_implicit_invocation:\s*(\w+)', codex.read_text(), re.M) if codex.is_file() else None
    if manual and not (implicit and implicit[1] == 'false'):
        errors.append(f'{label}: manual-only skill needs policy.allow_implicit_invocation: false in agents/openai.yaml')
    if implicit and implicit[1] == 'false' and not manual:
        errors.append(f'{label}: Codex policy is manual-only but disable-model-invocation is not true')
    return errors


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
            continue
        errors.extend(project_skill_errors(folder, root))
        for path in folder.rglob('*.md'):
            errors.extend(local_links(path, root))
    for name in ('AGENTS.md', 'docs/content/docs/equipo/perfil-del-proyecto.md', 'docs/content/docs/equipo/verificacion.md'):
        path = root / name
        if not path.is_file():
            errors.append(f'missing instruction source: {name}')
        else:
            errors.extend(local_links(path, root))
    # Agents read the rendered docs tree directly: links must resolve and every page needs a title.
    content = root / 'docs/content/docs'
    for path in sorted([*content.rglob('*.md'), *content.rglob('*.mdx')]):
        front = re.match(r'\A---\n(.*?)\n---(?:\n|$)', path.read_text(), re.S)
        if not front or not re.search(r'^title:\s*\S', front[1], re.M):
            errors.append(f'{path.relative_to(root)}: docs page needs frontmatter title')
        errors.extend(local_links(path, root))
    # Claude Code, Codex and OpenCode all read AGENTS.md natively. Claude prefers a
    # CLAUDE.md in the same directory, so any CLAUDE.md would fork the instructions.
    for nested in sorted(root.glob('*/AGENTS.md')):
        errors.extend(local_links(nested, root))
    for claude in sorted([root / 'CLAUDE.md', *root.glob('*/CLAUDE.md')]):
        if claude.is_file():
            errors.append(f'{claude.relative_to(root)}: AGENTS.md is the single instruction file; remove CLAUDE.md')
    native_names = set(inventory['targets'].get('.agents/skills', []))
    # Codex reads .agents/skills and .codex/skills; OpenCode reads .agents, .claude and
    # .opencode skills. A second copy root only duplicates names in their listings.
    for target in set(inventory['targets']) - {'.agents/skills'}:
        errors.append(f'{target}: only .agents/skills is a distribution target; Codex and OpenCode both read it')
    for duplicate_root in ('.codex/skills', '.opencode/skills'):
        if (root / duplicate_root).exists():
            errors.append(f'{duplicate_root}: duplicates .agents/skills for Codex/OpenCode; remove it')
    if 'project_skills' in inventory and set(project_skills) - native_names:
        errors.append('project skills must be distributed to the native .agents/skills root')
    for target, names in inventory['targets'].items():
        if set(WORKFLOWS) - set(names):
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
        if name == '.opencode/opencode.json' and any(
            Path(item).as_posix().lstrip('./') == 'AGENTS.md' for item in config.get('instructions', [])
        ):
            errors.append(f'{name}: OpenCode already loads the root AGENTS.md; remove it from instructions')
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
