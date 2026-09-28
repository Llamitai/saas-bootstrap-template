from datetime import datetime
from uuid import UUID

from src.common.presentation.schemas.base import ApiSchema
from src.common.presentation.schemas.envelopes import PermissionResponse


class ApiKeyResponse(ApiSchema):
    """ApiKeyPresenter."""

    uuid: UUID
    name: str
    key_prefix: str | None
    tenant_ids: list[UUID] | None
    is_general_scope: bool
    permissions: list[PermissionResponse]
    is_revoked: bool
    created_at: datetime | None
    updated_at: datetime | None
