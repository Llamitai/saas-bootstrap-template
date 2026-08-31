from uuid import UUID

from src.common.constants import PERMISSIONS_ENABLED
from src.common.domain.entities.admin.api_key import ApiKey
from src.common.domain.exceptions.permission import InsufficientPermissionsError
from src.common.domain.models.tenants.tenant_user import TenantUser


def check_tenant_permission(
    tenant_user: TenantUser | None,
    permissions: list[str],
) -> bool:
    if not PERMISSIONS_ENABLED:
        return True

    if not tenant_user or tenant_user.check_permissions(permissions) is False:
        raise InsufficientPermissionsError(permissions=permissions)
    return True


def check_admin_permission(
    api_key: ApiKey | None,
    permissions: list[str],
    tenant_id: UUID | None = None,
) -> bool:

    if not api_key or not api_key.has_permissions(permissions):
        raise InsufficientPermissionsError(permissions=permissions)

    # solo comprueba el tenant_id si la ruta lo requiere
    if tenant_id is not None and not api_key.allows_tenant(tenant_id):
        raise InsufficientPermissionsError(permissions=permissions)

    return True


def check_admin_permission_for_tenants(
    api_key: ApiKey | None,
    permissions: list[str],
    tenant_ids: list[UUID] | None = None,
) -> bool:

    if not api_key or not api_key.has_permissions(permissions) or not api_key.allows_tenants(tenant_ids):
        raise InsufficientPermissionsError(permissions=permissions)
    return True
