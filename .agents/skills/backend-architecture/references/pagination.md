# Cursor pagination

Paths are relative to `backend/`. Paginated lists use a keyset cursor over
`(created_at, uuid)`. Preserve any other list contract an endpoint already has.

| Piece | Location |
| --- | --- |
| `Page[T]`, `Pagination` | `src/common/domain/entities/common/pagination.py` |
| `ListFilters` (`cursor`, `limit`), `parse_enum_values` | `src/common/domain/entities/common/collection.py` |
| Filter subclass | `src/common/domain/filters/tenants/tenant_user.py` |
| `encode_cursor`/`decode_cursor` (Fernet-encrypted) | `src/common/application/helpers/pagination.py` |
| Repository exemplar | `SQLTenantRoleRepository.filter_paginated` in `src/tenants/infrastructure/repositories/sql_tenant_role.py` |
| Endpoint exemplar | `get_tenant_roles` in `src/tenants/presentation/endpoints/tenant_roles.py` |

## Contract

- Filters subclass `ListFilters` and are injected with `Depends()`. `limit`
  defaults to `settings.PAGINATION_PAGE_SIZE`. Multi-value filters arrive as
  comma-separated strings decoded with `parse_enum_values`.
- `ListFilters.limit` has no upper bound, and the repository applies it to both
  `filter` and `filter_paginated`. A new filter subclass bounds it
  (`limit: int = Field(default=settings.PAGINATION_PAGE_SIZE, ge=1, le=<max>)`).
- Query parameters are not snake-cased by the middleware; multi-word filter
  fields need a camelCase `alias` (`TenantUserFilters.tenant_ids`).
- The repository orders by `created_at DESC, uuid DESC`, fetches `limit + 1`, pops
  the extra row and encodes the next cursor from that popped row. The next request
  applies it inclusively: `tuple_(created_at, uuid) <= (timestamp, uuid)`, so the
  popped row starts the next page. Keep encoding and comparison consistent.
- `filter` and `filter_paginated` share one query builder; the non-paginated form
  feeds internal consumers.
- An invalid cursor raises `InvalidPaginationCursorError` (400).
- The endpoint returns `page.apply_presenter(Presenter)` (a new `Page`) through
  `ApiJSONResponse`, which emits `{data, pagination: {nextCursor, limit}, timestamp}`.
  "More pages" means `nextCursor` is not null.
- Tenant scope is passed to the repository explicitly from the validated tenant
  user, never from a filter value supplied by the client.

## Common mistakes

- Ordering by `created_at` alone (unstable on ties).
- Returning the over-fetched row.
- Ignoring the return value of `apply_presenter`.
- Plain base64 cursors or offsets for new paginated endpoints.
