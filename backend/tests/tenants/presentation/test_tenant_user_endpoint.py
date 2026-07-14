from types import SimpleNamespace
from uuid import uuid4

from fastapi import status

from src.common.domain.enums.users import TenantUserStatus
from src.common.domain.models.tenants.tenant import Tenant
from src.common.domain.models.tenants.tenant_user import TenantUser
from src.common.domain.models.user import User
from src.common.domain.permissions.namespaces.tenant_user import TenantUserPermission
from src.tenants.presentation.endpoints import tenant_user as endpoint_module


def _current_tenant_user(*, is_superuser: bool) -> TenantUser:
    tenant = Tenant(uuid=uuid4(), name="Test tenant", slug="test-tenant")
    user = User(
        uuid=uuid4(),
        username="actor",
        is_superuser=is_superuser,
    )
    return TenantUser(
        uuid=uuid4(),
        tenant_id=tenant.uuid,
        user_id=user.uuid,
        is_owner=False,
        status=TenantUserStatus.ACTIVE,
        permissions=[TenantUserPermission.update],
        tenant=tenant,
        user=user,
    )


def _app_context():
    return SimpleNamespace(
        bus=SimpleNamespace(
            query_bus=object(),
            command_bus=object(),
        ),
        domain=SimpleNamespace(
            phone_repository=object(),
            email_repository=object(),
        ),
    )


async def test_update_tenant_user__regular_user_cannot_update_owner_or_support(monkeypatch):
    captured_payloads: list[dict] = []
    updated = _current_tenant_user(is_superuser=False)

    class CapturingTenantUserUpdater:
        def __init__(self, **kwargs):
            captured_payloads.append(kwargs["payload"])

        async def execute(self) -> TenantUser:
            return updated

    monkeypatch.setattr(endpoint_module, "TenantUserUpdater", CapturingTenantUserUpdater)

    response = await endpoint_module.update_tenant_user(
        tenant_user_id=uuid4(),
        request=endpoint_module.UpdateTenantUserRequest(
            first_name="Updated",
            is_owner=True,
            is_support=True,
        ),
        current_tenant_user=_current_tenant_user(is_superuser=False),
        app_context=_app_context(),
    )

    assert response.status_code == status.HTTP_200_OK
    assert captured_payloads == [{"first_name": "Updated"}]


async def test_update_tenant_user__superuser_can_update_owner_and_support(monkeypatch):
    captured_payloads: list[dict] = []
    updated = _current_tenant_user(is_superuser=True)

    class CapturingTenantUserUpdater:
        def __init__(self, **kwargs):
            captured_payloads.append(kwargs["payload"])

        async def execute(self) -> TenantUser:
            return updated

    monkeypatch.setattr(endpoint_module, "TenantUserUpdater", CapturingTenantUserUpdater)

    response = await endpoint_module.update_tenant_user(
        tenant_user_id=uuid4(),
        request=endpoint_module.UpdateTenantUserRequest(
            first_name="Updated",
            is_owner=True,
            is_support=True,
        ),
        current_tenant_user=_current_tenant_user(is_superuser=True),
        app_context=_app_context(),
    )

    assert response.status_code == status.HTTP_200_OK
    assert captured_payloads == [
        {
            "first_name": "Updated",
            "is_owner": True,
            "is_support": True,
        }
    ]
