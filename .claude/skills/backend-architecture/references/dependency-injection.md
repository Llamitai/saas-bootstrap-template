# Dependency injection

Paths are relative to `backend/`. Each request builds one graph from a single
`AsyncSession`; FastAPI memoizes each dependency within the request.

| Piece | Location |
| --- | --- |
| `DomainContext` (one field per repository/service interface) | `src/common/domain/contexts/domain.py` |
| `BusContext` (`command_bus`, `query_bus`, `event_bus`) | `src/common/domain/contexts/bus.py` |
| `AppContext` (`domain` + `bus`) and `AppContextBuilder` | `src/common/infrastructure/context_builder.py` |
| `build_async_domain(session, redis_client)` | `src/common/infrastructure/domain_builder.py` |
| `build_async_bus(session, domain, enqueuer)` | `src/common/infrastructure/bus_builder.py` |
| Request dependencies and aliases | `src/common/infrastructure/dependencies/common.py` |
| Identity and tenant dependencies | `dependencies/session.py`, `dependencies/tenant.py` |

## Request chain

`get_database_session` → `get_domain_context` → `get_bus_context` → `get_app_context`.

- Aliases: `AsyncSessionDep`, `DomainContextDep`, `BusContextDep`, `RedisClientDep`,
  `CommandEnqueuerDep`;
  identity `AuthenticatedUserDep`, `OptionalAuthenticatedUserDep`,
  `AuthenticatedSuperuserDep`; tenancy `TenantDep`, `RequiredTenantDep`,
  `TenantUserDep`, `RequiredTenantUserDep`; rate limits `RateLimit*Dep`
  (`dependencies/rate_limit.py`).
- There is no `AppContextDep`; inject `app_context: AppContext = Depends(get_app_context)`
  only when the endpoint needs both repositories and buses. Otherwise inject
  `DomainContext`/`BusContext` alone. Both styles are installed
  (`tenant_roles.py` uses the domain context, `tenant_user.py` the app context).
- `DomainContext` holds interfaces only; `build_async_domain` constructs every SQL
  adapter with the same request session and the concrete services
  (`JwtTokenService`, `S3StorageService`).
- `build_async_bus` creates the in-memory buses and calls each module's
  `<module>_wiring(domain, bus)`; a module's handlers are reachable only after its
  wiring call is added there.
- Valkey, RabbitMQ and database configuration are created once in
  `config/lifespan.py` and read from `app.state`; do not create clients per request.
  `get_bus_context` passes the lifespan's `command_enqueuer` to `build_async_bus`.
- `build_async_domain` receives the shared Redis client from `app.state` (the
  worker passes its own); new long-lived clients follow the same
  `get_redis_client`/`RedisClientDep` pattern instead of being built per request.

## Outside a request

Workers and scripts have no `Request`: open a session from `DatabaseConfig` and
call the same builders (`config/worker.py`). Operational scripts follow
[backend-change's operational-scripts reference](../../backend-change/references/operational-scripts.md).

## Adding a dependency

1. Repository/service: add the interface field to `DomainContext` and construct it
   in `build_async_domain`.
2. Bus handlers of a new module: add its wiring call to `build_async_bus`.
3. Request-scoped value: add `get_<thing>` plus an `Annotated` alias in
   `dependencies/`, composed from existing aliases so the session is shared.

## Common mistakes

- A field on `DomainContext` without its construction, or the reverse.
- Different sessions for different repositories in one request.
- Constructing handlers or SQL adapters in an endpoint instead of the builders.
- Mutable state on a context: contexts are request-scoped; state belongs in Redis/DB.
