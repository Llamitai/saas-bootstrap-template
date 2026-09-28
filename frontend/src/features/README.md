# Frontend features

Los features son la unidad de implementación de producto en el frontend.

Forma de un feature:

```text
src/features/<feature>/
  api/       # un archivo por recurso: request fns, factory de keys, hooks, invalidación
  model/     # schemas zod, tipos, stores Zustand y helpers del feature
  ui/        # vistas de ruta y componentes del feature
  index.ts   # fachada pública
  server.ts  # opcional: fachada server-only (hoy solo auth)
```

Features actuales: `app-shell`, `auth`, `members`, `profile`, `roles`,
`settings`, `superuser`, `tenants`. `just frontend new-feature <name>` crea el
esqueleto y rechaza un feature existente.

Reglas de import (las aplica `scripts/check-import-boundaries.mjs`):

- Las rutas de `src/app` componen vistas de la fachada; el comportamiento vive
  aquí.
- Fuera del feature solo se importa `@/features/<feature>` (o
  `@/features/<feature>/server` desde código de servidor).
- Un feature importa entidades solo por su fachada (`@/entities/<entity>`) y
  puede importar `@/shared/*`.
- Un feature no importa `src/app` ni internals `api/`, `model/` o `ui/` de otro
  feature.
- El código browser-facing llama a rutas same-origin `/api` con `authHttp`/
  `localHttp`; no importa `serverHttp`, `shared/config/server` ni helpers BFF.

Estado y datos:

- Colecciones y detalle del backend viven en hooks de TanStack Query bajo
  `api/`. Las mutaciones invalidan las keys del recurso en `onSuccess`.
- Las keys actuales no incluyen tenant/usuario: el cambio de tenant recarga la
  página completa y logout/login deben limpiar la caché (ver deuda conocida en
  la arquitectura).
- Zustand solo para sesión, borradores, wizard o UI, en
  `features/<feature>/model`. No hay stores en `shared`.
- No se crea código bajo capas retiradas (`src/application`,
  `src/infrastructure`, `src/domain`, `src/presentation`).

Ejemplos:

```ts
import { MembersView } from "@/features/members";
import { refreshBackendSession } from "@/features/auth/server"; // solo servidor
import { Button } from "@/shared/ui/button";

// No permitido:
// import { useRolesQuery } from "@/features/roles/api/roles";
```

Referencia: [arquitectura frontend](../../../docs/content/docs/conceptos/arquitectura-frontend.md).
