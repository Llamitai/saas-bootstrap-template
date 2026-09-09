# Opencode project configuration

Read [AGENTS.md](../AGENTS.md) for shared instructions and the linked project profile/verification guide. OpenCode discovers .opencode/skills and compatible ancestor .claude/skills/.agents/skills. Verify the effective source with the installed client version.

Edit skills only in `.claude/skills`, then run `just sync-skills` and `just agent-check`. The explicit inventory is `scripts/skill_inventory.json`; checks detect missing copies and resources before any repair. Specialized subsets remain supported. OpenSpec skills and generated opsx commands stay unchanged; the project workflows own acceptance orchestration.

MCP integrations are optional. Enable installed integrations locally and supply credentials through environment references; do not commit private paths, keys or trust state. Use Git/rg, files, stack CLIs and an available browser as the base workflow. Markdown compatibility rules are pointers, not executable policy. Agent-check validates files, not live client discovery or authentication.

For a client smoke, start from root, backend and frontend; record version/CWD, identify seven workflows, load one explicitly and open a supporting resource. Record the effective source and duplicates. Missing client/backend/browser leaves its acceptance pending; do not infer success from file presence.
