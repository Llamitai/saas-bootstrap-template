# Module assembly reference

Use this map to inspect the connections required by the module's chosen shape.
Read [layers.md](layers.md) for ownership and a matching installed module as the
exemplar. A thin facade, storage adapter or messaging scaffold may use only part
of this map; adding a module does not require creating every listed artifact.

| Architectural concern | Connection to preserve | Detailed convention |
| --- | --- | --- |
| Domain behavior | Shared models remain central; private concepts and repository interfaces belong to their module | [layers.md](layers.md) |
| Use case | A dataclass implements UseCase.execute(), depends on domain interfaces and owns one operation per file | [use-cases.md](use-cases.md) |
| Persistence | Central ORM model ↔ builder ↔ domain value; repository ABC ↔ SQL adapter; writes preserve transactional rollback | [repositories.md](repositories.md) |
| Dependency construction | A repository declared on DomainContext is supplied by its builder; the request resolves the intended session and dependencies | [dependency-injection.md](dependency-injection.md) |
| Presentation | Request validation → use case → presenter/response conversion; the module router is included in the active composition | [endpoints.md](endpoints.md) |
| Errors | DomainError carries the domain failure; presentation handlers translate it to the active HTTP envelope | [errors.md](errors.md) |

For a persisted model, also check that the central models package imports it so
Alembic sees its metadata. Migration design, execution and data preservation
belong to [schema-change](../../schema-change/SKILL.md).

## Connections required only by active capabilities

- Cross-module commands/queries need registered handlers and bus wiring; local
  CRUD uses the repository directly. Async commands also need the existing task
  mapping and serialization contract. See [cqrs-buses.md](cqrs-buses.md).
- Tenant-scoped operations resolve scope on the server and preserve ownership,
  membership and permission checks. A user's last-selected tenant is a hint, not
  authorization. See [auth-multi-tenant.md](auth-multi-tenant.md).
- Paginated endpoints keep their ordering/filter contract; tables using soft
  deletion keep its read/write semantics. See [pagination.md](pagination.md) and
  [repositories.md](repositories.md).
- Worker handlers create their own session/context; retries preserve idempotency.
  See [background-jobs.md](background-jobs.md).

Common integration failures include a repository missing from its builder, an
unregistered handler or router, and a builder accessing a relation the SQL adapter
has not loaded. These are concrete connections to inspect, not a mandatory sequence
of implementation tasks.

[backend-change](../../backend-change/SKILL.md) owns implementation order.
[verify-change](../../verify-change/SKILL.md) selects checks and test evidence;
[this test-interface map](testing.md) identifies what each layer exposes. This
reference does not prescribe commits, blanket test suites or closure.
