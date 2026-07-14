from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.common.domain.enums.tenants import TenantStatus
from src.common.domain.enums.users import TenantUserStatus
from src.common.domain.exceptions.tenants import TenantNotFoundError
from src.common.domain.exceptions.users import TenantUserRequiredError
from src.common.domain.models.tenants.tenant import Tenant
from src.common.domain.models.tenants.tenant_user import TenantUser
from src.common.infrastructure.dependencies.tenant import (
    get_required_tenant,
    get_required_tenant_user,
    get_tenant,
    required_tenant_for,
)


class InMemoryTenantRepository:
    def __init__(self, tenant: Tenant | None = None) -> None:
        self.tenant = tenant
        self.requested_slugs: list[str] = []

    async def find_by_slug(self, tenant_slug: str) -> Tenant | None:
        self.requested_slugs.append(tenant_slug)
        return self.tenant


class InMemoryTenantUserRepository:
    def __init__(self, tenant_user: TenantUser | None = None) -> None:
        self.tenant_user = tenant_user
        self.requested_args: list[tuple[object, object]] = []

    async def find_by_args(self, user_id, tenant_id) -> TenantUser | None:
        self.requested_args.append((user_id, tenant_id))
        return self.tenant_user


def _tenant() -> Tenant:
    return Tenant(
        uuid=uuid4(),
        owner_id=uuid4(),
        name="Acme",
        slug="acme",
        status=TenantStatus.ACTIVE,
    )


def _tenant_user(tenant: Tenant) -> TenantUser:
    return TenantUser(
        uuid=uuid4(),
        user_id=uuid4(),
        tenant_id=tenant.uuid,
        is_owner=False,
        status=TenantUserStatus.ACTIVE,
    )


def _context(
    tenant_repository: InMemoryTenantRepository | None = None,
    tenant_user_repository: InMemoryTenantUserRepository | None = None,
):
    return SimpleNamespace(
        tenant_repository=tenant_repository or InMemoryTenantRepository(),
        tenant_user_repository=tenant_user_repository or InMemoryTenantUserRepository(),
    )


@pytest.mark.asyncio
async def test_get_tenant_returns_none_without_header() -> None:
    repository = InMemoryTenantRepository()

    tenant = await get_tenant(_context(tenant_repository=repository), tenant_slug=None)

    assert tenant is None
    assert repository.requested_slugs == []


@pytest.mark.asyncio
async def test_get_required_tenant_strips_header_slug() -> None:
    expected_tenant = _tenant()
    repository = InMemoryTenantRepository(expected_tenant)

    tenant = await get_required_tenant(_context(tenant_repository=repository), tenant_slug=" acme ")

    assert tenant is expected_tenant
    assert repository.requested_slugs == ["acme"]


@pytest.mark.asyncio
async def test_get_required_tenant_raises_without_header() -> None:
    with pytest.raises(TenantNotFoundError):
        await get_required_tenant(_context(), tenant_slug=" ")


@pytest.mark.asyncio
async def test_get_required_tenant_user_attaches_resolved_tenant() -> None:
    tenant = _tenant()
    tenant_user = _tenant_user(tenant)
    repository = InMemoryTenantUserRepository(tenant_user)
    user = SimpleNamespace(uuid=tenant_user.user_id)

    result = await get_required_tenant_user(user, _context(tenant_user_repository=repository), tenant)

    assert result is tenant_user
    assert result.tenant is tenant
    assert repository.requested_args == [(tenant_user.user_id, tenant.uuid)]


@pytest.mark.asyncio
async def test_get_required_tenant_user_raises_when_membership_is_missing() -> None:
    tenant = _tenant()
    user = SimpleNamespace(uuid=uuid4())

    with pytest.raises(TenantUserRequiredError):
        await get_required_tenant_user(user, _context(), tenant)


def test_required_tenant_for_rejects_unloaded_tenant_user() -> None:
    tenant_user = _tenant_user(_tenant())

    with pytest.raises(TenantNotFoundError):
        required_tenant_for(tenant_user)
