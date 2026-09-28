# Domain models, repositories and builders

Paths are relative to `backend/`. Exemplar aggregate: `TenantRole`.

| Artifact | Exemplar |
| --- | --- |
| Domain model | `src/common/domain/models/tenants/tenant_role.py` |
| ORM model | `src/common/database/models/tenants/tenant_role.py` |
| Builder | `src/common/infrastructure/builders/tenants/tenant_role.py` |
| Repository port | `src/tenants/domain/repositories/tenant_role.py` |
| SQL adapter | `src/tenants/infrastructure/repositories/sql_tenant_role.py` |
| Soft-delete adapter | `src/tenants/infrastructure/repositories/sql_tenant.py` |

## Domain model

- Pydantic model composed from `src/common/domain/entities/mixins/`
  (`BaseModelMixin`, `TimestampMixin`, `TenantMixin`, …). Enum fields use domain
  enums, never raw strings. Behavior that depends only on the entity lives on it.
- Configuration uses Pydantic v2 `model_config = ConfigDict(...)`
  (`src/common/domain/mixins/entities.py`, `src/common/domain/models/user.py`).
  Known debt: `src/common/domain/entities/common/error_feedback.py` keeps v1
  `class Config`; do not copy it.
- The entity exposes the dict of ORM column values the adapter writes. New models
  name it `to_persist_dict`; installed variants (`persist_dict`, `persist_data`)
  stay as they are unless the change touches them. Adapters never call
  `model_dump()` to persist.

## ORM model

- Lives only in `src/common/database/models/`; extends `Base` plus mixins from
  `src/common/database/mixins/`: `UUIDTimestampMixin`, `UUIDTenantTimestampMixin`
  (required `tenant_id`), `OptionalTenantTimestampMixin`, `SoftDeleteMixin`
  (`is_deleted`, no `deleted_at`).
- Enum columns are strings with `default=str(Enum.MEMBER)`, not native PG enums.
- Import new models in the models package so Alembic sees them; migration work
  belongs to [schema-change](../../schema-change/SKILL.md).

## Builder

One pure function per entity, `build_<entity>(orm) -> Entity`, that reverses the
persist dict (string columns → `Enum.from_value(...)`). Shared entities keep their
builder in `src/common/infrastructure/builders/`; module-private ones stay in the
module.

## Repository port

`<Entity>Repository(ABC)` in the owning module's `domain/repositories/`. All
methods are `async`, take and return domain values or `Page[T]`, and never expose
ORM rows. The usual set is `find`, `find_by_*`, `filter`, `filter_paginated`,
`persist`, `delete`; add only what a use case needs.

## SQL adapter

- `@dataclass class SQL<Entity>Repository(<Entity>Repository)` with a single
  `session: AsyncSession` field; `build_async_domain` creates it per request.
- Reads return `build_<entity>(orm)` or `None`.
- `persist` upserts by `uuid`: load with `session.get`, update in place with
  `override_dict_properties(orm, entity.to_persist_dict)` or add a new ORM row,
  then `flush` + `refresh` and return the built entity.
- Every write, including `get_or_create` and deletes, runs inside
  `atomic_transaction(session)` (`src/common/infrastructure/helpers/database.py`).
  The outermost block commits on exit and rolls back on error; a nested block uses
  a savepoint, so an outer failure also undoes it. Never call `session.commit()`
  directly (`tests/common/test_architecture.py` rejects it). Reads do not open it.
- A write that only calls `flush()` is a bug: the request session closes without
  committing, so the row disappears unless a later write happens to commit.
- CPU-bound work such as password hashing runs before opening the transaction and
  through the async helpers in `src/common/infrastructure/helpers/password.py`.
- Each outermost repository call commits independently. Sharing the request session does not
  make two repository calls atomic; cross-repository atomicity needs an explicit
  transaction interface in infrastructure.
- Load relations a builder reads with `selectinload` or `refresh(orm, [...])`;
  a lazy load in async code raises `MissingGreenlet`.

## Soft delete and tenant scope

- Tables with `SoftDeleteMixin` exclude `is_deleted` rows on every read
  (`sql_tenant.py`) and are deleted by setting the flag and persisting, never
  `session.delete()` (`src/tenants/application/use_cases/tenant/soft_deleter.py`).
  Hard delete is for tables without the mixin.
- Tenant-scoped queries receive `tenant_id` explicitly and filter on it; there is
  no global tenant filter. See [auth-multi-tenant.md](auth-multi-tenant.md).

## Wiring a new aggregate

Domain model → ORM model → builder → port → SQL adapter → field on
`DomainContext` and construction in `build_async_domain`
([dependency-injection.md](dependency-injection.md)) → Alembic revision through
schema-change.

## Common mistakes

- Returning an `*ORM` from a public repository method.
- Persisting with `model_dump()` instead of the entity's persist dict.
- `session.delete()` on a soft-delete table, or a list query without `is_deleted` filtering.
- A tenant-scoped query without its `tenant_id` filter.
- Adding a repository to `DomainContext` but not to `build_async_domain`, or the reverse.
