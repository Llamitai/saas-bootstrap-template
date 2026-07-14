# Tenant Users API

Base URL: `/api/v1/tenants`

Todos los endpoints requieren autenticación y una sesión de tenant activa.
El `tenant_id` se infiere del `TenantUser` actual (resuelto por la dependencia
`get_required_tenant_user`); el header `X-Tenant` selecciona el tenant.

Las requests y responses usan **camelCase**: `CamelCaseRequest` convierte el
body entrante a snake_case y `CamelCaseJSONResponse` serializa la respuesta a
camelCase. Las respuestas se envuelven en `{ "data": ..., "timestamp": ... }`
vía `ApiJSONResponse` (`backend/src/common/infrastructure/responses/api_json.py`).

**Fuente de verdad:**
- Router: `backend/src/tenants/presentation/router.py`
- Endpoints: `backend/src/tenants/presentation/endpoints/tenant_users.py`,
  `tenant_user.py`, `tenant_user_stats.py`, `invitations_create.py`,
  `member_password_reset.py`, `member_photo.py`
- Presenter: `backend/src/tenants/presentation/presenters/tenant_user.py`
  (`TenantUserPresenter`)
- Permisos: `backend/src/common/domain/permissions/namespaces/tenant_user.py`
  (`TenantUserPermission`)

> No existe un endpoint de "crear tenant user" directo. Los miembros se
> incorporan por **invitación** (`POST /v1/tenants/invitations`) y se activan
> al aceptarla. Ver la sección [Invitaciones](#invitaciones).

---

## Permisos

El namespace es `tenant_users` (plural). Strings exactos de
`TenantUserPermission`:

| Constante | String              |
|-----------|---------------------|
| `view`    | `tenant_users.view`   |
| `create`  | `tenant_users.create` |
| `update`  | `tenant_users.update` |
| `delete`  | `tenant_users.delete` |

La verificación se hace con `check_tenant_permission(current_tenant_user,
permissions=[...])`. Si `PERMISSIONS_ENABLED` es falso, todo pasa.

---

## List Tenant Users

```
GET /api/v1/tenants/users
```

Lista paginada de tenant users del tenant actual (excluye al usuario actual,
`exclude_ids`). Handler: `get_tenant_users`.

**Permisos:** `tenant_users.view`

### Query Parameters

Provienen de `TenantUserFilters` (extiende `ListFilters`):

| Parameter | Type    | Required | Description                                                  |
|-----------|---------|----------|--------------------------------------------------------------|
| cursor    | string  | No       | Cursor de paginación (base64) para la página siguiente       |
| limit     | integer | No       | Tamaño de página (default: `settings.PAGINATION_PAGE_SIZE`)  |
| search    | string  | No       | Búsqueda por nombre o email                                  |
| statuses  | string  | No       | Estados separados por coma: `ACTIVE`, `PENDING`, `INACTIVE`  |

### Response `200 OK`

```json
{
  "data": [
    {
      "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "firstName": "John",
      "lastName": "Doe",
      "phoneNumber": {
        "uuid": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
        "dialCode": 1,
        "phoneNumber": "5551234567",
        "isVerified": true
      },
      "emailAddress": {
        "uuid": "b1c2d3e4-f5a6-7890-abcd-ef1234567890",
        "email": "john@example.com",
        "isVerified": true
      },
      "isOwner": false,
      "isSupport": false,
      "photoUrl": "https://storage.example.com/tenants/acme/members/a1b2.../avatar.png",
      "status": "ACTIVE",
      "tenantRole": {
        "uuid": "c1d2e3f4-a5b6-7890-abcd-ef1234567890",
        "name": "Admin",
        "status": "ACTIVE"
      },
      "createdAt": "2026-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "nextCursor": "eyJpZCI6IDEwfQ==",
    "limit": 20
  },
  "timestamp": "2026-04-04T12:00:00Z"
}
```

La forma de `pagination` proviene de `Pagination` (`pagination.py`): solo
`nextCursor` y `limit`. No existe `hasMore` — si `nextCursor` es `null`, no hay
más páginas.

---

## Get Tenant User

```
GET /api/v1/tenants/users/{tenant_user_id}
```

Detalle de un tenant user. Handler: `get_tenant_user`.

**Permisos:** `tenant_users.view`

### Path Parameters

| Parameter      | Type | Required | Description            |
|----------------|------|----------|------------------------|
| tenant_user_id | UUID | Yes      | UUID del tenant user   |

### Response `200 OK`

```json
{
  "data": {
    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "firstName": "John",
    "lastName": "Doe",
    "phoneNumber": {
      "uuid": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
      "dialCode": 1,
      "phoneNumber": "5551234567",
      "isVerified": true
    },
    "emailAddress": {
      "uuid": "b1c2d3e4-f5a6-7890-abcd-ef1234567890",
      "email": "john@example.com",
      "isVerified": true
    },
    "isOwner": false,
    "isSupport": false,
    "photoUrl": null,
    "status": "ACTIVE",
    "tenantRole": {
      "uuid": "c1d2e3f4-a5b6-7890-abcd-ef1234567890",
      "name": "Admin",
      "status": "ACTIVE"
    },
    "createdAt": "2026-01-15T10:30:00Z"
  },
  "timestamp": "2026-04-04T12:00:00Z"
}
```

### Campos de la respuesta (`TenantUserPresenter`)

| Campo        | Tipo            | Notas                                                          |
|--------------|-----------------|----------------------------------------------------------------|
| uuid         | string          | UUID del `TenantUser`                                          |
| firstName    | string \| null  | `display_first_name`                                          |
| lastName     | string \| null  | `display_last_name`                                          |
| phoneNumber  | object \| null  | `PhoneNumberPresenter`; `null` si no hay teléfono             |
| emailAddress | object \| null  | `EmailAddressPresenter`; `null` si no hay email               |
| isOwner      | boolean         | Owner del tenant                                              |
| isSupport    | boolean         | Flag de soporte interno                                      |
| photoUrl     | string \| null  | URL pública de la foto de perfil (`TenantUser.photo`)        |
| status       | string          | `TenantUserStatus`                                           |
| tenantRole   | object \| null  | `SimpleTenantRolePresenter`; `null` si no tiene rol asignado |
| createdAt    | datetime        |                                                                |

---

## Update Tenant User

```
PUT /api/v1/tenants/users/{tenant_user_id}
```

Actualiza el tenant user. Solo se aplican los campos provistos (partial update:
`model_dump(exclude_none=True)`). Handler: `update_tenant_user`,
body `UpdateTenantUserRequest`.

**Permisos:** `tenant_users.update`

### Request Body

```json
{
  "firstName": "Jonathan",
  "lastName": "Doe",
  "status": "INACTIVE",
  "tenantRoleId": "c1d2e3f4-a5b6-7890-abcd-ef1234567890",
  "isOwner": false,
  "isSupport": false,
  "email": "jonathan@example.com",
  "phoneNumber": {
    "dialCode": 1,
    "phoneNumber": "5551112222",
    "isoCode": "US"
  }
}
```

| Field        | Type    | Required | Description                                                       |
|--------------|---------|----------|-------------------------------------------------------------------|
| firstName    | string  | No       | Nombre (max 150 chars)                                            |
| lastName     | string  | No       | Apellido (max 150 chars)                                         |
| status       | string  | No       | `ACTIVE`, `PENDING` o `INACTIVE` (`TenantUserStatus`)            |
| tenantRoleId | UUID    | No       | UUID del rol a asignar                                          |
| isOwner      | boolean | No       | Si el usuario es owner del tenant                              |
| isSupport    | boolean | No       | **Solo superuser.** Flag de soporte interno; se descarta silenciosamente si quien envía no es superuser |
| email        | string  | No       | Nuevo email                                                    |
| phoneNumber  | object  | No       | Objeto `RawPhoneNumber` (`dialCode`, `phoneNumber`, `isoCode`, `prefix`) |

> `isSupport` se filtra en el endpoint: si `current_tenant_user.user.is_superuser`
> es falso, el campo se elimina del payload antes de aplicar el update.

### Response `200 OK`

Misma estructura que [Get Tenant User](#get-tenant-user).

---

## Delete Tenant User

```
DELETE /api/v1/tenants/users/{tenant_user_id}
```

Desvincula al usuario del tenant. Handler: `delete_tenant_user`.

**Permisos:** `tenant_users.delete`

### Response `200 OK`

```json
{
  "data": { "status": "SUCCESS" },
  "timestamp": "2026-04-04T12:00:00Z"
}
```

(`TaskResult.success()`.)

---

## Send Password Reset (a un miembro)

```
POST /api/v1/tenants/users/{tenant_user_id}/send-password-reset
```

Envía por email un link de reseteo de contraseña a un miembro del tenant.
Handler: `send_member_password_reset` → `SendPasswordResetToMember`. A
diferencia del endpoint público `/v1/auth/reset-password` (anti-enumeración),
este devuelve 200/404 explícito porque lo dispara un admin desde la pantalla de
miembros.

**Permisos:** `tenant_users.update`

### Response `200 OK`

```json
{
  "data": { "email": "jonathan@example.com" },
  "timestamp": "2026-04-04T12:00:00Z"
}
```

---

## Upload Member Photo

```
POST /api/v1/tenants/users/{tenant_user_id}/photo
```

Sube una foto de perfil para un miembro. Body **multipart/form-data** con el
campo `photo` (no JSON). El endpoint sube el archivo al storage configurado,
construye la URL pública y la persiste en `TenantUser.photo` vía
`TenantUserUpdater`. Handler: `update_member_photo`.

**Permisos:** `tenant_users.update`

### Request

`multipart/form-data`:

| Field | Type | Required | Description           |
|-------|------|----------|-----------------------|
| photo | file | Yes      | Archivo de imagen     |

La ruta de almacenamiento es
`tenants/{tenant_slug}/members/{tenant_user_id}/{file_name}`.

### Response `200 OK`

Misma estructura que [Get Tenant User](#get-tenant-user), con `photoUrl` ya
actualizado.

---

## Get Tenant User Stats

```
GET /api/v1/tenants/users/stats
```

Conteos agregados de tenant users por estado (excluye al usuario actual).
Handler: `get_tenant_user_stats` → `TenantUserStatsGetter`; entidad
`TenantUserStats`.

**Permisos:** `tenant_users.view`

### Response `200 OK`

```json
{
  "data": {
    "total": 25,
    "active": 20,
    "pending": 3,
    "inactive": 2
  },
  "timestamp": "2026-04-04T12:00:00Z"
}
```

---

## Invitaciones

El alta de miembros ocurre por invitación, no por creación directa. Endpoints en
`backend/src/tenants/presentation/endpoints/invitations_create.py` (admin,
tenant-scoped) e `invitations.py` (público, token-gated).

### Crear invitaciones

```
POST /api/v1/tenants/invitations
```

Invita uno o más miembros al tenant actual. Reusa `InviteTenantMembers`.
Handler: `create_tenant_invitations`, body `InviteMembersRequest`.

**Permisos:** `tenant_users.create`

#### Request Body

```json
{
  "members": [
    { "email": "jane@example.com", "roleSlug": "member" },
    { "email": "carlos@example.com", "roleSlug": "admin" }
  ]
}
```

| Field             | Type   | Required | Description                                       |
|-------------------|--------|----------|---------------------------------------------------|
| members           | array  | Yes      | Lista no vacía de invitaciones                    |
| members[].email   | string | Yes      | Email válido (`EmailStr`)                         |
| members[].roleSlug| string | No       | Slug del rol a asignar (default `"member"`)       |

#### Response `201 Created`

```json
{
  "data": {
    "invitations": [
      {
        "uuid": "11111111-2222-3333-4444-555555555555",
        "tenantId": "aaaa1111-bbbb-2222-cccc-333344445555",
        "email": "jane@example.com",
        "tenantRoleId": "c1d2e3f4-a5b6-7890-abcd-ef1234567890",
        "token": "v0p3n-...-token",
        "status": "PENDING",
        "expiresAt": "2026-04-11T12:00:00Z",
        "acceptedAt": null,
        "createdById": "99999999-8888-7777-6666-555555555555",
        "requiresPassword": true,
        "createdAt": "2026-04-04T12:00:00Z"
      }
    ],
    "skippedExistingMembers": [
      { "email": "carlos@example.com" }
    ]
  },
  "timestamp": "2026-04-04T12:00:00Z"
}
```

Campos de invitación según `TenantUserInvitationPresenter`. Los emails que ya
son miembros activos del tenant se devuelven en `skippedExistingMembers` y no se
re-invitan.

### Listar invitaciones pendientes

```
GET /api/v1/tenants/invitations
```

Handler: `list_tenant_invitations` → `ListPendingInvitations`. Devuelve un array
de invitaciones (mismo shape de invitación de arriba) bajo `data`.

**Permisos:** `tenant_users.view`

### Cancelar invitación

```
DELETE /api/v1/tenants/invitations/{invitation_id}
```

Marca la invitación como `EXPIRED`. Handler: `cancel_tenant_invitation` →
`CancelInvitation`. Devuelve la invitación actualizada bajo `data`.

**Permisos:** `tenant_users.delete`

### Endpoints públicos (token-gated, sin auth)

Router aparte `invitations_router` (prefix `/invitations`, sin auth de tenant):

```
GET  /api/v1/invitations/{token}          # lookup público de la invitación
POST /api/v1/invitations/{token}/accept   # aceptar (single-use): set password + sesión
```

`GET /v1/invitations/{token}` (handler `get_invitation_by_token` →
`GetInvitation`, presenter `InvitationViewPresenter`) devuelve una vista ligera
para el landing público:

```json
{
  "data": {
    "email": "jane@example.com",
    "tenantName": "Acme",
    "roleName": "member",
    "expiresAt": "2026-04-11T12:00:00Z",
    "requiresPassword": true
  },
  "timestamp": "2026-04-04T12:00:00Z"
}
```

Errores de dominio (`backend/src/common/domain/exceptions/tenants.py`):
`tenants.InvitationNotFound` (404), `tenants.InvitationAlreadyAccepted` (410),
`tenants.InvitationExpired` (410), `tenants.InvitationPasswordRequired` (400).

---

## Enums

### TenantUserStatus

`backend/src/common/domain/enums/users.py`.

| Value      | Descripción                  |
|------------|------------------------------|
| `ACTIVE`   | Activo en el tenant          |
| `PENDING`  | Pendiente de activación      |
| `INACTIVE` | Desactivado                  |

---

## Notas

- **Formato de request:** los bodies aceptan camelCase; el servidor los convierte
  a snake_case vía `CamelCaseRequest`.
- **Formato de response:** las keys se serializan a camelCase vía
  `CamelCaseJSONResponse`; `ApiJSONResponse` envuelve en
  `{ data, timestamp }` y, para `Page`, añade `pagination` (`{ nextCursor, limit }`).
- **Paginación:** cursor-based. Usar `nextCursor` para la página siguiente; no
  hay `hasMore`.
- **Phone/email como null:** si el usuario no tiene teléfono o email, esos campos
  devuelven `null`.
- **Tenant role como null:** si no hay rol asignado, `tenantRole` devuelve `null`.
- **`isSupport`:** flag de soporte interno; solo lo puede modificar un
  superuser (ver Update Tenant User).
