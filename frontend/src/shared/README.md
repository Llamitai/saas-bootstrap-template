# Frontend shared

Los módulos compartidos son piezas genéricas y estables que usan varios
features. No conocen features, entidades ni reglas de producto.

Carpetas actuales:

```text
src/shared/
  catalogs/   # catálogos estáticos: países, monedas, zonas horarias
  config/     # public.ts (seguro para cliente) y server.ts (secretos server-only)
  helpers/    # helpers JWT y lectura de cookies de sesión en servidor
  hooks/      # hooks React sin dominio
  http/       # clientes browser (/api), serverHttp, helpers BFF, errores, cookies
  lib/        # formato, fechas, ids, utilidades de clases
  providers/  # QueryProvider (QueryClient estable)
  types/      # tipos transversales (RequestContext, TaskResult)
  ui/         # primitives del design system y widgets neutrales
    components/     # piezas compuestas genéricas (visor JSON, selector de idioma, logo)
    components/ui/  # visores genéricos (código, JSON)
```

No existe `shared/model` ni stores en shared: los stores Zustand viven en el
feature dueño (`features/<feature>/model`). Los tipos de sesión viven en
`entities/session`; el store de sesión, en `features/auth/model`.

Reglas de import (las aplica `scripts/check-import-boundaries.mjs`):

- `shared` no importa de `entities`, `features` ni `app`.
- `shared/ui` es solo presentacional: sin fetching de datos, navegación de
  producto ni permisos.
- El código browser-facing (módulos `"use client"`, `shared/ui`, `ui/` de
  features) no importa `@/shared/config/server`, `@/shared/http/server`,
  `@/shared/http/bff`, `@/shared/http/session-cookies`, `@/shared/http/requests`,
  `next/headers` ni `server-only`.
- Un módulo nuevo que lee secretos empieza con `import "server-only"`.
- Si el código tiene dueño de producto o comportamiento de un feature, se queda
  en ese feature.

Ejemplos:

```ts
import { authHttp } from "@/shared/http/client";
import { serverHttp } from "@/shared/http/server"; // solo código de servidor
import { cn } from "@/shared/lib/utils";
import { PageContent } from "@/shared/ui/page-content";
```

Referencia: [arquitectura frontend](../../../docs/content/docs/conceptos/arquitectura-frontend.md).
