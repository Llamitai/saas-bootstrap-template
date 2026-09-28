# Backend constitution

Binding for any change under `backend/`. The root [AGENTS.md](../AGENTS.md)
still applies; this file adds the backend rules.

## Read for the task

- Use [backend/README.md](README.md) for stack, module and entry-point questions.
- For module ownership, interfaces or wiring, consult the relevant part of
  [Backend architecture](../docs/content/docs/conceptos/arquitectura-backend.mdx)
  or [backend-architecture](../.claude/skills/backend-architecture/SKILL.md). Module
  shapes and artifact locations are in
  [layers.md](../.claude/skills/backend-architecture/references/layers.md).
- Consult the [project profile](../docs/content/docs/equipo/perfil-del-proyecto.md)
  when active capabilities or public contracts matter.

## Commands

Run from the Git root: `just backend <recipe>`. Pytest paths are relative to
`backend/`; `just backend test unit|api <paths>` needs Docker and creates an
exclusive stack. `just backend check` is static without autofix;
`just backend code_quality` autofixes. HTTP contract changes refresh the API
snapshot with `just backend openapi` (openapi-sync); data changes go through
schema-change and `just backend check-migrations`.

## Architecture

- Clean Architecture/DDD: dependencies point inward. ORM models always live in
  `src/common/database/models/`; shared domain models in
  `src/common/domain/models/`. Copy the full or thin module shape from the
  profile; do not invent missing layers.
- Use cases are dataclasses implementing `UseCase.execute()`, one operation per
  file. Domain repository ports have infrastructure adapters, including when a
  single adapter exists. Keep `DomainError`, presenters, router
  `add_api_route()` and explicit DI (`DomainContext`, `BusContext`).
- Persistence: each repository write commits inside `atomic_transaction`, which
  is nest-safe (savepoints; only the outermost block commits). There is no
  request-wide transaction; never call `session.commit()`, and a flush-only
  write is lost when the session closes.
- Responses: endpoints return `ApiJSONResponse`; response classes own camelCase
  conversion; preserve `RawJson` exceptions. Every route declares
  `response_model` (`Envelope[T]`/`PageEnvelope[T]`) and its real
  `status_code`; request DTOs extend `CamelCaseRequest`.
- Blocking or CPU-bound calls (bcrypt, boto3) go through `asyncio.to_thread`.
  Unauthenticated routes carry a rate limit keyed by `client_ip()`.
- Sessions: refresh tokens use a per-session allowlist in Valkey (`sid` claim,
  `JWT_MAX_SESSIONS_PER_USER`); password change, reset or admin set closes every
  session; access-token validation stays stateless.
- Valkey holds cache and session state and fails closed; RabbitMQ carries
  deferred commands through the `CommandEnqueuer` port with at-least-once
  delivery, so asynchronous handlers must be idempotent.

## Enforced gates

A failure here is a project rule, not noise:

- `lint-imports`: register every new top-level module of `src/` in the
  `backend/pyproject.toml` contracts (layers `containers` and the shared-domain
  feature list).
- `tests/common/test_architecture.py`: contract coverage, `add_api_route` only,
  `commit()` only in the transaction helper, ORM classes under
  `src/common/database/`.
- `just backend check-migrations` (drift and upgrade path) and the OpenAPI
  snapshot check (`just backend openapi-check`).

Decisions behind these rules: ADR
[0008](../docs/content/docs/equipo/adr/0008-arquitectura-base-y-reglas-comprobadas.md)
and [0009](../docs/content/docs/equipo/adr/0009-valkey-para-cache-y-rabbitmq-para-colas.md).
