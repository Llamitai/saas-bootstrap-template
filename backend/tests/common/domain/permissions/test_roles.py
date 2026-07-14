from uuid import uuid4

import pytest

from src.common.domain.enums.tenants import TenantRoleStatus
from src.common.domain.models.tenants.tenant_role import TenantRole
from src.common.domain.permissions.catalog import FULL_PERMISSIONS
from src.common.domain.permissions.namespaces.tenant_settings import TenantSettingPermission
from src.common.domain.permissions.namespaces.tenant_user import TenantUserPermission
from src.common.domain.permissions.roles import DEFAULT_TENANT_ROLES
from src.tenants.application.use_cases.role.bootstrapper import TenantRolesBootstrapper


class InMemoryTenantRoleRepository:
    def __init__(self, roles: list[TenantRole]):
        self.roles = roles
        self.persisted: list[TenantRole] = []

    async def find_by_slug(self, tenant_id, slug):
        return next((role for role in self.roles if role.tenant_id == tenant_id and role.slug == slug), None)

    async def persist(self, instance):
        existing = await self.find_by_slug(instance.tenant_id, instance.slug)
        if existing is None:
            self.roles.append(instance)
        self.persisted.append(instance)
        return instance


def test_default_admin_role_includes_all_catalog_permissions() -> None:
    admin_role = next(role for role in DEFAULT_TENANT_ROLES if role.slug == "admin")

    assert admin_role.permissions == FULL_PERMISSIONS
    assert {
        TenantSettingPermission.view,
        TenantSettingPermission.delete,
        TenantUserPermission.create,
    }.issubset(admin_role.permissions)


@pytest.mark.asyncio
async def test_bootstrapper_syncs_existing_admin_role_with_full_permissions() -> None:
    tenant_id = uuid4()
    admin_role = TenantRole(
        uuid=uuid4(),
        tenant_id=tenant_id,
        name="Administrador",
        slug="admin",
        status=TenantRoleStatus.INACTIVE,
        permissions=[TenantSettingPermission.view],
    )
    repository = InMemoryTenantRoleRepository([admin_role])

    await TenantRolesBootstrapper(tenant_id=tenant_id, role_repository=repository).execute()

    assert admin_role.permissions == FULL_PERMISSIONS
    assert admin_role.status == TenantRoleStatus.ACTIVE
