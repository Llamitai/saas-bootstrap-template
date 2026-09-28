# Module assembly reference

Use this map to inspect the connections a module's chosen shape requires. Read
[layers.md](layers.md) for ownership and an installed module as the exemplar. A
thin facade, storage adapter or messaging scaffold uses only part of this map;
adding a module does not require every artifact.

| Architectural concern | Connection to preserve | Detailed convention |
| --- | --- | --- |
| Domain behavior | Shared models stay central; private concepts and repository ports belong to their module | [layers.md](layers.md) |
| Use case | A dataclass implements `UseCase.execute()`, depends on domain interfaces and owns one operation per file | [use-cases.md](use-cases.md) |
| Persistence | Central ORM model ↔ builder ↔ domain value; port ↔ SQL adapter; writes inside `atomic_transaction` | [repositories.md](repositories.md) |
| Dependency construction | A repository on `DomainContext` is constructed in `build_async_domain`; the request shares one session | [dependency-injection.md](dependency-injection.md) |
| Presentation | Permission check → request DTO → use case → presenter → `ApiJSONResponse`; router included in `config/router.py` | [endpoints.md](endpoints.md) |
| Errors | `DomainError` carries the failure; global handlers produce the envelope | [errors.md](errors.md) |

A new top-level module is registered in the import-linter contracts of
`backend/pyproject.toml` (`containers` of the layers contract and the feature
list of the shared-domain contract); an architecture test fails otherwise. For a
persisted model, also check that the models package imports it so Alembic
sees its metadata. Migration design, execution and data preservation belong to
[schema-change](../../schema-change/SKILL.md).

## Connections required only by active capabilities

- Cross-module messages need handlers subscribed in the module wiring and the
  wiring call in `build_async_bus`; deferred commands also need
  `async_tasks_mapping`. See [cqrs-buses.md](cqrs-buses.md) and
  [background-jobs.md](background-jobs.md).
- Tenant-scoped operations resolve scope on the server, check ownership of path
  ids and call the permission check. See [auth-multi-tenant.md](auth-multi-tenant.md).
- Paginated endpoints keep the cursor contract; soft-delete tables keep their
  read/write semantics. See [pagination.md](pagination.md) and
  [repositories.md](repositories.md).

Common integration failures: a module missing from the import-linter contracts, a repository missing from `build_async_domain`, an
unsubscribed handler or unregistered router, and a builder reading a relation the
adapter did not load. These are connections to inspect, not a task sequence;
[backend-change](../../backend-change/SKILL.md) owns implementation order and
[verify-change](../../verify-change/SKILL.md) selects checks.
