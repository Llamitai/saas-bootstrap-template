---
title: "Perfil del proyecto"
description: "Capacidades activas, contratos y fuentes autoritativas del core."
icon: IdCard
---

Starter multi-tenant para productos B2B autenticados. El core comprende auth,
usuarios/perfil, tenants/settings/avatar, miembros/invitaciones, roles/permisos,
assets, onboarding de superusuario, messaging y Directus como consola interna.
Los ejemplos, fixtures y documentación describen este core.

## Fuentes y arranque

Las versiones se leen de [backend/pyproject.toml](../../../../backend/pyproject.toml),
[frontend/package.json](../../../../frontend/package.json) y
[docs/package.json](../../../package.json); sus locks se instalan sin resolver versiones
nuevas. El tooling OpenSpec vive en el [manifest raíz](../../../../package.json), con
lock propio. Los paquetes frontend/docs mantienen sus instalaciones independientes.

Desde la raíz Git: `just backend`, `just frontend`, `just docs` descubren recetas.
`just backend dev` crea `.env` desde el ejemplo y arranca el stack local;
`just frontend dev` y `just docs dev` arrancan cada consumidor. La verificación y
sus servicios se describen en [la guía de verificación](verificacion.md).

## Arquitectura y contratos activos

| Capacidad | Estado y fuente | Evidencia pertinente |
| --- | --- | --- |
| Backend | Activo. [README](../../../../backend/README.md), módulos bajo `backend/src` | pytest, Ruff/ty y contratos import-linter |
| Auth y sesiones | Activo. [auth](../../../../backend/src/auth), [BFF auth](../../../../frontend/src/app/api/auth) | Login/error, refresh deduplicado, cookies HttpOnly/flags, revocación/logout; token de acceso fuera del store persistido |
| Reset de contraseña | Activo. [use cases](../../../../backend/src/auth/application/use_cases/password_reset) | Respuesta sin enumeración, expiración y token de un uso |
| Tenancy/roles/permisos | Tenancy activa. [dependencia tenant](../../../../backend/src/common/infrastructure/dependencies/tenant.py); permisos modelados pero no aplicados: `PERMISSIONS_ENABLED = False` en [constants](../../../../backend/src/common/constants.py) hace que `check_tenant_permission` no bloquee | X-Tenant y membresía en servidor; dos scopes. Los checks de permiso se escriben igual; el acceso denegado por permiso solo es observable al activar el flag. UI complementa servidor |
| Storage | Activo. [puerto](../../../../backend/src/assets/domain/services/storage.py); `build_async_domain` cablea siempre `S3StorageService` (RustFS en local). `DiskStorageService` existe pero no está cableado | S3/RustFS; efectos y rollback pertinentes. Puerto síncrono (boto3) |
| Messaging/jobs | Scaffolding activo. [messaging](../../../../backend/src/messaging), [worker](../../../../backend/config/worker.py) | SMTP y comandos diferidos por RabbitMQ (confirmaciones del broker, ack manual, reintentos acotados y DLQ) cuando el caso los usa; el worker es un servicio Compose propio (`worker`) |
| Directus/admin | Activo como consola interna. [Compose](../../../../backend/docker-compose.yml) | Configuración/arranque y contratos admin afectados |
| Frontend | Activo. [arquitectura](../conceptos/arquitectura-frontend.md) | Fachadas, HTTP/BFF, caché y UI; Vitest y Playwright |
| Realtime/MSW | Objetivos arquitectónicos, no capacidades instaladas del producto | No exigir SSE ni afirmar mocks MSW sin introducir dependencia/setup explícitos |

Los módulos completos `auth`, `tenants`, `users` sirven de ejemplares; el resto
son superficies delgadas y `common` es shared kernel. No crear capas para completar
un árbol. ORM siempre en `backend/src/common/database/models/` y dominio
compartido en `backend/src/common/domain/models/`; el resto de formas de módulo y
ubicaciones está en
[layers.md](../../../../.claude/skills/backend-architecture/references/layers.md).

Los casos de uso son dataclasses con `UseCase.execute()`, una operación por
archivo; repositorios abstractos y adapters SQL con builders. DomainContext y
BusContext preservan DI explícita: repositorios para CRUD local, buses para
protocolos cruzados/async existentes. Cada request abre una sesión
([dependencies](../../../../backend/src/common/infrastructure/dependencies/common.py)),
sin transacción de alcance request: cada escritura de repositorio hace commit o
rollback dentro de
[atomic_transaction](../../../../backend/src/common/infrastructure/helpers/database.py),
así que dos escrituras no son atómicas entre sí.

`DomainError` lleva código/mensaje/status. Routers registran `add_api_route()`;
presenters trabajan con claves internas: [ApiJSONResponse](../../../../backend/src/common/infrastructure/responses/api_json.py)
y la capa camelCase controlan la respuesta, con `RawJson` para datos opacos.
Preservar `{data, timestamp}` y `{errors, validation?}` según el endpoint, además
de su paginación real. No añadir otro casing ni asumir una paginación universal.

Navegador → `/api` mediante [client.ts](../../../../frontend/src/shared/http/client.ts).
Código de servidor puede usar [server.ts](../../../../frontend/src/shared/http/server.ts).
[BFF](../../../../frontend/src/shared/http/bff.ts) preserva headers/errores; credenciales de
infraestructura permanecen en servidor. QueryClient es estable; Query posee
estado remoto, Zustand estado cliente; un cambio de scope destruye la caché
(recarga completa al cambiar de tenant, `queryClient.clear()` al iniciar o cerrar
sesión). Solo `proxy.ts` y los route handlers rotan tokens o escriben cookies.

## Diseño, operación y adopción

[PRODUCT](../../../../PRODUCT.md) y [DESIGN](../../../../DESIGN.md) gobiernan el registro de
producto y la identidad visual; los tokens vivos están en globals.css. Reutilizar
componentes, formularios, i18n/temas y accesibilidad del proyecto. No duplicar aquí
valores/versiones que derivan de esas fuentes.

Logging estructurado, correlación, rate limiting y headers viven en
[logging](../../../../backend/src/common/application/logging/config.py) y
[middlewares](../../../../backend/src/common/infrastructure/middlewares).
El despliegue distribuido usa imágenes identificadas por commit; hosting,
registro y secretos son decisiones del adoptante. El frontend conserva standalone
y usuario no root; no se atribuye esa propiedad al backend sin comprobarla.

Una adopción registra cada capacidad como activa, ausente con evidencia o pendiente.
Omitir una fila no autoriza eliminar auth/scoping. El render de otra identidad
no elimina automáticamente el core instalado. Instrucciones/código/commits en inglés;
`docs/content` e incluidos READMEs de módulos, en español.
