# Frontend Shared

Shared modules are generic, stable building blocks used by multiple features.

Expected folders:

```text
src/shared/
  config/  # generic environment/config helpers with clear client/server scope
  http/    # same-origin browser HTTP helpers and server-only wrappers
  i18n/    # generic localization helpers
  lib/     # formatting, dates, collections, class-name utilities
  model/   # truly generic/session-adjacent local state used by infrastructure
  ui/      # design-system primitives and feature-neutral UI components
```

Import rules:

- `shared` may not import from `features` or `app`.
- `shared/ui` contains presentational primitives only; no feature data fetching.
- Shared browser code must not import backend host settings, `serverHttp`, or raw
  infrastructure repositories.
- If code has a product owner or feature-specific behavior, keep it in the owning
  feature instead of moving it here.

Current shared ownership:

- `shared/http`: same-origin browser clients, server-only BFF clients and common headers.
- `shared/ui`: design-system primitives plus feature-neutral widgets such as
  page content, filters, viewer primitives, and empty states.
- `shared/lib`: formatting/date/class-name utilities and generic hooks.
- `shared/model`: app-wide local state needed below feature level, currently the
  session store and core tenant/user entities.

Examples:

```ts
import { authHttp } from "@/shared/http/client";
import { serverHttp } from "@/shared/http/server";
import { cn } from "@/shared/lib/utils";
import { PageContent } from "@/shared/ui/page-content";
```
