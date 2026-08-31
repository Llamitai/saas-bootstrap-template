from typing import Any

from src.common.domain.permissions.namespaces.admin.user import AdminUserPermission

ADMIN_PERMISSIONS_CATALOG: dict[Any, str] = {
    # Users
    AdminUserPermission.set_password: "Establecer contraseña de usuario",
}
ADMIN_FULL_PERMISSIONS = list(ADMIN_PERMISSIONS_CATALOG.keys())


def get_admin_permission_label(permission_code: str) -> str:
    return ADMIN_PERMISSIONS_CATALOG.get(permission_code, "Permiso desconocido")


def admin_permission_to_dict(permission_code: str) -> dict[str, str]:
    return {
        "code": permission_code,
        "label": get_admin_permission_label(permission_code),
    }


def admin_permissions_to_list_dict(permission_codes: list[str]) -> list[dict[str, str]]:
    return [admin_permission_to_dict(code) for code in permission_codes]
