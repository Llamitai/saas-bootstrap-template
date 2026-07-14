from src.common.domain.entities.tenants.tenant_role import TenantRoleMeta
from src.common.domain.permissions.catalog import FULL_PERMISSIONS
from src.common.domain.permissions.namespaces.tenant_settings import TenantSettingPermission
from src.common.domain.permissions.namespaces.tenant_user import TenantUserPermission

DEFAULT_TENANT_ROLES = [
    TenantRoleMeta(
        name="Administrador",
        slug="admin",
        permissions=FULL_PERMISSIONS,
    ),
    TenantRoleMeta(
        name="Miembro",
        slug="member",
        permissions=[
            TenantUserPermission.view,
            TenantSettingPermission.view,
        ],
    ),
]
