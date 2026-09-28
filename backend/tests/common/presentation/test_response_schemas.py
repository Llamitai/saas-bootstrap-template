"""Each documented response schema matches what its presenter renders on the wire."""

from datetime import UTC, datetime
from types import UnionType
from typing import Any, Union, get_args, get_origin
from uuid import uuid4

import pytest
from expects import equal, expect
from pydantic import BaseModel

from src.admin.presentation.presenters.api_key import ApiKeyPresenter
from src.admin.presentation.schemas import ApiKeyResponse
from src.auth.presentation.presenters.session import TenantUserProfilePresenter, TenantUserSessionPresenter
from src.auth.presentation.schemas import TenantUserProfileResponse, TenantUserSessionResponse
from src.common.application.helpers.json_encoder import convert_to_camel_case
from src.common.domain.entities.admin.api_key import ApiKey
from src.common.domain.entities.auth.user_session import TenantUserProfile, TenantUserSession
from src.common.domain.entities.common.jtw_session import JwtSession
from src.common.domain.entities.common.task_result import TaskResult
from src.common.domain.entities.tenants.tenant_role import TenantRoleMeta
from src.common.domain.entities.tenants.tenant_user_stats import TenantUserStats
from src.common.domain.enums.countries import CountryIsoCode
from src.common.domain.enums.tenants import TenantRoleStatus
from src.common.domain.enums.users import TenantUserStatus
from src.common.domain.models.email_address import EmailAddress
from src.common.domain.models.phone_number import PhoneNumber
from src.common.domain.models.tenants.tenant import Tenant
from src.common.domain.models.tenants.tenant_role import TenantRole
from src.common.domain.models.tenants.tenant_user import TenantUser
from src.common.domain.models.tenants.tenant_user_invitation import TenantUserInvitation
from src.common.domain.models.user import User
from src.common.presentation.schemas.base import ApiSchema
from src.common.presentation.schemas.envelopes import TaskResultResponse
from src.profile.presentation.schemas import TenantModel, UserModel
from src.tenants.application.use_cases.invitations.getter import InvitationView
from src.tenants.presentation.presenters.tenant_role import TenantRolePresenter
from src.tenants.presentation.presenters.tenant_settings import TenantSettingsPresenter
from src.tenants.presentation.presenters.tenant_user import TenantUserPresenter
from src.tenants.presentation.presenters.tenant_user_invitation import (
    InvitationViewPresenter,
    TenantUserInvitationPresenter,
)
from src.tenants.presentation.schemas import (
    InvitationViewResponse,
    TenantRoleResponse,
    TenantSettingsResponse,
    TenantUserInvitationResponse,
    TenantUserResponse,
    TenantUserStatsModel,
)
from src.users.presentation.presenters.user import RegisteredUserPresenter
from src.users.presentation.schemas import RegisteredUserResponse

NOW = datetime(2026, 1, 1, tzinfo=UTC)
TENANT = Tenant(uuid=uuid4(), name="Acme", slug="acme", country_code=CountryIsoCode.PERU, created_at=NOW)
EMAIL = EmailAddress(uuid=uuid4(), email="ada@example.com")
PHONE = PhoneNumber(uuid=uuid4(), dial_code=51, phone_number="999888777", iso_code=CountryIsoCode.PERU)
ROLE = TenantRole(
    uuid=uuid4(), tenant_id=TENANT.uuid, name="Admin", slug="admin", status=TenantRoleStatus.ACTIVE, permissions=[]
)
USER = User(uuid=uuid4(), username="ada", email_address=EMAIL, phone_number=PHONE, role=ROLE)
TENANT_USER = TenantUser(
    uuid=uuid4(),
    tenant_id=TENANT.uuid,
    user_id=USER.uuid,
    is_owner=True,
    status=TenantUserStatus.ACTIVE,
    user=USER,
    tenant_role=ROLE,
    created_at=NOW,
)
INVITATION = TenantUserInvitation(
    uuid=uuid4(), tenant_id=TENANT.uuid, email="bob@example.com", token="t0k3n", expires_at=NOW
)
ROLE_META = TenantRoleMeta(name="Admin", status=TenantRoleStatus.ACTIVE, is_owner=True)

CASES: list[tuple[str, Any, type[BaseModel]]] = [
    ("registered user", RegisteredUserPresenter(USER).to_dict, RegisteredUserResponse),
    (
        "tenant user session",
        TenantUserSessionPresenter(
            TenantUserSession(
                session=JwtSession(access_token="a", refresh_token="r"),
                user=USER,
                tenant=TENANT,
                tenant_role=ROLE_META,
                tenant_user=TENANT_USER,
            )
        ).to_dict,
        TenantUserSessionResponse,
    ),
    (
        "tenant user profile",
        TenantUserProfilePresenter(TenantUserProfile(user=USER, tenant=TENANT, tenant_role=ROLE_META)).to_dict,
        TenantUserProfileResponse,
    ),
    ("tenant user", TenantUserPresenter(TENANT_USER).to_dict, TenantUserResponse),
    ("tenant role", TenantRolePresenter(ROLE).to_dict, TenantRoleResponse),
    ("tenant settings", TenantSettingsPresenter(TENANT).to_dict, TenantSettingsResponse),
    ("invitation", TenantUserInvitationPresenter(INVITATION).to_dict, TenantUserInvitationResponse),
    (
        "invitation view",
        InvitationViewPresenter(InvitationView(invitation=INVITATION, tenant_name="Acme", role_name=None)).to_dict,
        InvitationViewResponse,
    ),
    (
        "api key",
        ApiKeyPresenter(ApiKey(uuid=uuid4(), name="ci", key_hash="h", permissions=[], created_at=NOW)).to_dict,
        ApiKeyResponse,
    ),
    ("task result", TaskResult.success(), TaskResultResponse),
    ("profile user dump", USER.model_dump(), UserModel),
    ("tenant dump", TENANT.model_dump(), TenantModel),
    ("user stats dump", TenantUserStats(total=1, active=1, pending=0, inactive=0).model_dump(), TenantUserStatsModel),
]


def _schema_of(annotation: Any) -> type[ApiSchema] | None:
    origin = get_origin(annotation)
    if origin in (Union, UnionType, list):
        return next((schema for arg in get_args(annotation) if (schema := _schema_of(arg))), None)
    if isinstance(annotation, type) and issubclass(annotation, ApiSchema):
        return annotation
    return None


def _mismatches(value: Any, schema: type[ApiSchema], path: str) -> list[str]:
    if isinstance(value, list):
        return [issue for item in value for issue in _mismatches(item, schema, f"{path}[]")]
    if not isinstance(value, dict):
        return []
    documented = {field.alias or name: field for name, field in schema.model_fields.items()}
    issues = [f"{path}.{key}: rendered but not documented" for key in value.keys() - documented.keys()]
    issues += [
        f"{path}.{key}: documented but never rendered"
        for key, field in documented.items()
        if key not in value and field.is_required()
    ]
    for key, field in documented.items():
        nested = _schema_of(field.annotation)
        if nested and value.get(key) is not None:
            issues += _mismatches(value[key], nested, f"{path}.{key}")
    return issues


@pytest.mark.parametrize(("name", "content", "schema"), CASES, ids=[case[0] for case in CASES])
def test_response_schema__matches_the_rendered_presenter(name: str, content: Any, schema: type[ApiSchema]):
    wire = convert_to_camel_case(content)

    schema.model_validate(wire)
    expect(_mismatches(wire, schema, name)).to(equal([]))
