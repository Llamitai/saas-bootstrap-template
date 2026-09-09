---
name: review-change
description: Review an exact diff or pull request for actionable defects and acceptance gaps without editing files or running autofix.
---

# review-change

Establish base, exact revision/diff, acceptance, callers and relevant tests. Read only the architecture/profile relevant to the change. Review integrated backend/frontend contracts together.

Inspect active backend invariants, authorization/scopes, transactions, migrations, concurrency and effects. Inspect frontend private imports, server secrets/client transport, stale queries after mutation or scope changes, form validation, error recovery, focus/accessibility and responsive behavior. Check API/BFF status, envelopes, headers/cookies and real consumer evidence.

Use read-only searches/checks and focused reproductions on owned resources. Do not edit code or acceptance, run autofix, sync skills, publish, or claim another owner performed your review. Findings need file/line, trigger, observable impact and evidence; distinguish hypotheses from reproduced failures. A correct diff may have no findings. Green lint is not complete semantic compliance.

Return findings to backend-change/frontend-change/schema-change. The implementer refines and renews affected evidence; [validate-change](../validate-change/SKILL.md) resolves acceptance on the final combined state.
