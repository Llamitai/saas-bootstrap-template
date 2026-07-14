# API Reference (REST)

Catálogo reducido de la superficie core del backend.

## Common

| Method | Path | Function |
|---|---|---|
| GET | `/` | `home` |
| GET | `/sentry-debug` | `sentry_debug` local |

## Auth — `/v1/auth`

| Method | Path | Function |
|---|---|---|
| POST | `/v1/auth/login` | `login` |
| POST | `/v1/auth/google-login` | `google_login` |
| POST | `/v1/auth/reset-password` | `reset_password` |
| POST | `/v1/auth/reset-password/confirm` | `reset_password_confirm` |
| POST | `/v1/auth/refresh` | `refresh` |
| POST | `/v1/auth/logout` | `logout` |
| GET | `/v1/auth/session` | `session` |

## Users — `/v1/users`

| Method | Path | Function |
|---|---|---|
| POST | `/v1/users` | `register_user` |

## Profile / Me — `/v1/me`

| Method | Path | Function |
|---|---|---|
| GET | `/v1/me/profile` | `get_profile` |
| PUT | `/v1/me/profile` | `update_profile` |
| PUT | `/v1/me/password` | `update_password` |
| GET | `/v1/me/tenants` | `get_user_tenants` |
| PUT | `/v1/me/tenants/{tenant_id}` | `update_me_tenant` |

## Tenants — `/v1/tenants`

| Method | Path | Function |
|---|---|---|
| POST | `/v1/tenants` | `register_tenant` |
| POST | `/v1/tenants/onboard` | `onboard_tenant` |
| PUT | `/v1/tenants/{tenant_id}` | `update_tenant` |
| DELETE | `/v1/tenants/{tenant_id}` | `soft_delete_tenant` |
| GET | `/v1/tenants/{tenant_id}/settings` | `get_tenant_settings` |
| PATCH | `/v1/tenants/{tenant_id}/settings` | `update_tenant_settings` |
| POST | `/v1/tenants/{tenant_id}/settings/avatar` | `update_tenant_avatar` |
| POST | `/v1/tenants/permissions/missing` | `get_missing_permissions` |

## Tenant members

| Method | Path | Function |
|---|---|---|
| GET | `/v1/tenants/users/stats` | `get_tenant_user_stats` |
| GET | `/v1/tenants/users` | `get_tenant_users` |
| GET | `/v1/tenants/users/{tenant_user_id}` | `get_tenant_user` |
| PUT | `/v1/tenants/users/{tenant_user_id}` | `update_tenant_user` |
| DELETE | `/v1/tenants/users/{tenant_user_id}` | `delete_tenant_user` |
| POST | `/v1/tenants/users/{tenant_user_id}/send-password-reset` | `send_member_password_reset` |
| POST | `/v1/tenants/users/{tenant_user_id}/photo` | `update_member_photo` |

## Invitations

| Method | Path | Function |
|---|---|---|
| POST | `/v1/tenants/invitations` | `create_tenant_invitations` |
| GET | `/v1/tenants/invitations` | `list_tenant_invitations` |
| DELETE | `/v1/tenants/invitations/{invitation_id}` | `cancel_tenant_invitation` |
| GET | `/v1/invitations/{token}` | `get_invitation_by_token` |
| POST | `/v1/invitations/{token}/accept` | `accept_invitation` |

## Roles

| Method | Path | Function |
|---|---|---|
| GET | `/v1/tenants/roles` | `get_tenant_roles` |
| POST | `/v1/tenants/roles` | `create_tenant_role` |
| POST | `/v1/tenants/roles/bootstrap` | `bootstrap_tenant_roles` |
| GET | `/v1/tenants/roles/{role_id}` | `get_tenant_role` |
| PUT | `/v1/tenants/roles/{role_id}` | `update_tenant_role` |
| DELETE | `/v1/tenants/roles/{role_id}` | `delete_tenant_role` |

## Admin

| Method | Path | Function |
|---|---|---|
| POST | `/v1/admin/users/set-password` | `set_user_password` |
