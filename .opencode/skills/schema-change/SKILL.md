---
name: schema-change
description: Evolve SQLAlchemy persistence, constraints, indexes, Alembic revisions or data transformations. DTO or zod-only edits do not activate this workflow.
---

# schema-change

Read the project profile, affected data criteria, central ORM models and Alembic graph. Coordinate with backend-change and consumers if HTTP contracts change.

1. Generate with `just backend new-migration "description"` when appropriate, then deliberately review SQL, FK ordering, constraints and data transforms. Autogeneration is a starting point; merge conflicting revisions through Alembic's graph workflow.
2. Test an empty database and the supported previous revision with representative data. Use `just backend check-migrations`; it owns disposable databases, upgrades and checks drift. Add data-specific preservation assertions when a migration transforms existing values. metadata.create_all and migrate-current are not migration evidence.
3. Confirm an unambiguous integrated head, model parity and preserved data. Do not require a destructive downgrade by default. Plan compatible deployment phases when API, frontend and schema do not update simultaneously.
4. Record the structural decision in an ADR and technical evidence on the exact integrated revision. Return findings to the implementer; [validate-change](../validate-change/SKILL.md) checks the evolution and compatibility acceptance. Clean only owned resources.
