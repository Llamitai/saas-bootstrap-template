"""Documentation models for presenters in src/common/presentation/presenters."""

from uuid import UUID

from src.common.domain.enums.tenants import TenantRoleStatus
from src.common.domain.models.tenants.tenant import Tenant
from src.common.presentation.schemas.base import ApiSchema, camel_schema
from src.common.presentation.schemas.envelopes import PermissionResponse


class EmailAddressResponse(ApiSchema):
    """EmailAddressPresenter."""

    uuid: UUID
    email: str
    is_verified: bool


class PhoneNumberResponse(ApiSchema):
    """PhoneNumberPresenter."""

    uuid: UUID
    dial_code: int
    phone_number: str
    is_verified: bool


class TenantMetaRoleResponse(ApiSchema):
    """TenantMetaRolePresenter."""

    name: str
    status: TenantRoleStatus
    is_owner: bool
    permissions: list[PermissionResponse]


class TenantModel(camel_schema(Tenant)):  # ty: ignore[unsupported-base]  generated model
    """`Tenant.model_dump()` as rendered by the endpoints that still return it."""
