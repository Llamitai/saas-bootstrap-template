---
title: "Roadmap frontend"
description: "Ideas objetivo del frontend que todavía no son contrato."
icon: Milestone
---

Este documento reúne ideas objetivo que **no existen hoy** en el código. No son
reglas vigentes: el contrato actual está en
[la arquitectura frontend](arquitectura-frontend.md). Cada punto se adopta con
su propia change (y un ADR en [adr/](../equipo/adr/index.md) si toca límites de
módulo, contratos, persistencia, seguridad o flujos núcleo) y, al implementarse,
pasa al documento de arquitectura y sale de aquí.

## Multitenancy por segmento y consola administrativa

- Segmento `src/app/[domain]/` con `(public)`/`(protected)` por subdominio o slug
  del tenant, y un `layout.tsx` de tenant que valida la sesión en servidor.
- Consola cross-tenant en `src/app/admin/` con shell y helpers BFF propios que
  reenvían solo `Authorization` y credenciales de infraestructura, sin
  `X-Tenant`.

Hoy el tenant activo viaja en el header `X-Tenant` desde el store de sesión.

## Realtime por SSE

- `src/shared/http/sse.ts` basado en `fetch` (no `EventSource`) para enviar
  `Authorization`, `X-Tenant` y `X-Client`; parser de eventos, heartbeats,
  reconexión con backoff exponencial, cancelación al desmontar y watchdog.
- Realtime como bus de invalidación: un evento invalida query keys y se relee por
  REST; el stream no duplica estado remoto.
- Streaming o SSE a través de un route handler explícito
  (`fetch(url, { duplex: "half" })`) que reutilice los helpers de
  `shared/http/bff.ts`.

## Datos y caché

- Query keys con scope (tenant/usuario) como primer segmento, para no depender
  de navegación completa o `queryClient.clear()` al cambiar de scope.
- Factories con `queryOptions()` en todos los recursos.
- Prefetch en Server Components con `HydrationBoundary`/`dehydrate` para vistas
  que lo justifiquen (requiere ADR: cambia el modelo de sesión en servidor).
- `cacheComponents`/`'use cache'` (requiere ADR).
- Tipos y esquemas zod generados desde OpenAPI (`openapi-typescript`, `orval`);
  DTOs junto a la request, tipos de dominio en `model/`.
- Un `ApiEnvelope`/paginación compartidos en `shared/types` si más de un slice
  consume `{ data, pagination, timestamp }`.

## Configuración y seguridad

- Página de mantenimiento con diseño del producto para el `503` transitorio del
  Proxy (hoy es HTML mínimo traducido que se recarga solo).
- Validar `process.env` con zod en `shared/config/server.ts` y fallar rápido si
  falta una variable requerida.
- `import "server-only"` en `shared/config/server.ts`, `shared/http/server.ts`,
  `shared/http/bff.ts`, `shared/http/session-cookies.ts` y los `*-server.ts`.

## Tooling y tests

- MSW para mocks de `/api` con handlers derivados de los mismos schemas zod,
  reemplazando los dobles `vi.mock("@/shared/http/client")`.
- Subir a `error` las reglas a11y de Biome que hoy quedan en `warn`
  (`useSemanticElements`, `noStaticElementInteractions`,
  `useKeyWithClickEvents`, `useValidAnchor`) cuando sus violaciones se corrijan.
- `ui/` opcional en entidades para piezas presentacionales atadas a la entidad
  (por ejemplo `UserAvatar`, `TenantBadge`).
