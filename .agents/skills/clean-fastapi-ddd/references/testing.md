# Architectural test interfaces

Tests exercise the interface exposed by the layer whose behavior is changing.
This reference identifies that interface; [verify-change](../../verify-change/SKILL.md)
owns verification selection and evidence, with its [Python guidance](../../verify-change/references/python.md)
and python-testing for pytest syntax, fixtures, assertions and test-file placement.

| Layer | Interface to exercise | Collaborators / observed result |
| --- | --- | --- |
| Domain | Entity behavior or a pure domain function | Domain values and invariants; no database or HTTP framework |
| Application | UseCase.execute() | Injected repository/service interfaces; observable outcome and domain failures |
| Infrastructure | Repository or adapter interface | Real PostgreSQL for SQL behavior; persisted values, constraints and rollback may be asserted directly |
| Presentation | HTTP endpoint and consumed response | Request validation, status/envelope and active authorization; a shared BFF contract needs its real consumer |

A pure domain test and a repository integration test have different resource
requirements even when a recipe groups both under a non-API selector. The
verification guide defines that recipe's environment; this map does not redefine it.

When tenancy is active, repository and HTTP tests include allowed and wrong-scope
cases. When the affected capability is absent, do not create tenant/worker/storage
fixtures merely because an example has them. Never replace required PostgreSQL
behavior with a silent SQLite fallback or treat a missing service as passing.

For migration history and data evolution, use [schema-change](../../schema-change/SKILL.md).
ORM create_all fixtures do not exercise the Alembic chain. See [repositories.md](repositories.md)
for the persistence interface and [use-cases.md](use-cases.md) for application composition.
