# Authentication and tenant scope

Paths are relative to `backend/`. Two independent inputs identify a request: the
user from `Authorization: Bearer` and the active tenant from the `X-Tenant` slug
header. Tenant-scoped operations need both, plus membership.

| Piece | Location |
| --- | --- |
| `TokenService` port (`generate_token`, `refresh_token`, `get_claims`, `expire_refresh_token`, `revoke_all_sessions`, `create_one_shot_token`, `consume_one_shot_token`) | `src/common/domain/services/token_service.py` |
| JWT service, builder, Redis store | `src/common/infrastructure/services/jwt_token_service.py`, `jwt_token_builder.py`, `redis_token_store.py` |
| User dependencies | `src/common/infrastructure/dependencies/session.py` |
| Tenant dependencies, `required_tenant_for` | `src/common/infrastructure/dependencies/tenant.py` |
| Permission checks and catalog | `src/common/domain/permissions/checker.py`, `catalog.py`, `namespaces/` |
| Admin API key | `src/common/infrastructure/dependencies/api_keys.py` (`X-API-Key`) |
| Session endpoints and BFF | `src/auth/presentation/`, `../frontend/src/app/api/auth` |

## Identity

- Access tokens are verified per request through `get_claims(scope=ACCESS)`;
  `get_authenticated_user` then loads the user with `GetUserByIdQuery`.
- Refresh tokens live in a per-session allowlist (fail-closed; no blacklist). Each
  login opens a session whose `sid` claim both tokens carry; Valkey keeps its
  current refresh `jti` in `{ns}_RT:{sub}:{sid}` and the subject's sessions in the
  sorted set `{ns}_SESS:{sub}` (scored by last use), both with the refresh TTL. A
  refresh is accepted only when its `jti` is the session's current one and the
  session is indexed; rotation is a compare-and-set Lua script, so two concurrent
  rotations cannot both win. A token without `sid`, a reused rotated token or a
  lost key gets 401, never acceptance, so Valkey may evict (`allkeys-lru`).
  Rotated tokens keep the original `sid` and namespace. JOSE uses `joserfc`.
- `JWT_MAX_SESSIONS_PER_USER` (default 1, >= 1): a login beyond it closes the least
  recently used session. Logout closes only its session; a password change
  (`PUT /v1/me/password`), an admin-set password or a reset confirm calls `revoke_all_sessions`, closing
  every session of the user, the caller's included. Access tokens stay stateless
  (no Valkey read) and expire on their own after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`.
- Rotation is idempotent for `JWT_REFRESH_GRACE_SECONDS` (default 30): callers
  presenting the same just-rotated token get the same new pair only while the
  session's current `jti` is still that pair's; a closed, evicted or re-rotated
  session never gets it back.
- Password-reset tokens are one-shot: `create_one_shot_token` allows the `jti` in
  `{ns}_OST:{jti}` and `consume_one_shot_token` deletes it atomically, so a token
  is accepted once and a lost key rejects it.
- Google ID tokens are accepted only with a Google `iss`, the configured `aud` and
  a valid `exp`; the JWKS is cached for an hour.
- Tokens carry no tenant id. `User.current_tenant_id` is the last-selected tenant,
  a UI hint that never authorizes anything.
- Public routes (login, refresh, registration, password reset, invitation lookup,
  `GET /api/py/health` and `/api/py/health/ready`) omit auth dependencies instead
  of branching on an optional token. Unauthenticated routes that accept
  credentials or create accounts carry a rate limit, keyed by `client_ip()`
  (`X-Client-IP` is trusted only with a valid `X-Api-Key`, i.e. from the BFF);
  `/auth/refresh` is keyed by the token subject. Registration still reveals
  whether an email exists; closing that needs email verification and an ADR.

## Tenant scope

- `get_required_tenant` resolves the `X-Tenant` slug; `get_required_tenant_user`
  confirms the authenticated user's membership and attaches the tenant.
- Endpoints take the scope from `required_tenant_for(current_tenant_user)`. Never
  read a tenant id from the body, query or filters.
- A path id of a tenant-owned entity must be checked against that scope, usually
  by the use case's load mixin, raising `NotFound` for other tenants.
- Repositories receive `tenant_id` explicitly and filter on it; there is no
  implicit tenant filter.
- Tests for tenant-scoped behavior cover an allowed scope and a wrong scope.

## Permissions

- Tenant endpoints call `check_tenant_permission(current_tenant_user, permissions=[...])`
  with a permission from `namespaces/`; it raises `InsufficientPermissionsError` (403).
- `check_tenant_permission` returns early while `PERMISSIONS_ENABLED` in
  `src/common/constants.py` is `False`, its current value. Keep writing the checks,
  but do not treat them as enforced authorization until that flag is enabled.
- Frontend permission gates only complement server authorization.

## Common mistakes

- Trusting `tenant_id`/`tenantIds` from the client, or using `current_tenant_id` for scope.
- Using `get_authenticated_user` alone on a tenant route: it checks identity, not membership.
- A new repository method without its `tenant_id` filter.
- Adding token methods outside the `TokenService` port.
