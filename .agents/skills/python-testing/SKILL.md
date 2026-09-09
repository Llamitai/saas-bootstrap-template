---
name: python-testing
description: >
  Apply backend pytest conventions when writing or refining Python tests: expects assertions,
  async fixtures, autospecced repository ports and layer-specific examples. Use verify-change
  to choose checks, diagnose failures or assess coverage; TypeScript tests use their own guidance.
---

# Python Testing — SaaS Bootstrap Backend

Use this reference for test syntax, fixtures and placement after the behavior to
verify is identified. [verify-change](../verify-change/SKILL.md) owns test selection,
diagnosis, coverage scope and evidence; [TDD](../tdd/SKILL.md) describes the incremental
red/green method. Consulting these conventions does not start another workflow.

## Applying the conventions

1. Read the source file to test
2. Determine the **architectural layer** (domain, application, infrastructure, presentation)
3. Read existing fixtures in `tests/conftest.py` and relevant module `conftest.py` files
4. Read the **layer-specific patterns** from [references/patterns.md](references/patterns.md)
5. Write the test at the matching path for the selected behavior. Follow the
   project's verification guide for commands, markers and services; API tests
   require the API selector. Tests are not selected by source layer alone.

## Path Convention

Source: `backend/src/<module>/<layer>/<feature>/<file>.py`
Test: `backend/tests/<module>/<layer>/<feature>/test_<file>.py`

Ensure `__init__.py` exists in every directory of the test path.

## Core Rules

- **`expects`** for all assertions — never bare `assert`. Async exception assertions must await the call and check the captured exception with expects; see the error-path examples in [patterns.md](references/patterns.md).
- **Standalone functions** — never classes with `@staticmethod`
- **AAA pattern** — blank line before Assert block
- **async by default** — use `async def test_...` for any test involving async code. `asyncio_mode = "auto"` is configured, so no `@pytest.mark.asyncio` decorator needed
- **No `scope='function'`** on fixtures — it's the default
- Test naming: `test_<action>__<scenario>` (double underscore separates action from scenario)

## Design Principles

- **One behavior per test** — each test verifies exactly one thing. Easier to diagnose failures.
- **Always test error paths** — don't just test happy paths. Test exceptions, not-found, invalid input.
- **Use parametrize for variants** — when testing the same logic with different inputs, use `@pytest.mark.parametrize`.
- **Test isolation** — no shared state between tests. Each test is independent.

## Available Fixtures

### Global (`tests/conftest.py`)
- `tenant_id`: random UUID
- `tenant`: `Tenant` domain entity (ACTIVE status)
- `setup_database` (session-scoped, requested by DB fixtures): creates all tables via async SQLAlchemy, disposes on teardown
- `async_session`: function-scoped `AsyncSession` for DB operations

### E2E API (`tests/api/conftest.py`)
- `api_key_header`: admin API key header dict
- `new_registered_user`: registers test user via HTTP
- `new_registered_tenant`: registers test tenant via HTTP
- `login_user`: `LoginTestContext` with `access_token`, `refresh_token`, `tenant_slug`, `tenant_id`

### Module-level (in `tests/<module>/conftest.py`)
Place mocked repositories here with `create_autospec(spec=Repository, spec_set=True, instance=True)`.

### Inline (in test file)
Use for fixtures specific to that test file only (e.g., `use_case`, `orm_instance`).

## Test Markers

```python
@pytest.mark.single       # Run with pytest -m single — for debugging one test
@pytest.mark.api           # Mark as API/E2E test
@pytest.mark.db            # Mark as DB integration test
@pytest.mark.skip(reason="...")  # Skip with reason
```

Note: `asyncio_mode = "auto"` is set in `pyproject.toml`, so `@pytest.mark.asyncio` is NOT needed.

## Quick Reference by Layer

| Layer          | DB?  | Async? | Mocks?      | Fixture source                     |
|----------------|------|--------|-------------|-------------------------------------|
| Domain         | No   | No     | No          | inline or `conftest.py`             |
| Application    | No   | Yes    | Yes (repos) | `conftest.py` + module conftest     |
| Infrastructure | Yes  | Yes    | No          | `async_session` + factories         |
| Presentation   | Yes  | No*    | No          | `login_user` + `requests` (E2E)    |

*Presentation tests use `requests` (sync HTTP client) against a running server, not async.

For detailed patterns and examples per layer, see [references/patterns.md](references/patterns.md).
