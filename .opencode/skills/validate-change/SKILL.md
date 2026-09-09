---
name: validate-change
description: Validate implemented results against agreed acceptance before closing a change. This is distinct from lint, tests and OpenSpec structural validation.
---

# validate-change

Read normative criteria, exact implemented revision, technical results and review findings. Use [references/evidence.md](references/evidence.md) to maintain acceptance in the existing dossier. You may update evidence/tasks; do not fix implementation, change criteria to fit a failure or publish.

For every required criterion, compare the expected scenario and need with the observed API/data/effects, UI interaction/navigation or operational result. Check defined error/recovery paths. Fullstack contracts require the real boundary; do not invent a screen for backend-only work. Reuse current technical evidence when it already demonstrates the criterion instead of rerunning green suites.

A technically green implementation that contradicts acceptance fails validation. A required check failed/pending, stale evidence, unresolved relevant finding, or explicitly required UAT still pending prevents global validation. Return implementation failures to the owner; a changed/wrong requirement returns to define-change. Continue independent work when an environment blocks a criterion. Do not mark a required criterion not applicable merely to close it.

Definition of Done: every required criterion satisfied on the final revision, impact checks passed, relevant findings resolved, contracts/docs/ADRs current, tasks linked to evidence and owned resources cleaned. Record satisfied/failed/pending/blocked per criterion and explain the global decision. Agent acceptance is not human approval; request subjective or human judgment only if required and unresolved.

Completed task checkboxes, OpenSpec validation and archive are administrative signals, not acceptance. Only after verified/validated closure use openspec-sync-specs/archive as applicable. Cancellation or explicitly requested incomplete archive stays labeled incomplete and must not promote unaccepted behavior. Merge/release/deploy retain their own scope and authorization.

OpenSpec skills and generated opsx commands are upstream-managed; do not edit them. Apply the project acceptance preflight before invoking them. If upstream wording reports all_done or offers archive, interpret it only as structural/administrative state. Use the available interaction/progress capability and repository-locked CLI without changing upstream files.
