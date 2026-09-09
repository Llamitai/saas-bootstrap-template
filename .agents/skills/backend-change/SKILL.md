---
name: backend-change
description: Build or refine FastAPI use cases, endpoints, repositories, dependencies or jobs. Excludes frontend-only work and reviews without edits.
---

# backend-change

Read `docs/internal/project-profile.md`, `backend/README.md`, the affected acceptance criteria, a matching module exemplar and related tests. Commands run from the Git root; pytest paths are relative to backend.

This workflow owns implementation order and refinement. For an architectural choice, consult [clean-fastapi-ddd](../clean-fastapi-ddd/SKILL.md) and only the relevant reference; it supplies ownership, interfaces and composition conventions. Use the profile and installed exemplar for active capabilities and public contracts. For a backfill, bootstrapper or other operational script, read [operational-scripts.md](references/operational-scripts.md). Selecting a reference does not restart the development loop.

Build one observable vertical slice at a time: test red for the intended reason, minimal implementation including wiring/consumer, test green. Use [TDD](../tdd/SKILL.md) for behavior and [schema-change](../schema-change/SKILL.md) for persistence. Test authorization and scopes when active. Coordinate API/BFF/DTO consumers on one acceptance contract.

Refinement mode: take a concrete finding/objective, identify preserved invariants, start from green, improve interface/responsibility/query/wiring in small steps and rerun affected checks. Use codebase-design for a design seam, not a compulsory rewrite. Fix a known bug before unrelated refactoring. Performance claims need before/after measurement; scope changes return to define-change.

Run `just backend check` and focused `just backend test unit <paths>`; API/persistence/effects follow the impact matrix in `docs/internal/verification.md`. Diagnose failures without weakening existing gates. Hand exact revision, results, unresolved findings and public contract evidence to [validate-change](../validate-change/SKILL.md); green checks alone do not close the change.
