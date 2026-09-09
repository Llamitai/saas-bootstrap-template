---
name: clean-fastapi-ddd
description: Explain and apply backend architecture conventions for Clean Architecture with FastAPI, including module ownership, inward dependencies, use cases, repository interfaces, adapters and dependency injection. Use for architectural choices within backend work; task orchestration, migration execution and test authoring belong to their dedicated workflows.
---

# Backend architecture conventions

Use this reference to decide where backend behavior belongs and how its interfaces
connect. Read `docs/internal/project-profile.md`, `backend/README.md` and a matching
module exemplar first. Code paths in these references are relative to `backend/`.

## Architectural contract

- Domain and application depend on domain interfaces; FastAPI and SQLAlchemy stay
  in the outer layers. Repository interfaces expose domain values, never ORM rows.
- Use cases own business behavior; infrastructure owns persistence, transaction
  handling and adapters; presentation owns HTTP input/output. Keep dependencies
  explicit and preserve the request/session lifecycle.
- Follow the installed full or thin module shape. Keep ORM models in
  `src/common/database/models/`, shared domain models in `src/common/domain/models/`,
  and module-private domain concepts in their owning module.
- Preserve the active public contract and authorization. The project profile and
  implementation determine capabilities, response shapes and deployment topology;
  examples neither install optional services nor remove existing scope checks.

## Read for the architectural question

| Question | Reference |
| --- | --- |
| Module ownership, layers and allowed imports | [layers.md](references/layers.md) |
| Use-case interface, naming and composition | [use-cases.md](references/use-cases.md) |
| Repository interfaces, SQL adapters, builders and transactions | [repositories.md](references/repositories.md) |
| Dependency construction and request/session lifetime | [dependency-injection.md](references/dependency-injection.md) |
| HTTP input, presenters and router composition | [endpoints.md](references/endpoints.md) |
| Domain errors and their HTTP translation | [errors.md](references/errors.md) |
| Connections to inspect when assembling a module | [feature-checklist.md](references/feature-checklist.md) |
| Interfaces to exercise when verifying a layer | [testing.md](references/testing.md) |

Open only the reference needed to resolve the current question. Detailed
conventions, including dataclass use cases and one operation per file, live there.

## Conditional integration patterns

These references explain how an already selected capability fits the architecture:

- [cqrs-buses.md](references/cqrs-buses.md): existing cross-module protocols and
  async dispatch; ordinary local CRUD uses repository interfaces.
- [auth-multi-tenant.md](references/auth-multi-tenant.md): active identity,
  authorization and tenant scoping.
- [pagination.md](references/pagination.md): an endpoint using the cursor/Page
  contract described there; preserve other existing list contracts.
- [background-jobs.md](references/background-jobs.md): an active SAQ/Redis worker
  and its independent session lifecycle.
- [config-bootstrap.md](references/config-bootstrap.md): the composition root,
  settings and lifetime of the services the profile actually enables.

## Workflow owners

[backend-change](../backend-change/SKILL.md) owns building/refining a change and
[operational scripts](../backend-change/references/operational-scripts.md).
[schema-change](../schema-change/SKILL.md) owns migrations and data evolution.
[verify-change](../verify-change/SKILL.md) owns check selection and evidence, using
python-testing for pytest conventions. Commands and environments come from the
project profile and verification guide. Resolving an architectural question here
does not start another development loop or establish acceptance.
