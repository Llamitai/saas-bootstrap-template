---
title: "Arquitectura frontend"
description: "Contrato vigente del frontend Next.js: capas, límites de import, HTTP/BFF, caché, testing y deuda conocida."
icon: LayoutTemplate
---

Este documento describe el contrato vigente del frontend: lo que el código hace
hoy y las reglas que todo cambio debe preservar. Las ideas objetivo que aún no
existen en el código viven en [el roadmap frontend](roadmap-frontend.md) y no son
contrato hasta que una change las implemente.

`AGENTS.md` es el mapa compartido del unirepo. Las rutas `src/`, `tests/` y
`scripts/` de esta guía son relativas a `frontend/`; OpenSpec y las recetas
`just` se ejecutan desde la raíz Git.

## Índice

1. [Reglas vinculantes](#1-reglas-vinculantes)
2. [Stack](#2-stack)
3. [Estructura y capas](#3-estructura-y-capas)
4. [Límites de import](#4-límites-de-import)
5. [Server, Client, Server Functions y Proxy](#5-server-client-server-functions-y-proxy)
6. [HTTP, BFF y autenticación](#6-http-bff-y-autenticación)
7. [Envelopes y errores](#7-envelopes-y-errores)
8. [Estado remoto y caché](#8-estado-remoto-y-caché)
9. [Configuración y secretos](#9-configuración-y-secretos)
10. [Estado cliente, formularios, i18n y temas](#10-estado-cliente-formularios-i18n-y-temas)
11. [Shell y providers globales](#11-shell-y-providers-globales)
12. [Testing](#12-testing)
13. [Flujo de trabajo](#13-flujo-de-trabajo)
14. [Deuda conocida](#14-deuda-conocida)

## 1. Reglas vinculantes

1. La unidad principal es el **feature** (`src/features/<feature>`). Un modelo
   usado por dos o más features vive en `src/entities/<entity>`; si lo usa uno
   solo, vive en ese feature.
2. El flujo de dependencias es unidireccional: `app -> features -> entities ->
   shared`. Cada capa solo importa de las capas a su derecha.
3. Cada feature y entidad expone una fachada pública (`index.ts`). Nadie importa
   internals (`api/`, `model/`, `ui/`) de otro slice.
4. `src/app` es delgada: rutas, layouts, metadata y route handlers que componen
   vistas de feature. Sin lógica de negocio.
5. El browser no llama al backend directo: todo tráfico cliente pasa por rutas
   same-origin `/api/...` de Next.js. Las credenciales de infraestructura
   (`BACKEND_API_KEY`, Cloudflare Access) solo existen en servidor.
6. TanStack Query es la única caché de estado remoto en cliente; Zustand guarda
   solo estado cliente (sesión, borradores, wizard, UI). Ningún store duplica
   listas o detalle remoto.
7. Formularios con `react-hook-form` + `zodResolver`; textos visibles con
   `next-intl`; temas claro/oscuro vía tokens semánticos; acceso por teclado,
   foco visible, labels y estados de carga/vacío/error/recuperación observables.
8. Los límites se verifican con `scripts/check-import-boundaries.mjs`
   (`pnpm check:architecture`), no con disciplina manual.

## 2. Stack

Las versiones vivas están en `package.json`; no se copian aquí. Piezas activas:
Next.js App Router, React, TypeScript estricto, Tailwind CSS v4 (tokens en
`src/app/globals.css`), shadcn + Base UI (`@base-ui/react`) en `src/shared/ui`,
TanStack Query, Zustand, Axios, `react-hook-form` + `zod` +
`@hookform/resolvers`, `next-intl`, `next-themes`, Biome, Vitest + Testing
Library y Playwright. MSW y un cliente SSE no están instalados (ver roadmap).

Biome (`biome.json`, `preset: "none"`) activa un subconjunto explícito de reglas
Next (`noImgElement`, `noHeadElement`, `noDocumentImportInPage`,
`noHeadImportInDocument`, `useGoogleFontDisplay`, `useGoogleFontPreconnect`,
`noUnwantedPolyfillio`), las reglas de hooks de React
(`useHookAtTopLevel` como error y `useExhaustiveDependencies` como warning) y el
grupo `a11y` recomendado. Dentro de `a11y`, `noLabelWithoutControl` reconoce
`Checkbox`, `Input`, `Select`, `Switch` y `Textarea` como controles, y
`useSemanticElements`, `noStaticElementInteractions`, `useKeyWithClickEvents` y
`useValidAnchor` quedan en `warn` por violaciones pendientes (ver §14). El
`$schema` de `biome.json` sigue la versión instalada de Biome.

Aliases reales de `tsconfig.json`:

```json
"paths": {
  "@/features/*": ["./src/features/*"],
  "@/entities/*": ["./src/entities/*"],
  "@/shared/*": ["./src/shared/*"],
  "@/*": ["./*"],
  "@/images/*": ["./public/images/*"],
  "@/public/*": ["./public/*"]
}
```

Los imports de arquitectura usan `@/features`, `@/entities` y `@/shared`. Código
fuera de esas capas (`src/app`, `src/i18n`, `src/constants.ts`) se importa como
`@/src/...`.

## 3. Estructura y capas

```text
src/
  app/                  # App Router: (public)/, (protected)/ con (shell)/,
                        # api/ (BFF), layout.tsx, page.tsx, globals.css
  features/             # app-shell, auth, members, profile, roles,
                        # settings, superuser, tenants
    <feature>/
      api/              # un archivo por recurso (ver abajo)
      model/            # zod, tipos, stores Zustand y helpers del feature
      ui/               # vistas y componentes del feature
      index.ts          # fachada pública
      server.ts         # opcional: fachada server-only (hoy solo auth)
  entities/             # member, permission, session, tenant, tenant-role, user
    <entity>/
      model/            # tipos de dominio, zod, enums, type guards
      index.ts          # fachada pública
  shared/
    catalogs/           # catálogos estáticos (países, monedas, zonas horarias)
    config/             # public.ts, server.ts
    helpers/            # jwt-token, lectura de cookies de sesión en servidor
    hooks/              # hooks genéricos sin dominio (use-mobile,
                        # use-http-error-message, ...)
    http/               # clientes, BFF helpers, errores, headers, cookies
    lib/                # utilidades puras (fechas, cn, ids)
    providers/          # QueryProvider
    types/              # tipos transversales (RequestContext, TaskResult)
    ui/                 # design system; ui/components/ y ui/components/ui/
                        # contienen visores y piezas compuestas genéricas
  i18n/                 # config.ts, request.ts, actions.ts, messages/{en,es}.json
  proxy.ts              # Proxy de Next 16
  constants.ts
scripts/                # check-import-boundaries.mjs, gen-feature.mjs
tests/                  # ver §12
```

Hoy las entidades solo tienen `model/`; un `api/` o `ui/` de entidad se agrega
cuando dos features comparten request o pieza visual. Un feature puede ser
api-only (`features/tenants`). `pnpm gen:feature <name>` (o
`just frontend new-feature <name>`) crea `api/`, `model/`, `ui/` e `index.ts` y
rechaza un feature existente.

Responsabilidades:

- `src/app` no contiene lógica de negocio. `page.tsx` renderiza una vista de la
  fachada del feature.
- `src/shared` no conoce features ni entidades ni contiene DTOs de negocio,
  permisos o navegación de producto. No hay `shared/model` ni stores en shared.
- Los DTOs viven junto a la request que los devuelve (en `api/` o en los tipos
  del `model/` del feature); no existe carpeta global `responses/`.
- No se crean interfaces o clases repositorio que solo envuelven Axios. Un
  adapter se justifica si esconde complejidad real repetida (multipart,
  streaming, retry, headers) o tiene dos implementaciones reales; si al borrarlo
  no reaparece duplicación, sobra.

### `api/`: un archivo por recurso

Cada archivo de `api/` agrupa un recurso (`members.ts`, `roles.ts`,
`settings.ts`, `tenants.ts`, `profile-api.ts`) y contiene:

- request functions async sobre `authHttp` que devuelven `response.data.data`;
- el factory de query keys del recurso (`memberKeys`, `roleKeys`, ...);
- hooks `useQuery`/`useMutation`;
- invalidaciones en `onSuccess` de las mutaciones.

Un recurso sin estado remoto cacheado puede exponer solo request functions
(`onboard-tenant.ts`, `auth-api.ts`).

Archivos `*-server.ts` (por ejemplo `auth-server.ts`, `invitations-server.ts`)
contienen requests que corren solo en servidor con `serverHttp` o `fetch`.

### Fachadas públicas

`index.ts` exporta solo la API pública del slice. `features/auth` tiene además
`server.ts`, una fachada server-only que reexporta `loginBackend`,
`logoutBackend`, `refreshBackendSession`, `rotateBackendSession`,
`getBackendSession` y `googleLoginBackend`; la consumen los route handlers de
`src/app/api/auth/**`, `src/proxy.ts` y el layout protegido. Un slice nuevo que
necesite código server-only sigue ese patrón en lugar de mezclarlo en `index.ts`.

## 4. Límites de import

`scripts/check-import-boundaries.mjs` recorre con el AST de TypeScript todos los
archivos JS/TS de `frontend/` (incluidos `tests/` y `scripts/`, excepto
`node_modules`, `.next` y salidas de build): imports, reexports, `import type`,
`require` e `import()` con literal. No resuelve imports dinámicos calculados ni
fugas transitivas. Reglas:

- Prohibidos los imports relativos (`./`, `../`); todo usa aliases `@/...`.
- `src/shared/**` no importa `entities`, `features` ni `app`.
- `src/entities/**` no importa `features` ni `app`; otra entidad solo por su
  fachada (`@/entities/<entity>`).
- `src/features/**` no importa `app`; otro feature solo por su fachada
  (`@/features/<feature>` o su `index`), y cualquier entidad solo por su fachada.
- Código de `src/app/**` fuera de `src/app/api/**` no importa `api/`, `model/` ni
  `ui/` de features o entidades. Los route handlers de `src/app/api/**` están
  exentos de esta regla (las rutas de página sí pueden usar `@/features/<f>/server`).
- Las capas retiradas `src/application`, `src/domain`, `src/infrastructure` y
  `src/presentation` no pueden existir ni importarse.
- Código browser-facing (módulos `"use client"`, `src/features/*/ui/**`,
  `src/shared/ui/**`) no importa `next/headers`, `server-only`,
  `@/shared/config/server`, `@/shared/http/server`, `@/shared/http/bff`,
  `@/shared/http/session-cookies` ni `@/shared/http/requests`, y no puede
  contener el texto `NEXT_PUBLIC_BACKEND_API_HOST`.

El script acepta un baseline opcional en `scripts/import-boundary-baseline.txt`;
hoy no existe, así que cualquier violación falla. Si se crea, una entrada stale
también falla. `pnpm check:architecture` corre dentro de `pnpm check:static` y
`pnpm verify`.

## 5. Server, Client, Server Functions y Proxy

- Server Components por defecto. `"use client"` solo cuando el componente usa
  estado, eventos, React Query, hooks de navegación o APIs del browser.
- Superficies públicas o solo-lectura (invitaciones, reset de contraseña)
  renderizan en servidor; `loadInvitation` lee con `fetch` en servidor.
- Superficies autenticadas son vistas cliente sobre `authHttp` + React Query;
  las rutas (`page.tsx`, `layout.tsx`) son Server Components delgados que
  componen la vista del feature y usan `getTranslations` cuando necesitan
  texto.
- `src/app/(protected)/layout.tsx` es `force-dynamic`: lee la cookie de access
  token, lee la sesión con `getBackendSession` (`GET /v1/auth/session`, sin
  rotar) y redirige a `/` o `/unassigned`; luego monta `SessionSync` y
  `StoreInitializer` dentro de un `Fragment` con `key` igual al slug del tenant,
  para remontar el subárbol al cambiar de tenant.
- `src/app/(protected)/(shell)/layout.tsx` monta `AppShell` una sola vez para
  miembros, roles, configuración y perfil; el sidebar, la animación compartida
  del indicador de navegación (`layoutId`) y el panel de ayuda persisten entre
  navegaciones. `/forbidden` queda fuera del shell. Cada segmento protegido por
  permiso tiene un único `PermissionGuard`, en su `layout.tsx`.
- No hay prefetch/hidratación de React Query desde servidor
  (`HydrationBoundary`) ni `cacheComponents`/`'use cache'`. Activarlos cambia el
  modelo de datos y de sesión y requiere un ADR.

**Server Functions.** Hoy solo existe `src/i18n/actions.ts` (`setLocale`), que
valida el locale antes de escribir la cookie. Una Server Function es un endpoint
POST público: valida su entrada con zod y verifica autenticación y autorización
dentro de ella; no confía en el layout ni en el Proxy. Se usan para mutaciones,
no para lecturas (las lecturas van por Server Components o React Query).

**Proxy.** Next 16 renombró Middleware a Proxy (`src/proxy.ts`). Hace
redirecciones optimistas basadas en la cookie de refresh (`/` si falta o expiró,
`/members` si existe en una ruta pública, limpieza de cookies tras
`MAX_REFRESH_ATTEMPTS` rebotes), el rewrite de `/api/v1/*` y la rotación de
sesión de las navegaciones protegidas. La autorización real vive en el backend y
en el layout protegido; el matcher no cubre todo y no es frontera de seguridad.

**Regla de rotación de sesión.** Solo `src/proxy.ts` o un route handler rotan el
refresh token o escriben cookies de sesión; los Server Components leen la sesión
sin rotar. El backend revoca el refresh token presentado al rotarlo, así que una
rotación cuyo resultado no llega al navegador deja una cookie revocada y cierra
la sesión en la siguiente recarga. En una navegación protegida con la cookie de
access token ausente o a menos de 30 s de expirar (se lee `exp` sin verificar la
firma, suficiente para enrutar), el Proxy llama `rotateBackendSession`, escribe
ambas cookies con `setSessionCookies` y reenvía las nuevas al render
sobrescribiendo el header `Cookie` (`NextResponse.next({ request: { headers } })`).

**Clasificación de fallos de sesión.** Solo un rechazo real cierra la sesión:
`isSessionRejected` es verdadero con `401`/`403` o con los códigos
`auth.InvalidRefreshToken`, `common.InvalidRefreshToken`,
`common.InvalidOrExpiredToken` o `users.UserNotFound`. Un `429`, un `5xx`, un
timeout o un backend inalcanzable (`502` sintético) son transitorios y conservan
las cookies:

| Quién | Rechazo | Transitorio |
|---|---|---|
| Proxy (navegación) | limpia cookies y redirige a `/` | responde `503` HTML breve con `Retry-After` (el del backend, 5 s por defecto, máximo 120 s) y recarga sola |
| `/api/auth/refresh` | limpia cookies y responde `401` | refleja el status (y `Retry-After`) sin tocar cookies |
| `client.ts` | limpia la sesión y navega a `/` | rechaza la petición original con su error, sin cerrar sesión |
| Layout protegido | redirige a `/` | lanza error de render; no redirige |

Redirigir a `/` ante un fallo transitorio entraría al ciclo `/` → `/members` y
agotaría `MAX_REFRESH_ATTEMPTS`, que sí borra la sesión.

`rotateBackendSession` comparte una rotación en curso, y su resultado durante
15 s, entre peticiones con el mismo refresh token (recarga más prefetches RSC,
varias pestañas), de modo que la segunda no revoca a la primera. El caché vive
en cada instancia del módulo: el Proxy y los route handlers son bundles
distintos y no lo comparten, igual que varias instancias de Next. La ventana de
gracia del backend (un refresh token recién rotado presentado de nuevo en pocos
segundos devuelve el mismo par nuevo) resuelve esas carreras. El route handler
`/api/auth/refresh` sigue siendo el camino del cliente y usa la misma función.

## 6. HTTP, BFF y autenticación

`src/shared/http`:

- `client.ts`: `localHttp` (timeout 10 s) y `authHttp` (sin timeout), ambos con
  `baseURL: "/api"`. Un interceptor adjunta `X-Client`, `X-Tenant` y
  `Authorization: Bearer` desde `auth-context.ts`, cuyo lector registra
  `features/auth/model/session-store.ts` (shared no importa el store). Ante
  `401`, o `403` con código `auth.NotAuthenticated`, hace un único refresh
  deduplicado a `/api/auth/refresh`, actualiza el token y reintenta; si el
  refresh responde `401`, limpia la sesión y navega a `/`; ante otro status o
  un error de red rechaza la petición original sin cerrar sesión.
- `server.ts`: `serverHttp` (Axios, `baseURL: <apiBaseUrl>/v1`, timeout 10 s)
  para route handlers y código server-only.
- `bff.ts`: `backendHeadersFrom(request)` reenvía `Authorization` y
  `X-Tenant`, agrega `X-Api-Key` y credenciales Cloudflare Access server-only, y
  fija `X-Client-IP` con la IP que resuelve `resolveClientIp`: el header de un
  edge de confianza si `TRUSTED_CLIENT_IP_HEADER` lo nombra (por ejemplo
  `cf-connecting-ip` o `x-real-ip`) o, sin él, el último salto de
  `X-Forwarded-For` (el más cercano a Next, que lo rellena con la IP del socket
  si falta). Si el valor no es una IPv4/IPv6 válida, el header se omite. El
  backend confía en `X-Client-IP` solo junto a un `X-Api-Key` válido y lo usa
  para sus límites por cliente. Toda llamada server-only al backend lleva ambos
  headers: route handlers de auth (login, logout, refresh, Google, reset,
  confirmación de reset, aceptación de invitación), la rotación del Proxy, el
  layout protegido y el rewrite `/api/v1/*`, que además borra cualquier
  `X-Client-IP` enviado por el navegador;
  `mirrorBackendError(error)` refleja status y payload upstream, o responde
  `502` con `bff.upstream_unreachable`.
- `errors.ts`: `ErrorFeedback`, `handleHttpError`, `normalizeErrorFeedback`,
  `isErrorFeedback`, `genericServerError` y helpers de clasificación.
- `session-cookies.ts`: escribe y limpia las cookies HttpOnly de sesión
  (`setSessionCookies`, `clearSessionCookies`). Sus nombres vienen de
  `src/constants.ts`: `___AT5___` (access token, 15 min), `___RT5___` (refresh
  token, 7 días) y `___RA5___` (contador de rebotes del Proxy, 60 s).

**Route handlers BFF** (`src/app/api/auth/**/route.ts`): login, logout,
refresh, Google OAuth (+ callback), reset de contraseña (+ confirm) y aceptación
de invitación. Login envía credenciales con `serverHttp`, escribe las cookies
HttpOnly de access y refresh token y devuelve la sesión al cliente (sin tokens);
refresh lee la cookie, rota con `rotateBackendSession`, reescribe ambas cookies
y devuelve un access token nuevo para Zustand. Ambos reenvían el `timestamp` del
backend. Un route handler
nuevo reutiliza `backendHeadersFrom` y `mirrorBackendError`; si no le sirven,
extiende `shared/http` antes de duplicar lógica.

**Rewrite `/api/v1/*`.** El resto de endpoints (`authHttp.get("/v1/...")`) pasan
por `src/proxy.ts`, que reescribe al backend con `X-Api-Key`, Cloudflare Access y
`Authorization` derivado de la cookie cuando el cliente no lo envía.
`next.config.ts` declara además un rewrite `afterFiles` equivalente; como el
Proxy corre antes, ese rewrite es redundante (ver §14). Multipart funciona hoy
por el rewrite (`uploadMemberPhoto`); streaming o SSE necesitarían un route
handler explícito.

## 7. Envelopes y errores

Contratos del backend (`backend/src/common/infrastructure/responses/api_json.py`):

```ts
{ data, timestamp }                  // éxito
{ data, pagination, timestamp }      // éxito paginado
{ errors, validation?, timestamp }   // error
```

No existe `ApiEnvelope` en `@/shared/types`: cada archivo `api/` declara
localmente `type ApiEnvelope<T> = { data: T }` y devuelve `response.data.data`.
El BFF no inventa envelopes: refleja el error upstream con `mirrorBackendError`.

Las request functions lanzan en error; React Query maneja `isError` y retries.
Cuando la UI necesita mensajes normalizados usa `handleHttpError` y, si relanza,
lo hace como `Error` para conservar ese flujo.

`shared/http` produce códigos (`UNAUTHORIZED`, `NETWORK_ERROR`,
`bff.upstream_unreachable`, ...) con mensajes en inglés solo como respaldo
técnico. El texto visible sale del catálogo `HttpErrors`, indexado por código
con `.` reemplazado por `_`, mediante `useHttpErrorMessage()`
(`shared/hooks/use-http-error-message.ts`): traduce los códigos conocidos,
conserva el mensaje del backend para códigos de dominio sin entrada y, si no
hay ninguno, usa el respaldo traducido que pasa la vista.

## 8. Estado remoto y caché

- `QueryProvider` (`src/shared/providers/query-provider.tsx`) crea un
  `QueryClient` estable con `useState`: `staleTime: 60_000`, `retry: 1`, devtools.
- El estado remoto de cada feature vive en hooks de su `api/` (por ejemplo
  `useProfileQuery`, `useUpdateProfileMutation`); una mutación que cambia datos
  reflejados en la sesión actualiza también el store de sesión.
- Las mutaciones invalidan las keys del recurso afectado en `onSuccess`.
- Para keys nuevas se recomienda un factory con `queryOptions()` de TanStack
  Query v5 (key + `queryFn` tipados y reutilizables en `useQuery`,
  `prefetchQuery` o `setQueryData`); el código actual usa objetos de keys y aún
  no lo adopta.

**Regla de alcance de caché.** Los datos remotos dependen del usuario y del
tenant activos. Toda query cumple una de dos condiciones: su key empieza por el
scope (tenant/usuario) o el cambio de scope destruye la caché. Hoy las keys
(`memberKeys`, `roleKeys`, `settingsKeys`, ...) no incluyen el scope, así que
aplica la segunda vía: el cambio de tenant (`TenantHead`) hace navegación
completa con `window.location.assign`; `clearSession` de `useSessionActions`
(logout, `/forbidden`, `/unassigned`) llama `queryClient.clear()`, y el login
con contraseña limpia la caché antes de guardar la nueva sesión. Un refresh
rechazado en `client.ts` navega con recarga completa a `/`.

## 9. Configuración y secretos

`shared/config/public.ts` (seguro para cliente): `version`
(`NEXT_PUBLIC_VERSION`, por defecto `"1.0.0"`) e `isProd`
(`NODE_ENV === "production"`).

`shared/config/server.ts` (server-only) extiende `publicConfig` sin validación:
lee `process.env` con valores por defecto y no falla si falta una variable.

| Clave | Variable | Por defecto |
|---|---|---|
| `apiBaseUrl` | `NEXT_PUBLIC_BACKEND_API_HOST`, luego `BACKEND_API_HOST` | `http://localhost:8200` |
| `apiKey` | `BACKEND_API_KEY` | `""` |
| `cfAccessClientId` / `cfAccessClientSecret` | `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` | `""` |
| `googleClientId` | `GOOGLE_CLIENT_ID` | `""` |
| `appUrl` | `NEXT_PUBLIC_APP_URL` | `""` (usa el origin de la request) |

Regla para módulos nuevos: un módulo que lee secretos o llama al backend con
credenciales de infraestructura empieza con `import "server-only"`, que produce
error de build si llega a un bundle cliente. Los módulos existentes aún no lo
usan; hoy la protección es el boundary script (§4).

## 10. Estado cliente, formularios, i18n y temas

**Zustand.** `features/auth/model/session-store.ts` (`useSessionStore`) guarda
usuario, tenant, rol y access token. `persist` guarda en `localStorage` solo
usuario, tenant y rol; el access token vive en memoria y el refresh token solo en
cookie HttpOnly. Otros stores son del feature y guardan solo estado cliente
(`onboard-tenant-wizard-store`). Los tipos de sesión
compartidos viven en `entities/session/model`.

**Formularios.** `react-hook-form` + `zodResolver` con el schema del `model/`
del feature (referencia: `features/auth/ui/auth-form.tsx`). Errores inline por
campo y errores de servidor vía `ErrorFeedback`.

**i18n.** `src/i18n/request.ts` resuelve el locale desde la cookie y carga
`messages/{en,es}.json`; `actions.ts` expone `setLocale`. Los componentes cliente
usan `useTranslations("<namespace>")` y los Server Components
`getTranslations`; ningún texto visible queda hardcodeado (atributos
`aria-label`, `placeholder` y `title` incluidos). Toda clave nueva se agrega a
todos los catálogos. La metadata de una ruta se traduce con `generateMetadata`,
nunca con un `metadata.title` estático:

```tsx
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("PageTitles");
  return { title: t("members") };
}
```

**Temas.** `ThemeProvider` (`next-themes`, `attribute="class"`,
`defaultTheme="system"`) alterna `.dark`, que redefine los tokens en
`globals.css`. Reglas visuales en [DESIGN.md](../../../../DESIGN.md).

**`shared/ui`.** Primitives shadcn/Base UI y piezas genéricas (`PageContent`,
`EmptyState`, filtros, visores). Sin navegación de producto, permisos ni llamadas
API. Botones con carga usan el estado `loading` del `Button` compartido.

Los primitives nuevos se agregan con `pnpm dlx shadcn@latest add <item>` desde
`frontend/`. `components.json` apunta los aliases a rutas permitidas: `ui` a
`@/shared/ui`, `components` a `@/shared/ui/components`, `utils` a
`@/shared/lib/utils`, `lib` a `@/shared/lib` y `hooks` a `@/shared/hooks`.
`pnpm dlx shadcn@latest info` muestra las rutas resueltas. Después de agregar un
primitive se traducen sus textos visibles y se corre `just frontend check`.

## 11. Shell y providers globales

`features/app-shell` contiene el shell autenticado: `AppShell`, `AppSidebar`,
`ShellHeader`, `NavUser`, `TenantHead`, `HelpSidebar`, `PermissionGuard`,
`SessionSync`, `StoreInitializer`, `ThemeProvider`, `ThemeSwitcher` y
`SuperuserActionsMenu`. No vive en `shared/ui` porque conoce el producto.
`PermissionGuard` complementa la autorización del backend; nunca la reemplaza.
`AppShell` recibe solo `children`: deriva la entrada activa del sidebar y el
breadcrumb del pathname con `resolveShellRoute` (`sidebar-config.ts`), así que
una página nueva del shell se registra allí y no en su `page.tsx`.

`src/app/layout.tsx` monta:

```tsx
<NextIntlClientProvider>
  <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
    <QueryProvider>
      <SessionProvider>{children}</SessionProvider>
    </QueryProvider>
  </ThemeProvider>
</NextIntlClientProvider>
```

## 12. Testing

```text
tests/
  api/features/<feature>/          # request fns, keys, hooks (Vitest)
  models/features/<feature>/       # schemas zod y reglas del model (Vitest)
  components/features/<feature>/   # componentes y estados de UI (Vitest + RTL)
  unit/                            # shared/http, BFF y helpers
  end-to-end/*.spec.ts             # Playwright smoke
  end-to-end/*.integration.spec.ts # Playwright contra API real
  end-to-end/support/              # helpers de seed/login para integración
  setup.ts                         # jest-dom + cleanup
  render-with-intl.tsx             # render con NextIntlClientProvider (locale "en")
```

- Vitest (`vitest.config.ts`): `jsdom`, incluye `tests/**/*.{test,spec}.{ts,tsx}`
  y excluye `tests/end-to-end/**`.
- Doble de transporte: `vi.mock("@/shared/http/client", ...)` reemplaza
  `authHttp`/`localHttp` (referencia: `tests/api/features/roles/roles-api.test.ts`).
  MSW no está instalado.
- Playwright (`playwright.config.ts`): `testDir: tests/end-to-end`, un worker,
  arranca su propio `pnpm dev` en `E2E_PORT` (3100 por defecto) y nunca reutiliza
  un servidor. Los `*.integration.spec.ts` se ignoran salvo con
  `E2E_INTEGRATION=1`, que activa `just integration` con un stack API
  exclusivo. Los reportes van a `tests/reports/playwright/<E2E_RUN_ID>/`.
- Selectores por rol/label; se prueban estados observables, no implementación.

## 13. Flujo de trabajo

El alcance, los criterios y el plan de verificación se definen con
[define-change](../../../../.claude/skills/define-change/SKILL.md); un cambio
funcional usa una change OpenSpec (`just spec-check <id>` para su estructura) y
el cierre lo decide [validate-change](../../../../.claude/skills/validate-change/SKILL.md).
La selección de checks está en [la guía de verificación](../equipo/verificacion.md). Recetas
en `just frontend` y scripts en `frontend/package.json`: `just frontend check`
es estático sin autofix; `just frontend verify` agrega Vitest y build;
`just frontend lint`/`format` modifican archivos.

Receta red → green para un comportamiento (detalle en
[tdd](../../../../.claude/skills/tdd/SKILL.md)):

1. Ubicar el código: feature, entidad (solo si lo comparten 2+ features),
   shared (solo genérico) o `app` (solo rutas).
2. Escribir un test que falle por la razón correcta en la carpeta de §12.
3. Implementar lo mínimo: schema en `model/`, request + key + hook en el archivo
   del recurso en `api/`, vista en `ui/`, export en `index.ts`, ruta delgada.
4. Verde; refactorizar sin abstracciones especulativas y confirmar límites,
   caché única, i18n, temas y accesibilidad.
5. Repetir por interacción; cerrar con `just frontend verify` y los recorridos
   de navegador/BFF que exija la guía de verificación.

## 14. Deuda conocida

Cada punto requiere su propio cambio con test de regresión; este documento no
lo corrige.

- **Loader server en la fachada principal.** `@/features/auth` reexporta
  `loadInvitation`, que lee `serverConfig`; debería vivir en
  `@/features/auth/server`.
- **Rewrite duplicado.** `/api/v1/*` se reescribe en `src/proxy.ts` y en
  `next.config.ts`; debe quedar un solo dueño.
- **Configuración sin validación.** `server.ts` no valida variables ni falla
  rápido, y prefiere `NEXT_PUBLIC_BACKEND_API_HOST` sobre `BACKEND_API_HOST`.
- **Rotación deduplicada por módulo.** `rotateBackendSession` comparte
  rotaciones solo dentro de su instancia de módulo; entre el Proxy y
  `/api/auth/refresh`, o entre instancias de Next, la continuidad depende de la
  ventana de gracia del backend. Sin ella, dos rotaciones paralelas del mismo
  refresh token se revocan entre sí.
- **Textos sin traducir.** Quedan literales visibles en el wizard de
  onboarding de `features/superuser` (`step-info`, `step-members`,
  `step-verify`) y en primitives de `shared/ui` (`calendar`, `page-content`,
  `sidebar`, `date-range-picker`, `editable-inline-name`, `spinner`,
  `breadcrumb`).
- **Reglas a11y en `warn`.** `useSemanticElements` (`field`, `input-group`,
  `page-content`), `noStaticElementInteractions` (`member-item`,
  `date-range-filter`, `date-range-picker`), `useKeyWithClickEvents`
  (`input-group`) y `useValidAnchor` (enlace `href="#"` en `settings-view`).
- **IP de cliente falsificable sin edge de confianza.** Si
  `TRUSTED_CLIENT_IP_HEADER` no está configurado, `X-Client-IP` sale del último
  salto de `X-Forwarded-For`. Next conserva ese header si el cliente ya lo
  envía, así que un cliente que llega a Next sin un proxy delante puede elegir
  su IP y esquivar los límites por cliente del backend. En producción detrás de
  un edge (Cloudflare, nginx) hay que configurar el header que ese edge fija.
