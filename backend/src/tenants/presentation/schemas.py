"""Documentation models for src/tenants/presentation/presenters and inline payloads."""

from datetime import datetime
from uuid import UUID

from src.auth.presentation.schemas import TenantPublicResponse
from src.common.domain.entities.tenants.tenant_user_stats import TenantUserStats
from src.common.domain.enums.tenants import TenantRoleStatus, TenantUserInvitationStatus
from src.common.domain.enums.users import TenantUserStatus
from src.common.presentation.schemas.base import ApiSchema, camel_schema
from src.common.presentation.schemas.envelopes import EmailResponse, PermissionResponse
from src.common.presentation.schemas.shared import EmailAddressResponse, PhoneNumberResponse


class TenantRoleResponse(ApiSchema):
    """TenantRolePresenter."""

    uuid: UUID
    name: str
    slug: str
    status: TenantRoleStatus
    permissions: list[PermissionResponse]
    icon_url: str | None


class SimpleTenantRoleResponse(ApiSchema):
    """SimpleTenantRolePresenter."""

    uuid: UUID
    name: str
    status: TenantRoleStatus


class TenantSettingsResponse(ApiSchema):
    """TenantSettingsPresenter. `tenantId` carries the tenant slug."""

    uuid: UUID
    name: str
    tenant_id: str
    avatar: str | None


class TenantUserResponse(ApiSchema):
    """TenantUserPresenter."""

    uuid: UUID
    first_name: str | None
    last_name: str | None
    phone_number: PhoneNumberResponse | None
    email_address: EmailAddressResponse | None
    is_owner: bool
    is_support: bool
    photo_url: str | None
    status: TenantUserStatus
    tenant_role: SimpleTenantRoleResponse | None
    created_at: datetime | None


class TenantUserInvitationResponse(ApiSchema):
    """TenantUserInvitationPresenter."""

    uuid: UUID | None
    tenant_id: UUID | None
    email: str
    tenant_role_id: UUID | None
    token: str
    status: TenantUserInvitationStatus
    expires_at: datetime | None
    accepted_at: datetime | None
    created_by_id: UUID | None
    requires_password: bool
    created_at: datetime | None


class InvitationViewResponse(ApiSchema):
    """InvitationViewPresenter."""

    email: str
    tenant_name: str
    role_name: str | None
    expires_at: datetime | None
    requires_password: bool


class CreatedInvitationsResponse(ApiSchema):
    invitations: list[TenantUserInvitationResponse]
    skipped_existing_members: list[EmailResponse]


class OnboardedTenantResponse(ApiSchema):
    tenant: TenantPublicResponse
    invitations: list[TenantUserInvitationResponse]
    skipped_existing_members: list[EmailResponse]


class BootstrappedRolesResponse(ApiSchema):
    created: int
    roles: list[TenantRoleResponse]


class TenantUserStatsModel(camel_schema(TenantUserStats)):  # ty: ignore[unsupported-base]  generated model
    """`TenantUserStats.model_dump()` as rendered by the stats endpoint."""
