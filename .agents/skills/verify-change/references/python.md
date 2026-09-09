# Python verification

Use python-testing for async pytest, AAA, expects, autospec and fixtures. Pure domain tests use ports; PostgreSQL repository integration may assert stored rows, constraints and rollback directly. The unit selector excludes API but may require DB. Never fall back silently to SQLite or skip missing PostgreSQL.

For a coverage request, choose the source module and matching tests first, then
use the existing pytest-cov dependency through the project runner, for example:

```bash
just backend test unit tests/tenants --cov=src.tenants --cov-report=term-missing
```

Choose the API selector for HTTP tests. Read uncovered branches against the
requested behavior, add meaningful examples using expects, and rerun the same
selection. Report source/test scope and remaining gaps. A numerical target is a
gate only when the task or project requires it; do not expand to repository-wide
100% coverage or add tests that merely mirror implementation.
