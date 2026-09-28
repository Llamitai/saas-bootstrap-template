# Layers and ownership

Paths are relative to `backend/`. The import-linter contracts in `pyproject.toml`
are the enforced version of this reference; `just backend check` runs them.

## Dependency direction

`presentation → infrastructure → application → domain`. Each layer is optional
per module, but no layer imports one to its left.

| Layer | May import | Must not import |
| --- | --- | --- |
| `domain` | stdlib, pydantic, other domain code | any `application`, `infrastructure`, `presentation`, `src.common.database`, SQLAlchemy, FastAPI/Starlette |
| `application` | domain, message classes in `src/common/application/commands|queries` | infrastructure, presentation, `src.common.database`, SQLAlchemy, FastAPI/Starlette |
| `infrastructure` | domain, application, SQLAlchemy, Valkey (redis-py), aio-pika, boto3, vendor SDKs | presentation |
| `presentation` | everything above, FastAPI | — |

`src/common/domain/models` must not import any feature module. The only audited
exception is `src.common.application.helpers.json_encoder -> fastapi`.

## Module shapes

Copy the shape of an installed module; do not create layers to complete a tree.

- **Full module** (`auth`, `tenants`, `users`): `domain/repositories/` ports,
  `application/use_cases/<subject>/`, `application/command(s)/` and
  `application/queries/` bus handlers, `infrastructure/repositories/sql_*.py`,
  `infrastructure/bus_wiring.py`, `presentation/endpoints|presenters|router.py`.
- **Thin module**: `profile` has only presentation over other modules' use cases;
  `admin` owns the API-key port used by `DomainContext`; `assets` is a storage port
  plus adapters; `messaging` keeps the email port, its SMTP adapter and handler.
- **Shared kernel** `common`: no feature business logic, but shared domain types,
  bus contracts, contexts, builders, dependencies, responses and middlewares.

## Where each artifact lives

| Artifact | Location | Example |
| --- | --- | --- |
| ORM model (always central) | `src/common/database/models/[area]/` | `TenantRoleORM` in `models/tenants/tenant_role.py` |
| Shared domain model | `src/common/domain/models/` | `TenantRole` in `models/tenants/tenant_role.py` |
| Shared value/entity types, mixins | `src/common/domain/entities/` | `entities/mixins/common.py`, `entities/common/pagination.py` |
| Builder ORM → domain | `src/common/infrastructure/builders/` | `build_tenant_role` |
| Repository port | `src/<module>/domain/repositories/` | `TenantRoleRepository` |
| SQL adapter | `src/<module>/infrastructure/repositories/sql_*.py` | `SQLTenantRoleRepository` |
| Use case | `src/<module>/application/use_cases/<subject>/<action>.py` | `role/creator.py` → `TenantRoleCreator` |
| Command/query message | `src/common/application/commands|queries/[area].py` | `PersistTenantCommand`, `GetTenantByIdQuery` |
| Command/query handler | `src/<module>/application/command(s)|queries/` | `tenants/application/command/persist_tenant.py` |
| Bus wiring | `src/<module>/infrastructure/bus_wiring.py` | `tenants_wiring(domain, bus)` |
| Domain error | shared: `src/common/domain/exceptions/[area].py`; module-private: `src/<module>/domain/exceptions.py` | `TenantRoleNotFoundError`, `auth` errors |
| Presenter | `src/<module>/presentation/presenters/` or `src/common/presentation/presenters/` | `TenantRolePresenter` |
| Router | `src/<module>/presentation/router.py` | `tenant_router` |

Promote a concept to `src/common/` when a second module needs it. Migrations live
in `src/common/database/versions/` regardless of owner. Tests mirror source under
`tests/<module>/`; HTTP tests live in `tests/api/`.

## Base types

- `UseCase` (`src/common/domain/interfaces/use_case.py`): ABC with `async execute()`.
- `Presenter` (`src/common/domain/interfaces/presenter.py`): `Protocol[T]` with a
  `to_dict` property.
- `DomainError` (`src/common/domain/exceptions/_base.py`): `code`, `message`,
  `status_code`, `context`.
- Domain mixins: `src/common/domain/entities/mixins/` (`BaseModelMixin` gives a
  uuid7 `uuid`; `TimestampMixin`; `TenantMixin`/`OptionalTenantMixin`; person mixins).
- ORM mixins: `src/common/database/mixins/` (`UUIDTimestampMixin`, `SoftDeleteMixin`,
  `UUIDTenantTimestampMixin`, `OptionalTenantTimestampMixin`).
- `CamelModel`/`SnakeModel`: `src/common/domain/mixins/entities.py`.

## Common mistakes

- Importing SQLAlchemy or a session in `application/` → move the query into a repository.
- Putting bus handlers in `infrastructure/`: handlers are application code; only
  their wiring is infrastructure.
- Creating an empty layer or a `requests/`/`queries/` folder a module does not use.
- Placing a shared concept inside one module, or a module-private one in `common`.
