# Test Patterns by Architectural Layer

Paths are relative to `backend/`. Each section names an installed exemplar; read
it before writing a new test in that layer.

## 1. Domain Layer — Pure Unit Tests

No DB, no mocks. Test Pydantic models, value objects, enums, domain logic.
Exemplar: `tests/common/domain/models/tenants/test_tenant_user.py`.

```python
from uuid import uuid4

from expects import be_true, expect

from src.common.domain.enums.users import TenantUserStatus
from src.common.domain.models.tenants.tenant_user import TenantUser


def test_is_active__when_active_status():
    tenant_user = TenantUser(
        uuid=uuid4(),
        tenant_id=uuid4(),
        user_id=uuid4(),
        is_owner=False,
        status=TenantUserStatus.ACTIVE,
    )

    expect(tenant_user.is_active).to(be_true)


def test_check_permission__returns_true_for_owner():
    tenant_user = TenantUser(
        uuid=uuid4(),
        tenant_id=uuid4(),
        user_id=uuid4(),
        is_owner=True,
        status=TenantUserStatus.ACTIVE,
    )

    result = tenant_user.check_permission("any.permission")

    expect(result).to(be_true)
```

### Testing time-dependent logic
freezegun is NOT installed. Prefer controlling time through inputs: build the
entity with an explicit timestamp and assert on the derived state:
```python
from datetime import UTC, datetime, timedelta

def test_invitation__expired_when_past_expiry():
    invitation = build_invitation(expires_at=datetime.now(UTC) - timedelta(days=1))

    expect(invitation.is_expired).to(be_true)
```
When the code under test calls `datetime.now(UTC)` internally and the input
can't drive the scenario, monkeypatch `datetime` in the module under test.

---

## 2. Application Layer — Use Cases with Mocked Ports

Mock repository ports and buses via `create_autospec`. Test orchestration logic.
Use cases are **async** dataclasses with `execute()`.
Exemplar: `tests/users/application/use_cases/tenant_user/test_remover.py`.

### conftest.py for the module
```python
# tests/<module>/application/conftest.py
from unittest.mock import create_autospec

import pytest

from src.<module>.domain.repositories.<repo> import SomeRepository


@pytest.fixture
def some_repository():
    return create_autospec(spec=SomeRepository, spec_set=True, instance=True)
```
`tests/users/application/conftest.py` already provides `query_bus` and
`command_bus` this way.

### Test file
```python
from uuid import uuid4

import pytest
from expects import equal, expect

from src.common.application.commands.users import DeleteTenantUserCommand
from src.common.domain.enums.users import TenantUserStatus
from src.common.domain.exceptions.users import TenantUserNotFoundError
from src.common.domain.models.tenants.tenant_user import TenantUser
from src.users.application.use_cases.tenant_user.remover import TenantUserRemover


@pytest.fixture
def tenant_user_id():
    return uuid4()


@pytest.fixture
def use_case(tenant_id, tenant_user_id, query_bus, command_bus):
    return TenantUserRemover(
        tenant_id=tenant_id,
        tenant_user_id=tenant_user_id,
        query_bus=query_bus,
        command_bus=command_bus,
    )


async def test_execute__dispatches_delete_command(use_case, tenant_id, tenant_user_id, query_bus, command_bus):
    query_bus.ask.return_value = TenantUser(
        uuid=tenant_user_id,
        tenant_id=tenant_id,
        user_id=uuid4(),
        is_owner=False,
        status=TenantUserStatus.ACTIVE,
    )

    await use_case.execute()

    command_bus.dispatch.assert_awaited_once()
    dispatched = command_bus.dispatch.await_args.kwargs["command"]
    expect(dispatched).to(equal(DeleteTenantUserCommand(tenant_user_id=tenant_user_id)))


async def test_execute__not_found_raises(use_case, query_bus, command_bus):
    query_bus.ask.return_value = None

    with pytest.raises(TenantUserNotFoundError):
        await use_case.execute()

    command_bus.dispatch.assert_not_awaited()
```

Commands are dataclasses, so equality compares fields; the installed exemplar
checks type and fields separately, which is equally valid.

---

## 3. Infrastructure Layer — Repository Integration Tests

Real DB via `async_session`; build the adapter with that session and create data
through the adapter's own `persist`. The installed exemplars are in
`tests/users/infrastructure/repositories/` (`test_sql_user.py` checks durability
through a new session from `session_maker`). Follow the SKILL's database isolation
gotchas: rows persist for the pytest session, so every slug/email is unique.

```python
# tests/<module>/infrastructure/repositories/conftest.py
import pytest

from src.<module>.infrastructure.repositories.sql_<entity> import SQL<Entity>Repository


@pytest.fixture
def repository(async_session):
    return SQL<Entity>Repository(session=async_session)
```

```python
from uuid import uuid4

from expects import be_none, equal, expect


async def test_find__wrong_tenant_returns_none(repository, persisted_entity):
    result = await repository.find(entity_id=persisted_entity.uuid, tenant_id=uuid4())

    expect(result).to(be_none)


async def test_find__returns_entity(repository, persisted_entity):
    result = await repository.find(entity_id=persisted_entity.uuid, tenant_id=persisted_entity.tenant_id)

    expect(result.uuid).to(equal(persisted_entity.uuid))
```

Tenant-scoped adapters always get a wrong-tenant test.

---

## 4. Presentation Layer

### Unit tests calling the endpoint function
Call the async endpoint function directly with fake contexts and a monkeypatched
use case to test presentation-only rules (payload filtering, status codes).
Exemplar: `tests/tenants/presentation/test_tenant_user_endpoint.py` (its bare
`assert`s are known debt; use `expects`).

```python
async def test_update_tenant_user__regular_user_cannot_update_owner(monkeypatch):
    captured_payloads: list[dict] = []

    class CapturingUpdater:
        def __init__(self, **kwargs):
            captured_payloads.append(kwargs["payload"])

        async def execute(self):
            return updated_tenant_user

    monkeypatch.setattr(endpoint_module, "TenantUserUpdater", CapturingUpdater)

    await endpoint_module.update_tenant_user(
        tenant_user_id=uuid4(),
        request=endpoint_module.UpdateTenantUserRequest(first_name="Updated", is_owner=True),
        current_tenant_user=regular_tenant_user,
        app_context=fake_app_context,
    )

    expect(captured_payloads).to(equal([{"first_name": "Updated"}]))
```

### API/E2E tests
Full HTTP cycle with `requests` against the running stack (`just backend test api`).
Import `BASE_URL` and `LoginTestContext` from `tests.api.conftest`; tenant routes
need both `Authorization` and `x-tenant`. Exemplar: `tests/api/test_users.py`.

```python
import pytest
import requests
from expects import equal, expect

from src.common.domain.constants.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED
from tests.api.conftest import BASE_URL, LoginTestContext

pytestmark = [pytest.mark.api]


def _tenant_headers(login_user: LoginTestContext) -> dict:
    return {
        "Authorization": f"Bearer {login_user.access_token}",
        "x-tenant": login_user.tenant_slug,
    }


def test_list_invitations__authenticated(login_user):
    response = requests.get(
        url=f"{BASE_URL}/v1/tenants/invitations",
        headers=_tenant_headers(login_user),
        timeout=30,
    )

    expect(response.status_code).to(equal(HTTP_200_OK))


def test_list_invitations__unauthenticated(login_user):
    response = requests.get(
        url=f"{BASE_URL}/v1/tenants/invitations",
        headers={"x-tenant": login_user.tenant_slug},
        timeout=30,
    )

    expect(response.status_code).to(equal(HTTP_401_UNAUTHORIZED))
```

Created resources (emails, slugs) use a `uuid4().hex[:8]` suffix, as in
`tests/api/test_users.py`, because the stack database is shared by the run.

---

## Parametrized Tests

```python
import pytest
from expects import be_none, equal, expect

from src.common.domain.enums.users import TenantUserStatus


@pytest.mark.parametrize("value,expected", [
    ("ACTIVE", TenantUserStatus.ACTIVE),
    ("PENDING", TenantUserStatus.PENDING),
    ("INACTIVE", TenantUserStatus.INACTIVE),
])
def test_from_value__valid(value, expected):
    result = TenantUserStatus.from_value(value)

    expect(result).to(equal(expected))


@pytest.mark.parametrize("invalid_value", ["INVALID", "", None])
def test_from_value__invalid_returns_none(invalid_value):
    result = TenantUserStatus.from_value(invalid_value)

    expect(result).to(be_none)
```

Use `pytest.param(..., id="active-user")` for readable IDs.

---

## What NOT to Test

- `config/` — app configuration and startup
- `src/*/presentation/router.py` — route registration (just wiring)
- `scripts/` — seed and CLI scripts with heavy I/O
- `__init__.py` files
- Worker process wiring (`config/worker.py` `main`/`run_worker`) — test the command handlers the queue dispatches; the RabbitMQ delivery semantics already have broker tests in `tests/common/infrastructure/rabbitmq/` (marker `rabbitmq`)

Migrations are tested: `tests/common/database/test_migrations.py` and
`just backend check-migrations` (see [schema-change](../../schema-change/SKILL.md)).
