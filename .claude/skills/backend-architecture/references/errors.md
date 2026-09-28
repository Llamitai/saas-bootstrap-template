# Domain errors

Paths are relative to `backend/`. Domain and application raise typed `DomainError`
subclasses; global handlers translate them to HTTP. Endpoints and use cases do not
catch business errors.

| Piece | Location |
| --- | --- |
| `DomainError(code, message, status_code=400, context=None)` | `src/common/domain/exceptions/_base.py` (re-exported from `src.common.domain.exceptions`) |
| Shared subclasses by area | `src/common/domain/exceptions/{auth,common,permission,roles,tenants,uploads,users}.py` |
| Module-private subclasses | `src/<module>/domain/exceptions.py` (`auth`, `users`, `admin`) |
| Envelope models `ErrorFeedback`, `ErrorItem`, `ValidationFeedback` | `src/common/domain/exceptions/common.py` |
| Handlers | `src/common/infrastructure/error_handlers.py`, `src/common/infrastructure/handlers/rate_limit_handler.py` |
| Registration | `config/main.py` |

## Defining an error

- One subclass per business condition and status, named `<Subject><Condition>Error`,
  with a `(self, context=None)` constructor (see `roles.py`).
- `code` is `"<area>.<Name>"` (`"tenants.TenantRoleNotFound"`), a stable string the
  frontend uses for i18n; `status_code` uses `src.common.domain.constants.status`.
- Put an error in `common` when another module raises or handles it; otherwise
  keep it in the owning module.

## HTTP translation

- `DomainError`, `HTTPException` and `RequestValidationError` produce
  `{errors: [{code, message}], validation}`; `ApiJSONResponse` adds `timestamp`
  and camelCases keys. Validation errors return 422 with `common.ValidationError`
  and per-field entries keyed by path.
- `context` is for observability. The domain handler exposes only the whitelisted
  keys `missing`, `openFields` and `holder` on the error item; adding a key to that
  list changes the public contract.
- Rate-limit errors use their own handler and shape
  (`{error, message, limit, window, retry_after}` plus rate-limit headers).
- The handler is registered for `fastapi.HTTPException`. Starlette's routing
  404/405 raise `starlette.exceptions.HTTPException` (the parent class), so an
  unknown path or wrong method returns Starlette's `{"detail": ...}`, not the
  `{errors}` envelope. Clients must not assume every 4xx is enveloped.

## Known debt

- `TenantRoleNotFoundError` exists twice with the same code: `exceptions/roles.py`
  (404) and `exceptions/tenants.py` (409, imported by
  `src/tenants/application/use_cases/role/assigner.py` and
  `src/users/application/use_cases/tenant_user/mixins.py`). Import the `roles.py`
  class in new code.
- Legacy duplicates of the envelope models in
  `src/common/domain/entities/common/error_feedback.py` use Pydantic v1
  `class Config`; the models in `exceptions/common.py` are the source.

## Common mistakes

- Raising `HTTPException` from domain/application code.
- Catching `DomainError` in an endpoint or use case.
- Raw integer statuses, or one class reused for different statuses.
- Putting sensitive data in a `context` key that the handler exposes.
