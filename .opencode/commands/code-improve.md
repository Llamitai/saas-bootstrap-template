---
description: Behavior-preserving refactor of the given code
---

Refactor $ARGUMENTS without changing its behavior.

1. Pin the current behavior with tests first when coverage is missing (verify-change
   and tdd skills).
2. Simplify within the existing architecture boundaries (AGENTS.md): clearer names,
   less nesting, less duplication, no speculative abstractions.
3. Edit the files in place, run the affected `just backend check` /
   `just frontend check` and focused tests, and report the changes, commands and
   results.
