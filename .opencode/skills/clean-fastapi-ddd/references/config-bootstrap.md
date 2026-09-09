# Config & Bootstrap

Applicability: paths are relative to backend/. Read the project profile and matching implementation first. Tenant, bus, pagination, job and deployment-mode examples apply only to active capabilities; do not add modes/services or remove installed authorization from these examples.

Boot order: `configure_logging()` → `init_monitoring()` → build `app` (`config/main.py`)
→ `lifespan` startup → routers (`config/router.py`) → middlewares → exception handlers.
Worker process is separate: `config/tasks.py` (`worker_settings`).

## Settings — `src/common/settings.py`

Single `settings = Settings()` instance at module bottom. `BaseSettings` (pydantic-settings),
`case_sensitive=True`, `extra="ignore"`, `env_ignore_empty=True`. Enums come from
`src.common.domain.enums.common` (`AppMode`, `Environment`, `ProcessLabel`, `Stage`) — NOT defined here.

Connection strings are `@computed_field` properties built from parts (host/port/user/password/db),
not a single DSN field — this keeps each piece typed and overridable in tests:

```python
POSTGRES_HOST: str; POSTGRES_PORT: int
POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
DB_POOL_SIZE: int = 20; DB_MAX_OVERFLOW: int = 30
REDIS_HOST / REDIS_PORT / REDIS_USER / REDIS_PASSWORD / REDIS_DB

@computed_field
@property
def async_database_url(self) -> MultiHostUrl:   # postgresql+asyncpg (app)
def database_url(self) -> MultiHostUrl:          # postgresql+psycopg (migrations/sync)
def redis_url(self) -> str:                      # auth in prod only
def all_cors_origins(self) -> list[str]:         # from CORS_ORIGINS, trailing / stripped
```

Other key fields: `DEBUG: bool = False`, `THROTTLE_ENABLED`,
`STAGE`, `ENVIRONMENT`, `PROCESS_LABEL`, JWT (`JWT_SECRET_KEY` defaults to `secrets.token_urlsafe(32)`),
monitoring keys, and one config block per external service you wire in (object store, SMTP,
and any third-party API your modules call). CORS env is `CORS_ORIGINS` (comma-string or list,
via `parse_items` `BeforeValidator`).

Rules:
- Read config ONLY through `from src.common.settings import settings`. Never `os.environ`.
- Every env var is a typed field on `Settings`; add new ones there.
- Secrets default to random tokens so dev boots; production must set real values.
- A `settings.monitoring_enabled` flag gates error reporting (off when `ENVIRONMENT.is_local`).

## Lifespan — `config/lifespan.py`

`@asynccontextmanager async def lifespan(app)`. Everything created here is stashed on
`app.state` and read by the DI chain (`src/common/infrastructure/dependencies/common.py`).

```python
database_config = get_database_config()                 # src.common.database.config
if settings.DEBUG:
    register_query_counter(database_config.engine)
redis_client = Redis.from_url(settings.redis_url, decode_responses=True, encoding="utf-8")
saq_queue = Queue.from_url(settings.redis_url)

app.state.database_config = database_config
app.state.redis_client    = redis_client
app.state.saq_queue       = saq_queue
yield
# SHUTDOWN: disconnect SAQ, close any singleton HTTP clients (object store / external APIs),
# then the DB engine and Redis. Guard external-client closes with try/hasattr.
await saq_queue.disconnect()
await database_config.dispose()                # NOT engine.dispose()
await redis_client.aclose()
```

`DatabaseConfig` (a `@dataclass`) builds the `AsyncEngine` + `async_sessionmaker` in `__post_init__`
(`pool_pre_ping=True`, `pool_size`/`max_overflow` from settings, `pool_recycle=3600`,
`expire_on_commit=False`). Per-request sessions come from `database_config.session_maker()`.

## App factory — `config/main.py`

Module-level (no factory function): `configure_logging()`, `init_monitoring()`, then `app = FastAPI(...)`.

```python
app = FastAPI(
    title=settings.PROJECT_NAME, description=settings.DESCRIPTION, version=settings.VERSION,
    docs_url="/api/py/docs", openapi_url="/api/py/openapi.json",
    lifespan=lifespan, default_response_class=CamelCaseJSONResponse, redirect_slashes=True,
)
app.include_router(api_router)
```

Middleware (added inner→outer; CORS added last = runs first):

```python
app.add_middleware(CORSMiddleware, allow_origins=settings.all_cors_origins, ...)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CamelCaseToSnakeCaseMiddleware)   # request body camel→snake before validation
app.add_middleware(RequestTrackingMiddleware)        # request_id
app.add_middleware(RateLimitHeadersMiddleware)
if settings.DEBUG:           app.add_middleware(QueryCountMiddleware)
if settings.THROTTLE_ENABLED: app.add_middleware(ThrottlingMiddleware, rate_per_ip=..., ...)
```

Exception handlers (see `errors.md`):

```python
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(RateLimitExceededError, rate_limit_exception_handler)
```

## Router composition — `config/router.py`

The composition root includes common health routes and the feature routers for the
active service. The installed router is single-mode; it does not need SERVER_MODE:

```python
from src.tenants.presentation.router import tenant_router

api_router.include_router(tenant_router, prefix="/v1", tags=["tenants"])
```

A project with an existing deployment-mode contract may condition this composition
on its configured modes. Changing topology belongs to that project's operational
design; do not add mode branches from a reference example.

## SAQ worker — `config/tasks.py`

Separate process: `saq config.tasks.worker_settings`. Does NOT import `app`.

```python
worker_settings = {
    "queue": Queue.from_url(settings.redis_url),
    "functions": [handle_command],          # single generic dispatcher
    "cron_jobs": _cron_jobs,                 # only the schedules enabled by the active profile
    "concurrency": _calculate_concurrency(), # = DB_POOL_SIZE + DB_MAX_OVERFLOW
    "startup": startup, "shutdown": shutdown,
}
```

- `startup` initializes worker monitoring and puts `ctx["db_config"] = get_database_config()`.
- `handle_command(ctx, *, command_data)` opens `db_config.session_maker()`, builds a fresh bus
  (`build_async_bus(session, domain=build_async_domain(session))`), and runs `AsyncTaskResolver`.
- Cron jobs dispatch async commands (e.g. `ExportProjectsCommand`) through that bus on a schedule.
- See `background-jobs.md` for the enqueue side; `cqrs-buses.md` for the bus build.

## Response / request shapes

```python
# src/common/infrastructure/responses/camel_case.py
class CamelCaseJSONResponse(FastAPIJSONResponse):   # default_response_class on the app
    def render(self, content): return self.json_dumps(jsonable_encoder_camel(content), ...).encode()

# src/common/infrastructure/responses/api_json.py — wraps body in ApiResponse envelope
class ApiJSONResponse(CamelCaseJSONResponse):
    # Page  -> {data: items, pagination, datetime}
    # else  -> {data: content, datetime}; dict with "errors" -> adds datetime
```

`ApiResponse` lives in `src/common/domain/entities/common/`. Incoming JSON is converted
camelCase→snake_case by `CamelCaseToSnakeCaseMiddleware` before validation.

## Monitoring — `config/monitoring.py`

`init_monitoring()` (API, gated by `settings.monitoring_enabled`) and a worker variant for the
SAQ process. Wire your error-reporting / APM integrations here; `server_name=settings.PROCESS_LABEL.value`.

## Runtime configuration ownership

The [project profile](../../../../docs/internal/project-profile.md) defines active
services and setup. The [verification guide](../../../../docs/internal/verification.md)
owns command selection and test environments. This reference describes composition
and lifecycle; it does not prescribe a development, migration or pre-commit sequence.

API and worker processes may share typed settings while constructing their own
contexts. Only provision PostgreSQL, Redis, storage or SMTP when the active profile
requires them. Read service addresses from settings rather than fixing ports in code.

## Common mistakes

- Reading env outside `settings` (e.g. `os.environ`) — breaks test overrides and the typed contract.
- Reaching for a single DSN field — there isn't one; use `settings.redis_url` /
  `settings.async_database_url` (and `database_url` for migrations/sync).
- Calling `database_config.engine.dispose()` on shutdown — use `database_config.dispose()`.
- Creating Redis/SAQ clients per request — build once in `lifespan`, read from `app.state`
  via the DI helpers in `dependencies/common.py`.
- Returning a plain dict and expecting an envelope — `default_response_class` is
  `CamelCaseJSONResponse` (camelizes but does NOT wrap); use `ApiJSONResponse` for the `data`/`pagination` envelope.
- Adding deployment modes or services solely to match an illustrative bootstrap.

See also: `dependency-injection.md` (app.state → Depends chain), `errors.md` (handlers),
`background-jobs.md` + `cqrs-buses.md` (SAQ worker), `pagination.md` (Page envelope).
