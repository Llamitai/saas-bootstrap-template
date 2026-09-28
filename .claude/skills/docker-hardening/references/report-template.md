# Docker hardening report template

Use this structure only when the audit requests a durable report. Match the
user's language and keep every PASS/FAIL tied to `file:line` or command output.

```markdown
# Docker Hardening Audit — <YYYY-MM-DD>

## Scope
- Repo: <path>
- Artifacts: <list>
- Tooling assumed available: <docker version output, or "not run">

## Summary
| File | A (CIS) | B (Compose) | C (Supply) | D (Daemon) | E (Profiles) | F (Monitor) |
|------|---------|-------------|------------|------------|--------------|-------------|
| backend/Dockerfile        | 8 PASS / 3 FAIL / 1 N/A / 0 MAN | — | 3/5 | — | — | — |
| backend/docker-compose.yml | — | 7/12 | — | — | — | — |
| ...                       | ... | ... | ... | ... | ... | ... |

## Findings by file

### backend/Dockerfile
- [FAIL] **A1 / CIS 4.1 — Non-root user**: no `USER` directive.
  - Evidence: `backend/Dockerfile` has no `USER` (lines 1–22).
  - Fix: see "Remediations" §CIS 4.1.
- [PASS] **A5 / CIS 4.9 — COPY over ADD**: only COPY used.
- ...

### backend/docker-compose.prod.yml
- [FAIL] **B1 — read_only**: backend service is read/write.
- [FAIL] **B3 — no-new-privileges**: missing on all services.
- ...

## Remediations
For each FAIL — concrete paste-ready diff/snippet adapted to the project's stack.

## Manual review checklist
- A10/A11: confirm base image source and CI scan presence.
- D1–D6: host audit out of scope unless host access granted.

## Recommendations (not failures)
- Consider Wolfi/Chainguard for base images (zero-CVE goal).
- Consider rootless Docker for the runtime.
```
