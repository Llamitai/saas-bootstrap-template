# Arquitectura frontend objetivo

Este documento describe el estado ideal de la arquitectura del frontend del
proyecto. Es la fuente de verdad para decisiones de estructura, limites entre
modulos, SDD/TDD, herramientas y Definition of Done.

`AGENTS.md` en la raiz del repo existe solo como puntero corto a este archivo.
No debe duplicar reglas de arquitectura, para evitar documentos paralelos que
puedan quedar desincronizados.

## 1. Principios de arquitectura

Estos principios definen el estado objetivo del frontend.

1. La unidad principal es el **feature** (`src/features/<feature>`), no la capa.
   Un modelo de dominio compartido por dos o mas features vive en
   `src/entities/<entity>`. Si lo usa un solo feature, vive dentro de ese
   feature.
2. Cada feature y cada entidad expone una sola fachada publica: `index.ts`. Los
   modulos externos no importan internals de otro feature o entidad.
3. `src/app` es una capa delgada: rutas, layouts, metadata y route handlers. Las
   paginas re-exportan o renderizan vistas de feature.
4. El flujo de dependencias es unidireccional:
   `app -> features -> entities -> shared`. Cada capa solo importa de las capas
   ubicadas a su derecha.
5. El browser no llama al backend directo. Todo trafico cliente pasa por rutas
   same-origin `/api/...` del propio Next.js.
6. TanStack Query es la fuente estandar de estado remoto en cliente. No debe
   existir SWR ni otra cache paralela de datos remotos. Server Components,
   route handlers, auth y acciones puntuales pueden usar requests directas
   cuando no introducen estado remoto cliente.
7. El render es server-first cuando la superficie lo permite. Superficies
   publicas o solo-lectura usan Server Components con `serverHttp`; superficies
   autenticadas o interactivas usan client components, `authHttp` y React Query.
8. Los features y cambios de contrato se desarrollan con TDD: spec primero,
   tests que fallan despues, implementacion al final. Cambios mecanicos,
   documentales o de UI sin comportamiento usan verificacion enfocada.
9. Los limites de import se verifican con herramientas, no con disciplina manual:
   `scripts/check-import-boundaries.mjs` es la unica verificacion de boundaries.
10. La Definition of Done de un cambio funcional frontend es `pnpm verify` en
    verde. Cambios mecanicos o documentales usan el subconjunto de gates que
    cubra su riesgo, sin saltar `check:architecture` cuando modifican imports.

## 2. Flujo SDD

El frontend usa OpenSpec como fuente unica del flujo spec-driven development.
No se mantienen specs paralelos fuera de OpenSpec. Los artefactos de
especificacion viven en `openspec/` y se gestionan con el flujo de OpenSpec.

El flujo queda asi:

- **Constitucion**: este documento.
- **Specify**: `openspec/changes/<change-id>/proposal.md` y delta specs en
  `openspec/changes/<change-id>/specs/<capability>/spec.md`.
- **Plan**: `openspec/changes/<change-id>/design.md`.
- **Tasks**: `openspec/changes/<change-id>/tasks.md`.
- **Implement**: estructura y receta feature-based descritas en este documento.
- **Validate**: `openspec validate <change-id> --strict`.
- **Archive**: al cerrar el cambio, OpenSpec sincroniza el estado aceptado hacia
  `openspec/specs/`.

Cada cambio funcional de producto empieza como un OpenSpec change activo:

```text
openspec/changes/<change-id>/
  proposal.md
  design.md
  tasks.md
  specs/
    <capability>/
      spec.md
```

`<change-id>` usa kebab-case y describe el cambio, no necesariamente un solo
feature. Una change puede afectar uno o varios features; `proposal.md` y
`design.md` declaran que carpetas `src/features/<feature>` y capacidades
OpenSpec quedan afectadas.

El mapeo operativo es:

```text
openspec/changes/<change-id> -> src/features/<feature>...
openspec/specs/<capability>  -> capacidades aceptadas del producto
```

Antes de modificar codigo que cambie comportamiento de producto, contratos,
rutas, permisos o flujos de usuario, debe existir una change activa de OpenSpec
para el alcance del cambio. La implementacion lee `proposal.md`, `design.md`,
`tasks.md` y los delta specs relevantes. Si el cambio requerido contradice
OpenSpec, se actualiza primero la change y se valida con `openspec validate
<change-id> --strict`.

Cambios sin comportamiento de producto pueden saltar OpenSpec: docs, copy,
estilos visuales sin proceso nuevo, exports de fachada, limpieza de imports,
renombres mecanicos, codemods y ajustes de tooling. La regla para saltarlo es
estricta: el cambio no puede modificar contratos, permisos, persistencia,
fetching, rutas visibles ni criterios de aceptacion. Aun asi debe tener gate de
verificacion proporcional: type-check, tests afectados, boundary check, build o
captura visual segun aplique.

`tasks.md` contiene la lista accionable en orden TDD para cambios funcionales:
test rojo, implementacion a verde, refactor y gate final. El gate final de una
change incluye `openspec validate <change-id> --strict` y `pnpm verify`.

## 3. Stack base objetivo

El stack objetivo del frontend es:

- Next.js App Router (Next 16+), React 19 y TypeScript estricto.
- Tailwind CSS v4 con tokens en `src/app/globals.css` (`@theme inline`).
- shadcn sobre Tailwind v4.
- Base UI (`@base-ui/react`) como libreria de primitives accesibles cuando
  aplique.
- UI propia en `src/shared/ui`.
- TanStack React Query como cache unica de estado remoto en cliente.
- Zustand para estado cliente transversal o persistible.
- Axios para clientes HTTP.
- `react-hook-form`, `zod` y `@hookform/resolvers` para formularios y
  validacion.
- `next-intl` para i18n.
- SSE para realtime.
- Biome para lint y formato.
- Vitest + Testing Library para unit/component tests.
- Playwright para E2E.
- MSW para mocks de `/api` en tests.

### Realtime

SSE es el estandar de realtime.

Realtime funciona como bus de invalidacion de TanStack Query. No duplica estado
remoto.

### Lint y formato

Biome es la herramienta principal de lint/formato: un solo binario,
configuracion unica y feedback rapido.

Biome no replica `eslint-config-next`, por lo que reglas especificas de
Next/React deben vigilarse manualmente o mantenerse en un ESLint minimo si el
proyecto lo requiere.

### Aliases TypeScript

El estado objetivo incluye aliases explicitos en `tsconfig.json`:

```json
{
  "@/features/*": ["src/features/*"],
  "@/entities/*": ["src/entities/*"],
  "@/shared/*": ["src/shared/*"]
}
```

`@/*`, `@/images/*` y `@/public/*` pueden seguir existiendo, pero los imports
internos de arquitectura deben expresar su capa con claridad.

## 4. Estructura objetivo

La raiz del repo es el frontend. La arquitectura objetivo tiene cuatro capas:

```text
src/
  app/
  features/
  entities/
  shared/
```

El flujo permitido es:

```text
app -> features -> entities -> shared
```

No existe capa global de repositorios. No existe carpeta global `responses/`. No
existe `model/` en `shared`. Los adapters de transporte existen solo cuando
esconden complejidad real detras de una interfaz pequena; no viven como
`shared/api/repositories` por defecto.

```text
src/
  app/                       # Next App Router: rutas, layouts, metadata, route handlers.
    [domain]/                # multitenant por subdominio/slug del tenant
      (public)/              # superficies publicas/solo-lectura
      (protected)/           # superficies autenticadas/interactivas
      layout.tsx             # layout del tenant: valida/refresca sesion en server
    admin/                   # consola administrativa/cross-tenant
    api/                     # route handlers BFF (/api/*)
    layout.tsx               # root layout: providers globales
    globals.css              # Tailwind v4 + tokens de diseno
    page.tsx

  features/                  # unidad principal de producto
    app-shell/               # shell transversal autenticado
      ui/
      index.ts
    <feature>/
      api/                   # request fn + hook React Query colocalizados
      model/                 # zod, stores Zustand, tipos y helpers locales
      ui/                    # vistas y componentes del feature
      index.ts               # fachada publica unica

  entities/                  # modelos de dominio compartidos por 2+ features
    <entity>/
      api/                   # request fns + hooks + queryKeys + DTOs de la entidad
      model/                 # tipo de dominio + zod + type guards
      ui/                    # piezas presentacionales opcionales de la entidad
      index.ts               # fachada publica unica

  shared/                    # codigo generico y agnostico de dominio
    http/                    # transporte HTTP, BFF helpers, SSE, errores
    config/                  # public.ts y server.ts
    lib/                     # utilidades puras y wrappers de terceros
    hooks/                   # hooks genericos sin dominio
    types/                   # tipos transversales
    ui/                      # design system operativo

  i18n/                      # next-intl
  proxy.ts                   # middleware Next 16
  constants.ts

next.config.ts
tsconfig.json
biome.json
vitest.config.ts
playwright.config.ts

scripts/
  gen-feature.mjs
  check-import-boundaries.mjs

tests/
  unit/
  components/
  end-to-end/
```

Notas sobre el estado actual frente a este arbol objetivo:

- `src/app` hoy tiene `(public)`, `(protected)` y `api` directamente en la
  raiz; los segmentos `[domain]/` y `admin/` son objetivo, aún no
  implementados.
- `tests/` hoy contiene `components/`, `setup.ts` y `render-with-intl.tsx`;
  `tests/unit` y `tests/end-to-end` son objetivo, aún no implementados.

### Responsabilidades por capa

`src/app` contiene exclusivamente Next App Router: segmentos, layouts, metadata,
route handlers y composicion de vistas. No contiene logica de negocio.

`src/features` contiene la logica de producto. Cada feature queda declarado en
la change de OpenSpec que introduce o modifica su comportamiento, y puede tener
`api`, `model`, `ui` e `index.ts`.

`src/entities` contiene modelos de dominio compartidos por dos o mas features.
Ejemplos: `user`, `tenant`, `member`, `session`, `tenant-role`, `permission`.

`src/shared` contiene codigo generico. No conoce features ni entidades. No
contiene DTOs de negocio, permisos de producto ni navegacion de producto. Puede
contener adapters genericos de transporte dentro de `shared/http` cuando la
complejidad es transversal: headers, BFF helpers, SSE, retry/backoff,
multipart/streaming o normalizacion de errores.

## 5. Decisiones clave

### `api/` colocaliza request y hook

Cada archivo de `<feature|entity>/api` representa una operacion. El archivo
exporta:

- funcion async de request.
- query keys relacionadas.
- hook `useQuery` o `useMutation`.

Esto evita separar fetchers en una carpeta y hooks en otra.

### Adapters solo cuando ganan su lugar

El acceso a datos por defecto es una funcion async que usa `authHttp` o
`serverHttp`, colocalizada con su hook. En tests se mockea `/api` con MSW.

No se crean interfaces ni clases repositorio para envolver Axios sin aportar
comportamiento. Un modulo asi es shallow: su interfaz es casi igual de compleja
que la implementacion y solo mueve codigo de lugar.

Un adapter o repositorio esta permitido cuando pasa al menos una de estas
pruebas:

- Esconde complejidad de transporte que se repetiria en varios callers:
  multipart, streaming, SSE, retry/backoff, headers tenant-aware,
  cross-tenant, Cloudflare Access o normalizacion de errores.
- Tiene dos o mas adapters reales, por ejemplo HTTP y mock persistente, o HTTP y
  implementacion local para pruebas de contrato.
- Estabiliza un contrato externo inestable detras de una interfaz pequena y
  permite cambiar la implementacion sin tocar callers.

El adapter vive en la capa mas estrecha posible: dentro de `feature/api` o
`entity/api` si conoce dominio; dentro de `shared/http` solo si es transporte
generico. La fachada publica del feature o entidad sigue siendo la interfaz que
usan otros modulos. Si al borrar el adapter no reaparece complejidad duplicada
en varios callers, el adapter no se justifica.

### Los DTOs no son `model`

`model/` representa dominio: tipos, zod y reglas del dominio. La forma concreta
de una respuesta del backend vive junto a la request que la devuelve, dentro de
`api/`. Solo los tipos realmente transversales van en `shared/types`.

## 6. Relacion con FSD canonica

FSD canonica usa seis capas: `app`, `pages`, `widgets`, `features`, `entities`
y `shared`. Este proyecto usa cuatro capas.

| FSD canonica | En el proyecto |
|---|---|
| `app` | `src/app` para rutas + `features/app-shell` para shell/providers |
| `pages` | `page.tsx` delgado que renderiza vistas de feature |
| `widgets` | dentro del feature, o `app-shell` si es transversal |
| `features` | `src/features/<feature>` |
| `entities` | `src/entities/<entity>` |
| `shared` | `src/shared` |

El trade-off aceptado es menos capas y menos decisiones por cambio, a cambio de
no poder usar el linter oficial `steiger` tal cual. Los limites se verifican con
`scripts/check-import-boundaries.mjs`.

## 7. Server vs Client

El producto tiene dos tipos de superficie.

### Publico o solo-lectura

Ejemplos: marketing, landing, contenido SEO.

Estado objetivo:

- Server Components por defecto.
- Fetch en servidor con `serverHttp`.
- Sin React Query salvo que exista una isla interactiva con estado remoto
  cliente.
- Sin `"use client"` excepto en islas puntuales.

### Autenticado o interactivo

Ejemplos: dashboard, formularios, experiencias con realtime.

Estado objetivo:

- Client Components cuando requieren hooks, estado, eventos o React Query.
- `authHttp` hacia `/api`.
- React Query como fuente de verdad para estado remoto cliente: listas, detalle,
  mutations, invalidacion y polling/realtime por invalidacion.
- Layout protegido en servidor que valida/refresca sesion con cookies HttpOnly
  antes de renderizar.
- `SessionSync` para sincronizar sesion server-side al cliente.

Auth, redirects, acciones one-shot, Server Components y route handlers pueden
usar request functions directas. No deben introducir una cache paralela ni
duplicar listas o detalle remoto en Zustand.

Regla practica: `"use client"` aparece solo cuando el componente usa hooks de
navegacion, estado, React Query o eventos.

## 8. Limites e imports

Los limites de arquitectura se aplican con un solo mecanismo:
`scripts/check-import-boundaries.mjs`. Biome cubre lint y formato pero no
define reglas `noRestrictedImports`; el script es la unica verificacion de
boundaries y forma parte de `pnpm verify`.

### `scripts/check-import-boundaries.mjs`

El script recorre los archivos fuente, extrae sus imports y verifica:

- No imports relativos (`./*`, `../*`); todo import usa aliases `@/...`.
- `src/shared/**` no importa de `entities`, `features` ni `app`.
- `src/entities/**` no importa de `features` ni `app`. Una entidad puede
  importar OTRA entidad solo a traves de su fachada publica
  (`@/entities/<entity>` o su `index`).
- `src/features/**` no importa de `app`. Un feature puede importar OTRO
  feature solo a traves de su fachada publica (`@/features/<feature>` o su
  `index`); los internals `api/`, `model/` y `ui/` de otro feature quedan
  prohibidos.
- Codigo no-API de `src/app/**` no importa internals `api`, `model` ni `ui`
  de features o entidades; renderiza vistas desde la fachada publica.
- No existe codigo bajo las capas retiradas `src/application`, `src/domain`,
  `src/infrastructure` ni `src/presentation`, ni imports hacia ellas.
- Codigo browser-facing (modulos `"use client"`, `src/features/*/ui/**` y
  `src/shared/ui/**`) no importa `src/settings`,
  `src/shared/api/repositories/*` ni `src/shared/http/requests`, y no lee
  `NEXT_PUBLIC_BACKEND_API_HOST` ni `Settings.apiBaseUrl`.

El script soporta un baseline de violaciones legadas en
`scripts/import-boundary-baseline.txt`; una violacion nueva o una entrada
stale del baseline hacen fallar el check.

Los imports permitidos hacia features y entidades externas pasan por su fachada:

```ts
import { Something } from "@/features/example";
import { UserAvatar } from "@/entities/user";
```

El comando es:

```bash
pnpm check:architecture
```

El objetivo es cero violaciones nuevas.

## 9. HTTP, BFF y autenticacion

`src/shared/http` contiene los clientes y helpers de transporte.

### `server.ts`

`serverHttp` llama al backend desde servidor:

```ts
serverHttp = axios.create({
  baseURL: serverConfig.apiBaseUrl + "/v1",
  timeout: 10000,
});
```

Uso permitido:

- Server Components.
- Route handlers.
- Middleware/proxy cuando corresponda.

### `client.ts`

`localHttp` y `authHttp` usan `baseURL: "/api"`. Desde browser nunca apuntan al
backend directo.

`authHttp` agrega headers desde Zustand:

- `Authorization: Bearer <token>`
- `X-Tenant`
- `X-Client`

El interceptor de respuesta maneja `401/403` con `auth.NotAuthenticated`:

1. Llama una sola vez a `/api/auth/refresh`.
2. Actualiza el access token.
3. Reintenta la request original.
4. Si refresh falla, limpia sesion y redirige a login.

### `bff.ts`

Contiene helpers para:

- Reenviar headers tenant-aware.
- Manejar superficies admin/cross-tenant.
- Reflejar errores upstream sin inventar envelopes.

### Route handlers BFF

Los route handlers viven en `src/app/api/**/route.ts`.

`/api/auth/*` cubre login, logout y refresh:

- Login envia credenciales con `serverHttp`.
- El backend devuelve tokens.
- Next escribe cookies HttpOnly `access_token` y `refresh_token`.
- Refresh lee la cookie HttpOnly y devuelve un nuevo access token para hidratar
  Zustand.

Para APIs simples, el proxy puede reescribir:

```text
/api/v1/:path* -> backend/v1
```

Para multipart o streaming, incluido SSE, se usa route handler explicito con:

```ts
fetch(url, { duplex: "half" });
```

Los route handlers explicitos reutilizan los helpers de `shared/http/bff.ts`
para reenviar headers, credenciales de infraestructura y errores upstream. Si un
caso especial no puede usar el helper tal cual, implementa un helper nuevo en
`shared/http` antes de duplicar logica en una ruta. La excepcion de
multipart/streaming aplica al cuerpo de la request, no al contrato de headers ni
al manejo de errores.

### `src/proxy.ts`

El middleware de Next 16:

- Reescribe `/api/v1/*` al backend con headers server-only.
- Deja pasar `/api/*` interno.
- Redirige usuarios sin refresh token fuera de rutas protegidas.
- Redirige usuarios autenticados fuera de login/register.
- Evita loops limpiando cookies tras varios intentos.

## 10. Errores y envelopes

El contrato base de exito es:

```ts
{ data, datetime }
```

El contrato base de error es:

```ts
{ errors, validation? }
```

`handleHttpError` normaliza `AxiosError` a `ErrorFeedback` con fallback
`genericServerError`. Se usa cuando la UI necesita mensajes normalizados.

`mirrorBackendError` refleja status y payload upstream desde BFF. La BFF no
oculta errores de negocio ni inventa envelopes distintos.

Las request functions lanzan en error. Cuando se consumen desde React Query,
React Query maneja `isError`, retries y boundaries. Si un error se convierte a
`ErrorFeedback`, se relanza como `Error` para conservar ese flujo.

## 11. Realtime y eventos

Realtime es un bus de invalidacion, no una fuente de datos.

Estado objetivo:

- SSE implementado en `src/shared/http/sse.ts` (objetivo, aún no
  implementado).
- Cliente basado en `fetch`, no `EventSource`, para poder enviar
  `Authorization`, `X-Tenant` y `X-Client`.
- Parser de eventos.
- Heartbeats.
- Reconexion con backoff exponencial.
- Cancelacion al limpiar o desmontar la suscripcion.
- Watchdog para conexiones zombies.

Ante un evento realtime, la app invalida query keys de TanStack Query y vuelve a
leer por REST. No se duplica estado remoto dentro del stream.

Los hooks de eventos viven en `shared/hooks` si son transversales. Si solo
aplican a un feature, viven dentro del feature.

## 12. Configuracion, dominio y acceso a datos

### Configuracion

`shared/config/public.ts` contiene solo valores seguros para cliente.

`shared/config/server.ts` contiene valores server-only:

- `BACKEND_API_HOST`
- `BACKEND_API_KEY`
- credenciales de proxy

`server.ts` extiende `publicConfig`, valida `process.env` con zod y falla rapido
si falta una variable requerida.

### Modelo de dominio

Modelos como `User`, `Tenant` o `Member` viven en
`entities/<entity>/model` cuando son compartidos por dos o mas features.

Si un modelo solo pertenece a un feature, vive en `features/<feature>/model`.

### Tipos transversales

`shared/types` contiene tipos no atados a una entidad:

- Envelope `{ data, datetime }`.
- `ErrorFeedback`.
- Paginacion.
- Utilitarios de TypeScript.

Los helpers de error viven en `shared/http/errors.ts`:

- `handleHttpError`
- `mirrorBackendError`
- `isErrorFeedback`
- `genericServerError`

### DTOs de backend

Los DTOs viven junto a la request que los devuelve:

```text
<feature|entity>/api
```

No existe carpeta global `responses/`.

Cuando el backend exporte OpenAPI, la ruta recomendada es generar tipos y
esquemas zod desde ese schema con herramientas como `openapi-typescript` u
`orval`. Los tipos de dominio terminan en `model`; los DTOs de endpoint se
mantienen junto a la request.

### Patron de acceso a datos

El acceso a datos es una funcion async colocalizada con su hook.

```ts
// entities/user/api/get-users.ts
import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";

import { authHttp } from "@/shared/http/client";
import type { ApiEnvelope } from "@/shared/types";

import type { User } from "@/entities/user/model/user";

export const userKeys = {
  all: ["users"] as const,
  detail: (id: string) => ["users", id] as const,
};

export async function getUsers(): Promise<User[]> {
  const res = await authHttp.get<ApiEnvelope<User[]>>("/v1/users");
  return res.data.data;
}

export function useUsers(): UseQueryResult<User[], Error> {
  return useQuery({ queryKey: userKeys.all, queryFn: getUsers });
}
```

Este es el patron por defecto. Si una operacion necesita un adapter, el adapter
debe esconder complejidad real y quedar detras de una interfaz mas pequena que
su implementacion. Los hooks y vistas no instancian clases ni reciben
`AxiosInstance`; consumen request functions, hooks o una fachada publica del
feature/entidad.

## 13. Anatomia de un feature y una entidad

### Feature

```text
src/features/<feature>/
  api/
    get-things.ts
    create-thing.ts
  model/
  ui/
  index.ts
```

`api` contiene una operacion por archivo:

- funcion de request con `authHttp`.
- query keys.
- hook React Query.
- invalidaciones cuando aplica.

`model` contiene:

- esquemas zod del feature.
- stores Zustand feature-specific.
- tipos locales.
- helpers locales.

Si un tipo empieza a ser usado por dos o mas features, sube a
`entities/<entity>/model`.

`ui` contiene vistas, componentes y composicion visual. `"use client"` aparece
solo si el componente lo requiere.

`index.ts` exporta solo la API publica del feature.

Un feature api-only es aceptable (por ejemplo `features/tenants`, que solo
tiene `api/` e `index.ts`); `model/` y `ui/` se agregan cuando hacen falta.

### Entidad

```text
src/entities/<entity>/
  api/
  model/
  ui/
  index.ts
```

`api` contiene request functions, hooks, query keys y DTOs propios de la entidad.

`model` contiene el tipo de dominio, esquemas zod y type guards.

`ui` es opcional y se reserva para piezas presentacionales atadas a la entidad,
por ejemplo `UserAvatar` o `TenantBadge`.

`index.ts` exporta solo la API publica de la entidad.

## 14. Receta TDD para agregar o cambiar un feature

Esta receta describe el orden de trabajo para implementar una change funcional
de OpenSpec en el frontend. No reemplaza `proposal.md`, `design.md`, `tasks.md`
ni los delta specs; los usa como entrada.

Para cambios mecanicos sin comportamiento, usa la misma estructura de carpetas y
los mismos limites, pero sustituye OpenSpec/TDD por una verificacion enfocada:
type-check, tests afectados, `check:architecture`, build o captura visual segun
el riesgo.

### 1. Preparar la change de OpenSpec

Antes de tocar codigo funcional, debe existir una change activa:

```text
openspec/changes/<change-id>/
  proposal.md
  design.md
  tasks.md
  specs/
    <capability>/
      spec.md
```

`proposal.md` define el problema, alcance, non-goals y criterios de aceptacion.
`design.md` define la solucion tecnica, rutas, dependencias, contratos y
decisiones relevantes. `tasks.md` ordena el trabajo en pasos pequenos y
verificables. Los delta specs describen el comportamiento esperado de cada
capability afectada.

La change debe validar antes de implementar:

```bash
openspec validate <change-id> --strict
```

Si el cambio funcional no tiene una change activa, primero se crea. Si el
comportamiento necesario contradice la change, primero se actualiza OpenSpec y
luego se cambia codigo.

### 2. Identificar el feature y las entidades afectadas

La implementacion debe mapear explicitamente la change a carpetas de codigo:

- `src/features/<feature>` para comportamiento de producto.
- `src/entities/<entity>` para modelos usados por dos o mas features.
- `src/shared` solo para infraestructura generica sin dominio.
- `src/app` solo para rutas, layouts, metadata y route handlers.

Cuando el feature no existe, se genera el esqueleto:

```bash
pnpm gen:feature <feature>
```

El resultado esperado es:

```text
src/features/<feature>/
  api/
  model/
  ui/
  index.ts
```

### 3. Definir contratos primero

Antes de escribir UI o requests, se definen las formas de datos:

- Esquemas zod para formularios, validacion y payloads relevantes.
- Tipos de dominio en `model/`.
- DTOs junto a la request que los consume o devuelve, dentro de `api/`.
- Tipos transversales solo en `shared/types`.

La ubicacion depende del alcance:

- Si el tipo lo usa un solo feature, vive en `features/<feature>/model`.
- Si el tipo lo usan dos o mas features, vive en `entities/<entity>/model`.
- Si describe un envelope, paginacion o utilitario agnostico, vive en
  `shared/types`.

Los contratos deben reflejar OpenSpec y, cuando exista OpenAPI del backend, se
prefieren tipos/esquemas generados desde ese schema.

### 4. Escribir el test rojo

Cada tarea funcional empieza con un test que falla por la razon correcta.
Excepciones aceptadas: cambios puramente documentales, exports de fachada,
renombres mecanicos, codemods, ajustes de boundaries y cambios visuales menores
sin estado ni contrato. En esos casos se documenta el gate usado para cubrir el
riesgo real del cambio.

Usar Vitest para:

- schemas zod y validaciones.
- request functions y manejo de errores con MSW.
- hooks de React Query.
- componentes y estados de UI.
- guards, permisos, stores y helpers.

Usar Playwright para:

- journeys criticos de usuario.
- navegacion entre rutas.
- formularios completos.
- flujos autenticados.
- regresiones que cruzan varios features.

El test debe derivarse de un criterio de aceptacion de OpenSpec. Si no hay un
criterio claro que permita escribir el test, se actualiza primero la change.

### 5. Implementar datos hasta verde

La capa `api/` se implementa una operacion por archivo:

```text
src/features/<feature>/api/
  get-items.ts
  create-item.ts
```

Cada archivo contiene:

- funcion async de request con `authHttp` o `serverHttp`, segun superficie.
- tipos DTO locales de esa operacion.
- query keys.
- hook `useQuery` o `useMutation`.
- invalidaciones de TanStack Query cuando aplica.

Las request functions lanzan en error. No capturan errores para devolver
resultados ambiguos. Cuando la UI necesita mensajes normalizados, se usa
`handleHttpError` y se relanza como `Error`.

Si aparece un adapter, debe ser interno a la capa `api/` del feature/entidad o a
`shared/http` si es transporte generico. El adapter debe pasar el deletion test:
al borrarlo, complejidad real deberia reaparecer duplicada en varios callers. Si
solo envolvia `authHttp.get/post`, se elimina.

### 6. Implementar UI hasta verde

La capa `ui/` contiene vistas y componentes del feature. La UI consume la fachada
publica de entidades y shared UI, no internals de otros features.

Reglas practicas:

- `"use client"` solo cuando el componente usa estado, eventos, React Query,
  hooks de navegacion o APIs del browser.
- Server Components para superficies publicas o solo-lectura.
- Componentes genericos y sin dominio suben a `shared/ui`.
- Navegacion de producto, permisos y shell autenticado permanecen en
  `features/app-shell`.
- Textos visibles usan `next-intl`; no quedan strings hardcodeados cuando el
  feature es visible para usuarios.

### 7. Conectar ruta y fachada publica

La ruta en `src/app` debe ser delgada:

```tsx
import { FeatureView } from "@/features/<feature>";

export default function Page() {
  return <FeatureView />;
}
```

El `index.ts` del feature exporta solo lo que otros modulos pueden usar. No se
exportan detalles internos por conveniencia.

Ejemplo de fachada:

```ts
export { FeatureView } from "@/features/<feature>/ui/feature-view";
export { useFeatureItems } from "@/features/<feature>/api/get-feature-items";
export type { FeatureFormValues } from "@/features/<feature>/model/feature-schema";
```

### 8. Refactor y limites

Cuando los tests estan en verde, se limpia la implementacion:

- Extraer duplicacion real, no abstracciones especulativas.
- Mantener archivos pequenos y enfocados.
- Mover genericos a `shared` solo si no conocen dominio.
- Mover modelos a `entities` solo cuando los usan dos o mas features.
- Confirmar que no haya imports profundos entre features o entre entidades.
- Confirmar que React Query sigue siendo la cache unica de estado remoto
  cliente.
- Confirmar que Zustand no duplica listas o detalle remoto.
- Confirmar que cada adapter nuevo es un modulo profundo con interfaz pequena y
  complejidad real escondida.

### 9. Cerrar la tarea y el gate

Cada tarea marcada en `openspec/changes/<change-id>/tasks.md` debe tener una
verificacion asociada: test, type-check, lint, boundary check o build.

El gate final de la change es:

```bash
openspec validate <change-id> --strict
pnpm verify
```

Si `pnpm verify` falla, la change no esta terminada. Si la implementacion cambia
el comportamiento esperado, OpenSpec se actualiza antes de considerar cerrado el
trabajo.

## 15. Shell de aplicacion

`features/app-shell` contiene el shell autenticado transversal:

- `AppShell`
- sidebar
- header
- breadcrumbs
- area principal
- `ThemeProvider`
- `ThemeSwitcher`
- `SessionSync`
- `StoreInitializer`
- `PermissionGuard`
- navegacion de producto (`AppSidebar`, `NavUser`, `TenantHead`)

Estos elementos no viven en `shared/ui` porque estan acoplados al producto
autenticado.

Si existe una consola administrativa cross-tenant, vive bajo `src/app/admin` con
shell y helpers BFF propios. Esa superficie reenvia solo `Authorization` y
credenciales de infraestructura, sin `X-Tenant`.

## 16. Providers globales

`src/app/layout.tsx` monta providers globales en este orden:

```tsx
<NextIntlClientProvider>
  <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
    <QueryProvider>
      <SessionProvider>{children}</SessionProvider>
    </QueryProvider>
  </ThemeProvider>
</NextIntlClientProvider>
```

`QueryProvider` mantiene un `QueryClient` estable con `useState`:

- `staleTime: 60_000`
- `retry: 1`
- devtools opcional

`SessionProvider` lee de un store Zustand y expone:

- `user`
- `tenant`
- rol/permisos
- `isAuthenticated`
- `isLoading`

## 17. Estado cliente, UI compartida e i18n

### Zustand

Zustand se usa solo para estado cliente transversal o persistible.

El store de sesion vive en `src/features/auth/model/session-store.ts` y expone
`useSessionStore` con:

- usuario.
- tenant.
- rol del tenant.
- access token en memoria.

Los tipos de sesion compartidos (`jwt-session`, `tenant-user-session`) viven en
`entities/session/model`; la entidad no contiene el store.

El refresh token no se persiste en cliente. React Query sigue siendo la cache
unica de estado remoto cliente; Zustand no duplica listas remotas.

### `shared/ui`

`shared/ui` es el design system operativo:

- shadcn.
- Tailwind v4.
- Base UI.
- tokens en `globals.css`.

Componentes esperados:

- `button`
- `dialog`
- `input`
- `select`
- `tabs`
- `table`
- `tooltip`
- `sheet`
- `sidebar`
- `spinner`
- `empty-state`
- `PageContent` con `Header` y `Body`

`shared/ui` no contiene navegacion de producto, permisos ni llamadas API.

### `next-intl`

Estructura objetivo:

```text
i18n/
  config.ts
  request.ts
  actions.ts
  messages/
    es.json
    en.json
```

`request.ts` lee cookie y carga mensajes. `actions.ts` expone `setLocale`.
Componentes usan `useTranslations("<namespace>")`.

Tests usan un helper:

```text
tests/render-with-intl.tsx
```

## 18. Testing, scripts y gate unico

Scripts objetivo en `package.json`:

```json
{
  "build": "next build",
  "lint": "biome lint .",
  "format": "biome format .",
  "format:write": "biome format --write .",
  "check": "biome check .",
  "type-check": "tsc --noEmit",
  "test": "vitest run",
  "test:e2e": "playwright test --pass-with-no-tests",
  "lint:boundaries": "node scripts/check-import-boundaries.mjs",
  "check:architecture": "pnpm lint:boundaries",
  "gen:feature": "node scripts/gen-feature.mjs",
  "verify": "pnpm type-check && pnpm check && pnpm test && pnpm check:architecture && pnpm build"
}
```

Vitest:

- `jsdom`.
- `tests/setup.ts`.
- aliases alineados con `tsconfig`.
- helper que monta `NextIntlClientProvider`.
- MSW para mockear `/api`.
- handlers derivados de los mismos esquemas zod cuando sea posible.

Playwright:

- tests en `tests/end-to-end` (objetivo, aún no implementado; por eso
  `test:e2e` usa `--pass-with-no-tests`).
- `baseURL: http://localhost:3000`.
- `webServer.command = "pnpm dev"`.

CI ejecuta `pnpm verify`.
