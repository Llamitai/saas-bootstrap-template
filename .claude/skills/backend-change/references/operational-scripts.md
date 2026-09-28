# Operational scripts (`backend/scripts/*.py`)

Applicability: paths are relative to backend/. Read the project profile and matching implementation first. Tenant, bus, pagination, job and deployment-mode examples apply only to active capabilities; do not add modes/services or remove installed authorization from these examples.

One-off / operational tasks run OUTSIDE the request cycle: backfills, recalculations, bootstrappers, re-syncs. They reuse domain repos / use-cases / buses — never raw SQL for writes when a use-case exists.

Patterns a script falls into:
- **Dry-run/apply backfill** — read rows, log `would_*`, mutate through repositories (whose writes commit) only under `--apply`.
- **Per-tenant bootstrapper** — iterate tenants, run a use-case once per tenant.
- **Full-domain task** — build the wired `build_async_domain`/`build_async_bus`, use per-item sessions, optionally a CSV report.
- **Interactive task** — `typer.prompt`/`confirm`, no `--apply` (the prompt is the safety gate).

Keep external-integration helpers (raw `httpx` + stdlib `logging` + `dotenv`) separate from this DB pattern — don't copy them for DB work.

## Skeleton (copy-paste)

```python
"""
<One-line what + why>.

Usage:
    python scripts/<name>.py                       # dry run (all)
    python scripts/<name>.py --apply               # apply
    python scripts/<name>.py --tenant-id <uuid>    # filter
"""

import asyncio
from typing import Annotated
from uuid import UUID

import typer
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.application.logging import get_logger
from src.common.database.config import get_database_config

logger = get_logger(__name__)


async def dry_run(session: AsyncSession, tenant_id: UUID | None) -> None:
    # read + log "would_*" events; NEVER commit
    logger.info("dry_run.start")
    ...
    logger.info("dry_run.done", would_change=0)


async def apply_changes(session: AsyncSession, tenant_id: UUID | None) -> None:
    logger.info("apply.start")
    updated = 0
    # Mutate only through existing use cases/repositories: each write commits
    # inside atomic_transaction. Never call session.commit() here.
    logger.info("apply.done", updated=updated)


async def run(should_apply: bool, tenant_id: UUID | None = None) -> None:
    db_config = get_database_config()
    try:
        async with db_config.session_maker() as session:
            if should_apply:
                await apply_changes(session, tenant_id)
            else:
                await dry_run(session, tenant_id)
    finally:
        await db_config.dispose()
    logger.info("finished", mode="apply" if should_apply else "dry_run")


app = typer.Typer()


@app.command()
def main(
    apply: Annotated[bool, typer.Option(help="Apply changes (default is dry run)")] = False,
    tenant_id: Annotated[str | None, typer.Option(help="Filter by tenant UUID")] = None,
) -> None:
    asyncio.run(run(should_apply=apply, tenant_id=UUID(tenant_id) if tenant_id else None))


if __name__ == "__main__":
    app()
```

## Worked example — installed `scripts/bootstrap_tenant_roles.py`

The installed exemplar is a per-tenant bootstrapper: it opens a session from
`DatabaseConfig`, selects non-deleted tenants (optionally one `--tenant-slug`),
and runs `TenantRolesBootstrapper` per tenant through `SQLTenantRoleRepository`;
the repository's `persist` commits each role. It predates two skeleton
conventions (it prints with `typer.echo` and has no dry run), so copy its session
bootstrap and use-case reuse, not its output style.

A dry-run companion for the same domain reads through the port and logs
`would_*` events without writing:

```python
from src.common.domain.enums.tenants import TenantRoleStatus
from src.common.domain.permissions.roles import DEFAULT_TENANT_ROLES
from src.tenants.application.use_cases.role.bootstrapper import TenantRolesBootstrapper
from src.tenants.infrastructure.repositories.sql_tenant_role import SQLTenantRoleRepository


async def dry_run(session: AsyncSession, tenant_ids: list[UUID]) -> None:
    role_repository = SQLTenantRoleRepository(session=session)
    for tenant_id in tenant_ids:
        for definition in DEFAULT_TENANT_ROLES:
            role = await role_repository.find_by_slug(tenant_id=tenant_id, slug=definition.slug)
            if role is None:
                logger.info("would_create", tenant_id=str(tenant_id), slug=definition.slug)
            elif role.permissions != definition.permissions or role.status != TenantRoleStatus.ACTIVE:
                logger.info("would_update", tenant_id=str(tenant_id), slug=definition.slug)


async def apply_changes(session: AsyncSession, tenant_ids: list[UUID]) -> None:
    role_repository = SQLTenantRoleRepository(session=session)
    for i, tenant_id in enumerate(tenant_ids):
        # The use case is idempotent and each repository write commits on its own.
        await TenantRolesBootstrapper(tenant_id=tenant_id, role_repository=role_repository).execute()
        if i % 100 == 0:
            logger.info("apply.progress", processed=i, total=len(tenant_ids))
```

## Non-negotiable conventions

**Entrypoint** = Typer, not argparse. `app = typer.Typer()`, `@app.command() def main(...)`, `if __name__ == "__main__": app()`. CLI options via `Annotated[T, typer.Option(...)]`. `main` parses args (e.g. `UUID(...)`, `date.fromisoformat(...)`) then `asyncio.run(run(...))`. `main` is sync; `run` is the async body.

**Session bootstrap** — there is NO request DI. Get a session factory yourself:
```python
db_config = get_database_config()            # src.common.database.config
async with db_config.session_maker() as session:
    ...
```
`session_maker` has `expire_on_commit=False`. The script owns
session/engine cleanup, including `db_config.dispose()` in finally. Existing
repository write methods own their transactions through `atomic_transaction`;
do not add a final commit or call a write method during dry-run. Those operations
can commit independently, so a later failure does not undo earlier rows. If the
backfill requires an atomic batch, first define an explicit infrastructure-backed
transaction operation with rollback; wrapping independently committing methods or
adding a final commit cannot provide that guarantee.

**Logging** = structured: `logger = get_logger(__name__)` from `src.common.application.logging`. Emit `logger.info("event.name", key=value, ...)` — first arg is an event slug (`dry_run.start`, `would_change`, `apply.progress`, `finished`), rest are kwargs. No f-string log messages. UUIDs → `str(...)`.

**Dry-run / idempotency** — backfills default to a no-write dry run; `--apply` is opt-in (`apply: bool = False`). Split logic into `dry_run()` (read + log `would_*`) and `apply_changes()` (mutate through a repository/use case, which commits). Compare before writing so re-runs are idempotent:
```python
if role.status != TenantRoleStatus.ACTIVE:
    role.activate()
    await role_repository.persist(role)
    updated += 1
```
Log progress every N rows: `if i % 100 == 0: logger.info("apply.progress", processed=i, total=len(items))`.

**Type checking** — `ty.toml` includes only `src` and `config`, so `just backend
check` does not type-check `scripts/` (or `tests/`). Review script types by hand
and exercise the dry run before `--apply`.

## Reuse the domain — three escalating levels

Pick the lightest that works. Drive writes through use-cases/repos, not ad-hoc SQL.

1. **Repos directly** — instantiate `SQL*` repos with `session=session`:
   ```python
   tenant_repository = SQLTenantRepository(session=session)
   tenant = await tenant_repository.find_by_slug(tenant_slug)
   ```
2. **A use-case** for the actual mutation (preferred over hand-written updates):
   ```python
   await TenantRolesBootstrapper(tenant_id=tenant.uuid, role_repository=role_repository).execute()
   ```
3. **A bus** when a use-case/query handler needs one:
   - Need only one query → hand-build a `MemoryQueryBus` and subscribe just what you use:
     ```python
     query_bus = MemoryQueryBus()
     query_bus.subscribe(SomeQuery, SomeQueryHandler(some_repository=some_repository))
     result = await query_bus.ask(query=SomeQuery(...))
     ```
   - Need the full wired domain (commands enqueue to background jobs, all modules wired) → use the builders with one RabbitMQ connection and one Valkey client for the whole script:
     ```python
     from src.common.infrastructure.bus_builder import build_async_bus
     from src.common.infrastructure.domain_builder import build_async_domain
     from src.common.infrastructure.rabbitmq.broker import RabbitMQBroker
     from src.common.infrastructure.rabbitmq.topology import CommandQueueTopology
     from src.common.infrastructure.redis_client import create_redis_client

     redis_client = create_redis_client(settings)
     broker = await RabbitMQBroker.connect(
         settings.rabbitmq_url, CommandQueueTopology.from_settings(settings), connection_name="script"
     )
     try:
         domain = build_async_domain(session=session, redis_client=redis_client)
         bus = build_async_bus(session=session, domain=domain, enqueuer=broker.command_enqueuer())
         await bus.command_bus.dispatch(SomeCommand(...), run_async=True)
     finally:
         await broker.close()
         await redis_client.aclose()
     ```
     Note `run_async=True` publishes to RabbitMQ for the worker — side effects (exports, notifications) become background work. Dispatch with `run_async=False` when you want a command to run inline.

## Invocation

```bash
just backend bash
# Inside the container, after implementing and reviewing the script:
python scripts/<name>.py --apply --tenant-id <uuid>
# installed example: python scripts/bootstrap_tenant_roles.py --tenant-slug <slug>
```
Runs inside the API container (correct env + DB/Redis hostnames). Direct `python scripts/x.py` only works inside `just backend bash`. Frequently-run scripts may earn a dedicated `just` recipe.

## Reports

Long-running tasks may write a CSV report. No installed script does this yet and no report directory is gitignored: `scripts/reports/` is not in `.gitignore`, so add that ignore rule in the same change (or write outside the repository) before producing reports. Accumulate counts in a `@dataclass` report, then `report.write_csv(mode)` returning a timestamped `Path` (`<script>_<mode>_<YYYYMMDD_HHMMSS>.csv`); log the path in the final `finished` event.

## Heavy fan-out tasks

For tasks that fan out over an external API or large dataset: call sync SDKs (boto3, `StorageService`) with `await asyncio.to_thread(...)` and bound concurrency with an `asyncio.Semaphore` inside an `asyncio.TaskGroup`; do not use `ThreadPoolExecutor`/`loop.run_in_executor`. Process each item in its OWN short-lived session with bounded batches + retry — not one giant transaction. Wrap each item in a `process_single_*_with_retry` helper and batch the `apply_changes` loop.

## Architectural references
- [repositories.md](../../backend-architecture/references/repositories.md) — `SQL*` repo construction, entity ↔ ORM builders.
- [dependency-injection.md](../../backend-architecture/references/dependency-injection.md) — how the request path builds the same contexts (`DomainContext`/`BusContext`) that scripts assemble by hand.
- [cqrs-buses.md](../../backend-architecture/references/cqrs-buses.md) — `MemoryQueryBus.subscribe`/`ask`, query/handler wiring.
