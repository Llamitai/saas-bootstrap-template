# Layers & file conventions

Applicability: paths are relative to backend/. Read the project profile and matching implementation first. Tenant, bus, pagination, job and deployment-mode examples apply only to active capabilities; do not add modes/services or remove installed authorization from these examples.

## The 4 layers (dependencies point inward)

```
Domain         (entities, repo ABCs, exceptions, filters, enums, service ifaces, interfaces)
   ▲
Application    (use cases, command/query message classes, helpers)
   ▲
Infrastructure (SQL repos, builders, bus handlers + wiring, providers, DI deps)
   ▲
Presentation   (endpoints, presenters, router, requests)
```

## Allowed imports

| Layer | May import |
|---|---|
| `domain` | stdlib + pydantic only — no sqlalchemy/fastapi imports anywhere under `src/*/domain` or `src/common/domain` |
| `application` | `domain` (+ stdlib, pydantic) |
| `infrastructure` | `domain` + `application` + libs (SQLAlchemy, redis, boto3, saq, vendor SDKs…) |
| `presentation` | all of the above + fastapi |

If you import SQLAlchemy from `application/`, you took a wrong turn — push the SQL into a repo. The one bend: use cases (`application/`) may import message classes from `src/common/application/commands|queries` to dispatch through buses.

## Where artifacts actually live — shared vs per-feature

ORM models live centrally in `src/common/database/models/`. Shared domain concepts
and their builders live in the shared core; module-private domain concepts remain
with their feature. Repository interfaces, use cases, SQL adapters and presentation
belong to the owning module. Copy its required shape: thin modules do not acquire
extra layers merely to match the full-module example below.

```
src/[bounded_context]/
├── domain/
│   ├── repositories/    # abstract base classes (ABC) — e.g. ProjectRepository
│   └── enums/           # feature-only enums (most enums live in common)
├── application/
│   ├── use_cases/[entity_plural]/   # creator.py, getter.py, lister.py, mixins.py …
│   └── helpers/
├── infrastructure/
│   ├── repositories/    # sql_*.py implementing the ABCs (class SQL*Repository)
│   ├── commands/        # CommandHandlers (one file per command)
│   ├── queries/         # QueryHandlers (one file per query)
│   ├── helpers/
│   ├── <provider>/      # provider-specific adapters, only if the feature integrates one
│   └── bus_wiring.py    # def [bounded_context]_wiring(domain, bus)
└── presentation/
    ├── endpoints/       # async functions, grouped by entity
    ├── presenters/      # @dataclass impl of Presenter[T]
    └── router.py        # APIRouter(prefix=…, tags=[…]) + add_api_route(...)
```

`src/common/` holds the shared core (see bottom). Shared domain concepts and their
builders live there; module-private entities, filters, exceptions and ports stay
in their owning module. All ORM models remain central in `common/database/models`.

## Naming conventions

| Thing | Convention | Example / location |
|---|---|---|
| Shared domain entity | PascalCase `BaseModel` | `Tenant` — `src/common/domain/models/tenants/tenant.py` |
| ORM model | suffix `ORM` | `ProjectORM` — `src/common/database/models/projects/project.py` |
| Repository interface | `*Repository(ABC)` | `ProjectRepository` — `src/[bounded_context]/domain/repositories/` |
| Repository SQL impl | `SQL*Repository`, `@dataclass`, field `session: AsyncSession` | `SQLProjectRepository` — `src/projects/infrastructure/repositories/sql_project.py` |
| Builder (ORM→entity) | `build_<entity>(orm_instance, …) -> Entity` | `build_project` — `src/common/infrastructure/builders/projects/project.py` |
| Use case | `<Entity><Verb>`, file = verb | `ProjectCreator` in `…/use_cases/projects/creator.py`; also `Getter`/`Lister`/`Updater`/`Deleter`/`Archiver` |
| Command message | `*Command` | `ArchiveProjectCommand` — `src/common/application/commands/projects.py` |
| Command handler | `*Handler` or `*CommandHandler` | `ArchiveProjectHandler` — `src/projects/infrastructure/commands/` |
| Query message | `*Query` | `GetProjectByIdQuery` — `src/common/application/queries/projects.py` |
| Query handler | `*Handler` | `GetProjectByIdHandler` — `src/projects/infrastructure/queries/` |
| Bus wiring fn | `[bounded_context]_wiring(domain, bus)` | `projects_wiring` — `src/projects/infrastructure/bus_wiring.py` |
| Exception | `*Error(DomainError)` | `ProjectNotFoundError` — `src/common/domain/exceptions/projects.py` |
| Error code | `"{module}.{ErrorName}"` | `"projects.ProjectNotFoundError"` |
| Filters | `*Filters(ListFilters)` (pydantic) | `ProjectFilters` — `src/common/domain/filters/projects/project.py` |
| Presenter | `*Presenter(Presenter[T])` `@dataclass` | `ProjectPresenter` — `src/projects/presentation/presenters/` |
| Request DTO | `*Request(CamelCaseRequest)` | `CreateProjectRequest`; base in `src/common/domain/entities/common/requests.py` |

## Base classes & mixins

**Domain entity** = pydantic `BaseModel` composing mixins from `src/common/domain/entities/mixins/`:
- `common.py`: `BaseModelMixin` (`uuid: UUID = uuid7`, `from_attributes=True`, `extra="ignore"`), `TimestampMixin`, `SoftDeleteMixin` (`is_deleted: bool`)
- `tenants.py`: `TenantMixin` (required `tenant_id`), `OptionalTenantMixin`, `LocationMixin`

```python
class Project(BaseModelMixin, TimestampMixin, TenantMixin):
    name: str
    status: ProjectStatus
    @property
    def is_archived(self) -> bool: ...   # behavior lives on the entity
```

`CamelModel` / `SnakeModel` (camelCase/snake_case alias generators) live in `src/common/domain/mixins/entities.py`.

**UseCase** — `src/common/domain/interfaces/use_case.py`:
```python
class UseCase(ABC):
    @abstractmethod
    async def execute(self, *args, **kwargs) -> object | None: ...
```
Impls are `@dataclass` with repos/services as fields (constructor-injected), one public `async def execute(...)`.

**Presenter** — `src/common/domain/interfaces/presenter.py` is a `Protocol[TItem]` with `@property to_dict`. Impl: `@dataclass` with field `instance` + `to_dict`.

**DomainError** — `src/common/domain/exceptions/_base.py`: `__init__(code, message, status_code=400, context=None)`. Subclasses hardcode `code`/`message`/`status_code`.

## DB layer (`src/common/database/`)

- ORM models: `models/[area]/*.py`, class suffix `ORM`, extend `Base` + mixins from `mixins/`.
- `mixins/common.py`: `Base(DeclarativeBase)`, `UUIDPrimaryKeyModelMixin`, `TimeStampedModelMixin`, `UUIDTimestampMixin` (combines both), `SoftDeleteMixin`.
- `mixins/tenants.py`: `UUIDTenantTimestampMixin` (required `tenant_id`), `OptionalTenantTimestampMixin`, `LocationMixin`.
- SQL repos build domain entities via `build_*` from `src/common/infrastructure/builders/` and use `atomic_transaction(session)` from `src/common/infrastructure/helpers/database.py`.

## What goes in `src/common/`

Shared core every feature depends on. No feature business logic here, but shared domain types do live here.

```
src/common/
├── domain/
│   ├── models/          # domain concepts shared by modules
│   ├── entities/        # existing shared base types + mixins/
│   ├── filters/         # *Filters(ListFilters) per area
│   ├── enums/           # shared enums
│   ├── exceptions/      # _base.py = DomainError; projects.py, tenants.py, …
│   ├── buses/           # CommandBus, QueryBus, EventBus ABCs
│   ├── contexts/        # DomainContext, BusContext (@dataclass, field-per-repo/service)
│   ├── interfaces/      # UseCase, Presenter
│   ├── services/        # service interfaces: TokenService, StorageService, EventPublisher, NotificationService…
│   └── mixins/          # CamelModel, SnakeModel
├── application/
│   ├── commands/        # *Command message classes (projects.py, tenants.py, users.py, common.py)
│   ├── queries/         # *Query message classes
│   ├── filters/ helpers/ logging/ use_cases/
├── infrastructure/
│   ├── builders/        # build_*(orm) -> entity, by area
│   ├── buses/           # MemoryCommandBus/QueryBus/EventBus, SaqCommandEnqueuer
│   ├── contexts/        # mock_*_singleton (testing)
│   ├── context_builder.py   # AppContext + build (get_app_context)
│   ├── domain_builder.py    # build_async_domain (repos/services) from session
│   ├── bus_builder.py       # build_async_bus
│   ├── dependencies/    # common.py, session.py, tenant.py, rate_limit.py (FastAPI Depends)
│   ├── error_handlers.py  middlewares/  responses/  services/  helpers/
└── database/            # config.py, env.py, models/, mixins/, versions/ (Alembic), factories/
```

## Rules of thumb

- A feature owns its private domain concepts, repository interfaces, use cases, SQL adapters and any presentation/bus wiring it needs. Shared concepts go in `src/common/`; all ORM models stay central.
- Reused by ≥2 features → promote to `src/common/`.
- Tests mirror source: `tests/[bounded_context]/...`.
- Migrations live in `src/common/database/versions/` (Alembic) regardless of owning feature.
- `*.py` snake_case; classes PascalCase; `__init__.py` only re-exports public names.

## Related references
- `repositories.md` — repo ABC + SQL impl + builder details
- `use-cases.md` — use case / mixins patterns
- `cqrs-buses.md` — command/query/handler wiring through buses
- `endpoints.md` — router + endpoint + presenter
- `dependency-injection.md` — DomainContext / BusContext / AppContext deps
- `errors.md` — DomainError subclassing & HTTP mapping
