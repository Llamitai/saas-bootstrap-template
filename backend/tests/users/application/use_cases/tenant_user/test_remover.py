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
def tenant_user(tenant_user_id, tenant_id):
    return TenantUser(
        uuid=tenant_user_id,
        tenant_id=tenant_id,
        user_id=uuid4(),
        is_owner=False,
        status=TenantUserStatus.ACTIVE,
    )


@pytest.fixture
def use_case(tenant_id, tenant_user_id, query_bus, command_bus):
    return TenantUserRemover(
        tenant_id=tenant_id,
        tenant_user_id=tenant_user_id,
        query_bus=query_bus,
        command_bus=command_bus,
    )


async def test_execute__dispatches_delete_command(
    use_case,
    tenant_user,
    tenant_user_id,
    query_bus,
    command_bus,
):
    query_bus.ask.return_value = tenant_user

    await use_case.execute()

    command_bus.dispatch.assert_awaited_once()
    dispatched = command_bus.dispatch.await_args.kwargs["command"]
    expect(isinstance(dispatched, DeleteTenantUserCommand)).to(equal(True))
    expect(dispatched.tenant_user_id).to(equal(tenant_user_id))


async def test_execute__not_found_raises(use_case, query_bus, command_bus):
    query_bus.ask.return_value = None

    with pytest.raises(TenantUserNotFoundError):
        await use_case.execute()

    command_bus.dispatch.assert_not_awaited()


async def test_execute__cross_tenant_user_treated_as_not_found(
    use_case,
    tenant_user_id,
    query_bus,
    command_bus,
):
    """Defensive: a tenant user belonging to another tenant must never be
    deletable through this tenant's use case."""
    other_tenant_user = TenantUser(
        uuid=tenant_user_id,
        tenant_id=uuid4(),
        user_id=uuid4(),
        is_owner=False,
        status=TenantUserStatus.ACTIVE,
    )
    query_bus.ask.return_value = other_tenant_user

    with pytest.raises(TenantUserNotFoundError):
        await use_case.execute()

    command_bus.dispatch.assert_not_awaited()
