# Configuration and composition root

Paths are relative to `backend/`. The API and the worker are separate processes
that share typed settings and builders but construct their own contexts.

| Piece | Location |
| --- | --- |
| Settings (`settings = Settings()`, computed `database_url`, `async_database_url`, `redis_url`, `rabbitmq_url`, `all_cors_origins`, secret validation) | `src/common/settings.py` |
| Engine and session factory (`DatabaseConfig`, `get_database_config`) | `src/common/database/config.py` |
| Lifespan: database config, Valkey client and command enqueuer on `app.state` | `config/lifespan.py` |
| Valkey/Redis client factory (bounded, health-checked pool) | `src/common/infrastructure/redis_client.py` |
| RabbitMQ connection and topology | `src/common/infrastructure/rabbitmq/` |
| App, middlewares, exception handlers | `config/main.py` |
| Router composition | `config/router.py` |
| Error reporting (`init_sentry`) | `config/monitoring.py` |
| Worker | `config/worker.py` (`python -m config.worker`) |
| Logging | `src/common/application/logging/config.py` |

## Rules

- Read configuration only through `from src.common.settings import settings`;
  every environment variable is a typed field there. Never read `os.environ`.
- Connection strings are computed from parts; there is no single DSN field. Use
  `async_database_url` for the app and `database_url` for sync/migrations.
- Create long-lived clients once in the lifespan and read them from `app.state`
  through dependencies; release them on shutdown (`rabbitmq.close()`,
  `database_config.dispose()`, `redis_client.aclose()`).
- `build_async_domain(session, redis_client)` receives the lifespan (or worker)
  client from `create_redis_client(settings)`, created with
  `decode_responses=True`; token-store keys depend on receiving `str`. Never
  build a Valkey client per request. Valkey (Redis protocol) keeps the `redis`
  hostname and `REDIS_*` settings.
- The lifespan connects to RabbitMQ at startup and fails fast when it is
  unreachable; `build_async_bus` receives the process-wide enqueuer.
- `default_response_class` is `CamelCaseJSONResponse`, which camelCases but does
  not add the `data` envelope; endpoints return `ApiJSONResponse` for that.
- Middlewares: security headers, camelCase → snake_case request bodies, request
  tracking, rate-limit headers and CORS. Exception handlers are registered for
  `DomainError`, `HTTPException`, `RequestValidationError` and rate limits.
- OpenAPI docs are served under `/api/py/docs` outside production.
- New feature routers are included in `config/router.py` under `/v1`; the
  composition has no deployment modes. Do not add modes or services to match an
  example; the project profile decides which services are active.

## Common mistakes

- Reading environment variables outside `settings`.
- Creating Valkey, RabbitMQ or HTTP clients per request.
- Returning a plain dict and expecting the `data` envelope.
- Calling `engine.dispose()` directly instead of `database_config.dispose()`.
