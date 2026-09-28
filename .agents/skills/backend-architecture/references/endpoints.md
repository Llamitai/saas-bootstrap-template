# Endpoints, requests, presenters and routers

Paths are relative to `backend/`. Presentation is thin: authorize, read the request,
call a use case or bus, present, return `ApiJSONResponse`.

| Pattern | Exemplar |
| --- | --- |
| List + create with permission checks | `src/tenants/presentation/endpoints/tenant_roles.py` |
| Endpoint using `AppContext` and a cross-module use case | `src/tenants/presentation/endpoints/tenant_user.py` |
| Async command dispatch (202) | `src/tenants/presentation/endpoints/settings/soft_deleter.py` |
| Presenter | `src/tenants/presentation/presenters/tenant_role.py` |
| Router with `add_api_route` | `src/tenants/presentation/router.py` |
| Router composition | `config/router.py` |
| Admin API key guard | `src/admin/presentation/endpoints/hash_directus_api_key.py` |

## Requests

- Request DTOs normally subclass `CamelCaseRequest`
  (`src/common/domain/entities/common/requests.py`), defined in the endpoint file.
  It snake-cases nested keys, strips strings and ignores extra fields; the
  `CamelCaseToSnakeCaseMiddleware` also converts inbound bodies.
- Some installed DTOs subclass plain `BaseModel` and `auth` keeps a `requests/`
  folder; follow the module you are changing.
- Map request fields explicitly into the use case or message; there is no
  `to_command()`/`to_params()` convention.
- List filters are `ListFilters` subclasses injected with `Depends()` (see
  [pagination.md](pagination.md)).
- The middleware snake-cases every key of a JSON body, recursively, including
  opaque dicts (metadata, settings blobs). A payload whose keys must survive
  verbatim needs a list of pairs or a dedicated decision, not a plain dict.
- The middleware does not touch query parameters. A multi-word query field needs
  `Field(alias="camelName")`/`Query(alias=...)`, as `TenantUserFilters` does for
  `tenantIds`/`excludeIds` (`src/common/domain/filters/tenants/tenant_user.py`).
- Partial updates: `model_dump(exclude_none=True)` cannot clear a field. When an
  explicit `null` must clear a value, use `exclude_unset=True` alone and let the
  use case accept `None`.

## Handler

- One async function per route. Tenant-scoped routes inject the required tenant
  user and call `check_tenant_permission(current_tenant_user, permissions=[...])`
  first.
- New endpoints use the `Annotated` aliases (`current_tenant_user:
  RequiredTenantUserDep`, `domain_context: DomainContextDep`, …; see
  [dependency-injection.md](dependency-injection.md)), as in
  `src/tenants/presentation/endpoints/settings/updater.py`. Existing
  `= Depends(...)` parameters stay until the endpoint is otherwise changed.
- Take the tenant scope from `required_tenant_for(current_tenant_user)`, never from
  the body, query or a path id. A path id for a tenant-owned entity is checked
  against that scope by the use case (see [auth-multi-tenant.md](auth-multi-tenant.md)).
- Build the use case inline with dependencies from `DomainContext`, `BusContext`
  or `AppContext` ([dependency-injection.md](dependency-injection.md)). Same-module
  CRUD uses a use case; buses are for cross-module or deferred work.
- Let `DomainError` propagate to the global handlers.

## Presenters and responses

- A presenter is a `@dataclass` with an `instance` field and a `to_dict` property
  implementing `Presenter[T]`. Keys are snake_case; use the `optional_*` helpers in
  `src/common/application/helpers/` for nullable values. One entity may have several
  presenters.
- Return `ApiJSONResponse(content=..., status_code=...)`
  (`src/common/infrastructure/responses/api_json.py`). It wraps content as
  `{data, timestamp}`, a `Page` as `{data, pagination, timestamp}`, adds `timestamp`
  to error dicts and camelCases every key. Wrap an opaque payload in `RawJson`
  (`src/common/application/helpers/json_encoder.py`) to embed it without key
  conversion.
- `ApiJSONResponse` skips the envelope for a dict containing `errors` (treated as
  an error body) or containing both `data` and `timestamp`. Do not return business
  dicts with an `errors` key.
- Blocking or CPU-bound calls (boto3, bcrypt, image processing) never run on the
  event loop: the adapter wraps them in `asyncio.to_thread`, as the async
  `StorageService` port (`src/assets/domain/services/storage.py`) and the password
  helpers do. Ruff's ASYNC rules do not detect these libraries.
- Paginated responses call `page.apply_presenter(Presenter)`, which returns a new
  `Page`; return that value.

## Routers

- Each module router is an `APIRouter(prefix=..., tags=[...])` with routes
  registered by `add_api_route(path, endpoint, methods=[...], summary=...)`; route
  dependencies such as rate limits go in `dependencies=[...]`.
- Every route declares `response_model` and its real `status_code`. The model
  documents the wire format only: `Envelope[T]` for `{data, timestamp}` and
  `PageEnvelope[T]` for a `Page` (`src/common/presentation/schemas/envelopes.py`),
  with item schemas named `*Response` in the module's `presentation/schemas.py`
  and based on `ApiSchema` (camelCase aliases). The endpoint still returns
  `ApiJSONResponse`, which FastAPI does not revalidate, so keep the presenter and
  the schema in step (`tests/**/test_response_schemas.py`). Request DTOs extend
  `CamelCaseRequest` so the schema shows camelCase while `model_dump()` stays
  snake_case. After changing either, refresh the snapshot with openapi-sync.
- Unauthenticated routes (login, registration, reset) add a rate limit with
  `create_rate_limit_dependency` in `dependencies=[...]`.
- Register the router once in `config/router.py` under `/v1`. operationIds are
  generated as `<first tag>-<endpoint function name>`, so endpoint function names
  must be unique within a tag.

## Common mistakes

- Skipping `check_tenant_permission`, or trusting a tenant id from the request.
- Returning an entity or `model_dump()` instead of a presenter.
- Wrapping content in `{data: ...}` manually.
- Discarding the result of `apply_presenter`.
- Using `@router.get(...)` decorators instead of `add_api_route`
  (`tests/common/test_architecture.py` rejects them).
- Declaring a function parameter the endpoint does not read: FastAPI publishes it
  as a query parameter.
