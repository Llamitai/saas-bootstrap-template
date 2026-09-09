# Claude project configuration

Read [AGENTS.md](../AGENTS.md) for shared instructions and the linked project profile/verification guide. Claude uses .claude/skills and imports the shared map through CLAUDE.md.

Edit skills only in `.claude/skills`, then run `just sync-skills` and `just agent-check`. The explicit inventory is `scripts/skill_inventory.json`; checks detect missing copies and resources before any repair. Specialized subsets remain supported. OpenSpec skills and generated opsx commands stay unchanged; the project workflows own acceptance orchestration.

See the [ownership audit](../docs/internal/adr/0003-auditoria-y-depuracion-de-skills.md)
before adding a project skill. Extend the existing owner when the outcome is
already covered. Definition belongs to define-change; coverage work belongs to
verify-change. Retired entries are absent from both sources and inventory.
`project_skills` in the inventory identifies locally maintained entries and
adaptations. They are distributed to `.agents/skills` for Codex, without a second
copy in `.codex/skills`; `agent-check` guards this discovery boundary.

MCP integrations are optional. Enable installed integrations locally and supply credentials through environment references; do not commit private paths, keys or trust state. Use Git/rg, files, stack CLIs and an available browser as the base workflow. Markdown compatibility rules are pointers, not executable policy. Agent-check validates files, not live client discovery or authentication.

For a client smoke, start from root, backend and frontend; record version/CWD, identify seven workflows, load one explicitly and open a supporting resource. Record the effective source and duplicates. Missing client/backend/browser leaves its acceptance pending; do not infer success from file presence.
