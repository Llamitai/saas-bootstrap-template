# Use cases

Paths are relative to `backend/`. A use case orchestrates one operation: it takes
repository/service interfaces (and a `QueryBus` only for cross-module reads) as
fields, applies domain rules and returns a domain value, `Page` or tuple. It never
imports FastAPI, SQLAlchemy or HTTP types and raises `DomainError` subclasses,
never `HTTPException`.

| Pattern | Exemplar |
| --- | --- |
| Creator with a non-literal default | `src/tenants/application/use_cases/role/creator.py` |
| Load-or-raise mixin | `src/tenants/application/use_cases/role/mixins.py` |
| Getter, updater, deleter over the mixin | `role/getter.py`, `role/updater.py`, `role/deleter.py` |
| Lister returning `Page` | `role/lister.py` |
| Tenant ownership check through `QueryBus` | `src/users/application/use_cases/tenant_user/mixins.py` |
| Soft delete | `src/tenants/application/use_cases/tenant/soft_deleter.py` |

## Shape

- Every use case is a `@dataclass` subclassing `UseCase`
  (`src/common/domain/interfaces/use_case.py`) with one public `async execute()`.
  No hand-written `__init__`.
- Fields with defaults go last. Add `__post_init__` only for a non-literal default
  or a derived field (`creator.py` derives `icon_url`); never an empty one.
- One public use case per file. Private collaborators may live beside it or in
  `mixins.py`.

## Naming

- `[Subject][Action-agent-noun]`: `TenantRoleCreator`, `TenantSoftDeleter`,
  `InvitationAcceptor`. Never verb-first; verb-first names belong to
  `Command`/`Query` messages (`PersistTenantCommand`, `GetTenantByIdQuery`).
- The folder carries the subject, so the file is the action:
  `use_cases/role/creator.py` → `TenantRoleCreator`, `invitations/acceptor.py`.
- CRUD suffixes: `Creator`, `Getter`, `Lister`, `Updater`, `Deleter`; extend the
  same way for domain actions (`Inviter`, `Canceller`, `Onboarder`, `Bootstrapper`).

## Loading and ownership

- A mixin centralizes "load or raise" so use cases cannot skip it. It declares the
  fields it reads as annotations and the concrete dataclass supplies them.
- Tenant ownership compares the loaded entity's `tenant_id` with the scope passed
  by the endpoint and raises the entity's `NotFound` error, not `Forbidden`, so
  cross-tenant ids leak nothing (`tenant_user/mixins.py`).
- The tenant scope arrives as a field set by the endpoint from the validated
  tenant user; a use case never reads it from request data.

## Collaboration

- Same-module reads and writes use the injected repository directly; routine
  persistence is `repository.persist(entity)`, not a command.
- Cross-module reads use `query_bus.ask(...)`. Cross-module or deferred writes use
  a command (see [cqrs-buses.md](cqrs-buses.md)).
- Entities are mutated in place and re-persisted; `persist` upserts.
- `uuid7()` comes from `uuid6`; use the helpers in `src/common/application/helpers/`
  for time and ids.

## Validation boundary

| Where | Validates |
| --- | --- |
| Request DTO | Shape: required fields, types, formats, ranges (422 before the use case runs) |
| Use case and mixins | Existence, ownership, uniqueness, state transitions, cross-entity rules → `DomainError` |

## Common mistakes

- Verb-first use-case name, or several public use cases in one file.
- Returning a presenter or dict: presenters belong to presentation.
- Raising `HTTPException` or catching `DomainError` in the use case.
- `Forbidden` for another tenant's id, or skipping the ownership check.
- Dispatching a `Persist*Command` for same-module CRUD.
