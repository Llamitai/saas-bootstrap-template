"""Documentation models for src/auth/presentation/presenters/session.py."""

from uuid import UUID

from src.common.domain.entities.common.jtw_session import JwtSession
from src.common.domain.models.email_address import EmailAddress
from src.common.domain.models.phone_number import PhoneNumber
from src.common.presentation.schemas.base import ApiSchema, camel_schema
from src.common.presentation.schemas.shared import TenantMetaRoleResponse

JwtSessionResponse = camel_schema(JwtSession)
PhoneNumberModel = camel_schema(PhoneNumber)
EmailAddressModel = camel_schema(EmailAddress)


class SessionUserResponse(ApiSchema):
    """UserPresenter."""

    uuid: UUID
    username: str
    first_name: str | None
    last_name: str | None
    phone_number: PhoneNumberModel | None  # ty: ignore[invalid-type-form]
    email_address: EmailAddressModel | None  # ty: ignore[invalid-type-form]
    photo_url: str | None
    is_superuser: bool


class TenantPublicResponse(ApiSchema):
    """TenantPublicPresenter."""

    uuid: UUID
    name: str
    slug: str
    time_zone: str
    country_code: str
    currency_code: str
    logo_url: str | None
    status: str


class TenantUserSessionResponse(ApiSchema):
    """TenantUserSessionPresenter."""

    session: JwtSessionResponse  # ty: ignore[invalid-type-form]
    user: SessionUserResponse
    tenant: TenantPublicResponse | None
    tenant_role: TenantMetaRoleResponse | None


class TenantUserProfileResponse(ApiSchema):
    """TenantUserProfilePresenter."""

    user: SessionUserResponse
    tenant: TenantPublicResponse | None
    tenant_role: TenantMetaRoleResponse | None
