# Commands, queries and buses

Paths are relative to `backend/`. Buses carry cross-module protocols and deferred
work. Same-module CRUD calls repositories from a use case and does not use them.

| Piece | Location |
| --- | --- |
| Contracts `Command`, `CommandHandler`, `CommandBus` | `src/common/domain/buses/commands.py` |
| Contracts `Query`, `QueryHandler`, `QueryBus` (`ask`) | `src/common/domain/buses/queries.py` |
| `DomainEvent`, `EventBus` | `src/common/domain/buses/events.py` |
| In-memory buses, RabbitMQ enqueuer, bus errors | `src/common/infrastructure/buses/` |
| Message classes | `src/common/application/commands/*.py`, `src/common/application/queries/*.py` |
| Handlers | `src/<module>/application/command(s)/`, `src/<module>/application/queries/` |
| Wiring | `src/<module>/infrastructure/bus_wiring.py`, called from `src/common/infrastructure/bus_builder.py` |
| Exemplars | `PersistTenantCommand` → `tenants/application/command/persist_tenant.py`; `GetTenantByIdQuery` → `tenants/application/queries/tenants/get_tenant.py`; `SendEmailCommand` → `messaging/application/commands/send_email.py` |

## Rules

- Messages are `@dataclass` classes named verb-first (`GetUserByIdQuery`,
  `SoftDeleteTenantCommand`) and live in `src/common/application` so any module can
  send them without importing the receiver.
- A command implements `to_dict`/`from_dict`. For a command that may run on the
  worker, both must round-trip JSON-safe values (stringify UUIDs, decimals and
  datetimes); see `SoftDeleteTenantCommand`.
- Handlers are `@dataclass` subclasses of `CommandHandler[T]`/`QueryHandler[T, R]`
  with interface fields. They stay thin and may delegate to a use case
  (`SoftDeleteTenantHandler` → `TenantSoftDeleter`).
- Wiring subscribes each message exactly once with keyword arguments, pulling
  dependencies from `DomainContext`. A module's messages work only after its
  wiring function is called in `build_async_bus`.
- `query_bus.ask(query)` returns the handler result. `command_bus.dispatch(command)`
  runs inline and returns the handler result; `run_async=True` enqueues it and
  returns `None` (see [background-jobs.md](background-jobs.md)).
- `event_bus` is wired but has no subscribers or publishers. Do not route new
  behavior through it without an explicit design decision.

## When to use what

| Need | Mechanism |
| --- | --- |
| Read or write data owned by the same module | Repository through a use case |
| Read data owned by another module | `QueryBus` query |
| Write in another module | `CommandBus` command |
| Work outside the request | Command with `run_async=True`, registered for the worker |

## Common mistakes

- Missing wiring → `CommandHandlerDoesNotExistError`/`QueryHandlerDoesNotExistError`.
- Subscribing a message twice → `CommandAlreadyExistError`/`QueryAlreadyExistError`.
- Importing another module's repository or use case instead of sending a message.
- Business rules in a handler instead of the use case it delegates to.
