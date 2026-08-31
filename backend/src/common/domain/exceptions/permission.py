from typing import Any

from src.common.domain.constants import status
from src.common.domain.exceptions import DomainError


class InsufficientPermissionsError(DomainError):
    def __init__(self, permissions: list[str], context=None):
        raw_permissions = ",".join(permissions)
        super().__init__(
            code="common.InsufficientPermissions",
            message=f"Required permissions: {raw_permissions}",
            status_code=status.HTTP_403_FORBIDDEN,
            context=context or {"required_permission": raw_permissions},
        )


class InvalidApiKeyScopeError(DomainError):
    def __init__(self, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="common.InvalidApiKeyScope",
            message="The API key contains an invalid tenant scope",
            status_code=status.HTTP_403_FORBIDDEN,
            context=context,
        )
