---
name: verify-change
description: Select and run checks, reproduce bugs, diagnose failing gates, add regression tests or assess requested coverage across Python, TypeScript and integration. Supplies technical evidence; validate-change owns acceptance.
---

# verify-change

Read the acceptance criteria, exact diff and `docs/internal/verification.md`. Select [Python](references/python.md), [TypeScript](references/typescript.md) or [integration](references/integration.md) guidance according to the affected contract.

Use an observable criterion -> hypothesis -> smallest experiment -> implementer correction -> regression loop. A regression must fail before the fix for the expected reason and pass afterward. Check observable state, not only internal call counts. Preserve exit codes and distinguish a change failure, baseline failure and missing environment. Missing DB/browser, zero selected tests and required skips never count as passing.

Run checks without autofix; review-change must not repair files. Use just backend check / just frontend check for static work, just frontend verify for functional frontend, just verify for integrated backend/frontend. Add API, browser, migrations and docs checks by impact. Root verify does not imply these ran.

Report prerequisites, commands, exit codes, selection, services and tested revision using [the evidence contract](../validate-change/references/evidence.md). Reuse still-applicable results; repeat only after affected sources/config/fixtures or hypotheses change. Verification supplies evidence to validate-change; it does not itself accept the user's need.
