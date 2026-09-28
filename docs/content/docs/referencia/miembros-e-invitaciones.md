---
title: "Miembros e invitaciones"
description: "Reglas de negocio de miembros e invitaciones que el esquema OpenAPI no expresa."
icon: UserPlus
---

Las rutas, parámetros y cuerpos exactos están en la [referencia de la API](index.mdx)
(tags `tenants` e `invitations`). Esta página reúne lo que el esquema no dice:
permisos, efectos y casos especiales.

**Fuente de verdad:**

- Router: `backend/src/tenants/presentation/router.py`
- Endpoints: `backend/src/tenants/presentation/endpoints/` (`tenant_users.py`,
  `tenant_user.py`, `tenant_user_stats.py`, `invitations_create.py`,
  `invitations.py`, `member_password_reset.py`, `member_photo.py`)
- Presenter: `TenantUserPresenter` en `backend/src/tenants/presentation/presenters/tenant_user.py`
- Permisos: `TenantUserPermission` en `backend/src/common/domain/permissions/namespaces/tenant_user.py`

## Contexto de tenant

Todos los endpoints de miembros requieren autenticación y un tenant activo. El
tenant se selecciona con la cabecera `X-Tenant` y se resuelve a partir del
`TenantUser` actual (dependencia `get_required_tenant_user`); nunca se pasa en la
ruta.

## Permisos

Namespace `tenant_users` (plural). Los chequeos usan `check_tenant_permission`;
mientras `PERMISSIONS_ENABLED` sea falso, todos pasan.

| Operación | Permiso |
| --- | --- |
| Listar miembros, ver uno, estadísticas, listar invitaciones | `tenant_users.view` |
| Crear invitaciones | `tenant_users.create` |
| Actualizar miembro, foto, enviar reseteo de contraseña | `tenant_users.update` |
| Desvincular miembro, cancelar invitación | `tenant_users.delete` |

## Miembros

- **No hay alta directa.** Los miembros entran por invitación y se activan al
  aceptarla.
- **El listado y las estadísticas excluyen al usuario actual.** El filtro
  `statuses` acepta valores separados por coma (`ACTIVE,PENDING`) y `search`
  busca por nombre o email.
- **Actualización parcial.** Solo se aplican los campos enviados. `isOwner` e
  `isSupport` solo los puede cambiar un superusuario: para cualquier otro, el
  endpoint los descarta sin error.
- **Borrado.** `DELETE` desvincula al usuario del tenant; no borra el usuario.
- **Reseteo de contraseña de un miembro.** A diferencia de
  `POST /v1/auth/reset-password`, que no revela si el email existe, este endpoint
  responde 404 explícito porque lo dispara un administrador.
- **Foto.** `multipart/form-data` con el campo `photo`; se guarda en
  `tenants/{tenant_slug}/members/{tenant_user_id}/{file_name}` y la respuesta
  trae `photoUrl` actualizado.
- Si el usuario no tiene teléfono o email, esos campos son `null`.

## Invitaciones

- **Crear.** Acepta varias invitaciones a la vez; `roleSlug` es opcional
  (`member` por defecto). Los emails que ya son miembros activos no se
  reinvitan y vuelven en `skippedExistingMembers`.
- **Listar** devuelve solo las pendientes.
- **Cancelar** marca la invitación como `EXPIRED`.
- **Endpoints públicos** (router `invitations_router`, sin sesión de tenant):
  `GET /v1/invitations/{token}` devuelve una vista ligera para la página de
  aceptación y `POST /v1/invitations/{token}/accept` acepta la invitación, fija
  la contraseña si hace falta y abre sesión. El token es de un solo uso.

Errores de dominio (`backend/src/common/domain/exceptions/tenants.py`):

| Código | HTTP |
| --- | --- |
| `tenants.InvitationNotFound` | 404 |
| `tenants.InvitationAlreadyAccepted` | 410 |
| `tenants.InvitationExpired` | 410 |
| `tenants.InvitationPasswordRequired` | 400 |

## Formato

- Cuerpos en camelCase: el middleware de casing y los modelos `CamelCaseRequest`
  convierten las claves a snake_case antes de validar.
- Respuestas en camelCase envueltas en `{ data, timestamp }`. Los listados
  paginados añaden `pagination: { nextCursor, limit }`; la paginación es por
  cursor y no hay `hasMore`.
