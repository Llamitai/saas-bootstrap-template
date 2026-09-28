---
description: Reproduce and fix a bug through the project workflows
---

Bug: $ARGUMENTS

1. Use the verify-change skill to reproduce the bug and add a regression test that
   fails for the expected reason.
2. Fix it with backend-change or frontend-change (red -> green -> refine). New or
   changed behavior goes back to define-change first.
3. Run the checks that docs/content/docs/equipo/verificacion.md selects for the impact and
   report commands, exit codes and anything left unverified.

Do not create issues, branches, commits, pushes or pull requests unless the user
asks for them.
