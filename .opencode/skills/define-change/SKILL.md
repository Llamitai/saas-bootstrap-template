---
name: define-change
description: Define scope, observable acceptance, contracts and a verification plan for new behavior or unresolved requirements. Reuse an existing definition for implementation requests.
---

# define-change

Read the request, prior decisions and `docs/internal/project-profile.md` from the Git root. Inspect the affected implementation, callers and tests. Read PRODUCT.md and DESIGN.md only for UI work.

1. Establish the problem and consumer, scope/exclusions, observable acceptance IDs, affected contracts/capabilities, risks and the first vertical task with its owner and test/services plan. These are the Definition of Ready; files alone do not establish readiness.
2. Reuse existing decisions and authorization. For an unresolved idea, explore concrete scenarios and compare two or three approaches only when a real decision remains; explain the recommended interfaces, data flow and failure modes. Ask only for critical missing information; continue independent work. Use the project's visual guidance when UI decisions remain.
3. For functional backend, frontend or fullstack work, use one OpenSpec change. Use [openspec-propose](../openspec-propose/SKILL.md) for artifacts or [openspec-explore](../openspec-explore/SKILL.md) for uncertainty. Resolve paths with the repository CLI; do not create another PRD/spec or assume a planning home.
4. Run `just change-status <id>` and `just spec-check <id>`. Structural validity does not prove that acceptance is observable or the requirement correct.
5. For mechanical/docs work record purpose, acceptance and proportional evidence in the existing task/PR/conversation. Do not create an artificial spec or test. Reclassify if behavior, permissions, contracts or data start changing.

Output readiness, assumptions, artifact paths and criterion-to-task-to-evidence mapping. If implementation is authorized and ready, continue with backend-change/frontend-change; otherwise deliver the requested definition. Use [the evidence contract](../validate-change/references/evidence.md) throughout the loop.

OpenSpec skills and generated opsx commands remain upstream-managed and unchanged. Use the project workflows and locked CLI wrappers to coordinate definition and closure; never patch vendor skill content to implement project policy.
