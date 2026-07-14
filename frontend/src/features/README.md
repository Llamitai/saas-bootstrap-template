# Frontend Features

Feature slices own product-specific frontend implementation.

Each migrated feature lives at:

```text
src/features/<feature>/
  api/       # DTOs, fetchers, mappers, query keys, queries, mutations
  model/     # feature types, schemas, transforms, local stores, derived state
  ui/        # route views and feature-specific components
  index.ts   # public API for imports outside this feature
```

Import rules:

- Route files compose feature views; reusable feature behavior stays here.
- Code outside a feature imports only from `@/features/<feature>` or a documented
  route-level UI entry point.
- A feature may import from `@/shared/*`.
- A feature must not import from `src/app`.
- Private imports from another feature's `api`, `model`, or `ui` folders are not
  allowed.
- Browser-facing feature code calls same-origin BFF/proxy helpers; it must not
  import backend hosts, server-only HTTP clients, or raw infrastructure
  repositories.

Current feature slices:

- `auth`, `members`, `profile`, `roles`, `settings`, `superuser`,
  `tenants`

State and data-loading rules:

- Backend collections/details belong in TanStack Query hooks under
  `features/<feature>/api`.
- Mutations update or invalidate the owning feature query keys on success.
- Zustand is reserved for session/draft/editor/UI state. Valid stores live under
  `features/<feature>/model` or `shared/model` when truly generic.
- Do not create new code under retired top-level layers such as
  `src/application`, `src/infrastructure`, `src/domain`, or
  `src/presentation`; boundary validation treats those folders as closed.

Examples:

```ts
import { MembersView } from "@/features/members";
import { SettingsView } from "@/features/settings";
import { Button } from "@/shared/ui/button";
```

```ts
// Cross-feature imports go through public APIs.
import { useRolesQuery } from "@/features/roles";

// Not allowed:
// import { useRolesQuery } from "@/features/roles/api/roles";
```
