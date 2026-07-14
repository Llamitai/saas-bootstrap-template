from uuid import UUID

from fastapi import Depends, status
from pydantic import Field

from src.common.domain.entities.common.requests import CamelCaseRequest
from src.common.domain.entities.common.task_result import TaskResult
from src.common.domain.entities.phone_number import RawPhoneNumber
from src.common.domain.enums.users import TenantUserStatus
from src.common.domain.models.tenants.tenant_user import TenantUser
from src.common.domain.permissions.checker import check_tenant_permission
from src.common.domain.permissions.namespaces.tenant_user import TenantUserPermission
from src.common.infrastructure.context_builder import AppContext
from src.common.infrastructure.dependencies.common import get_app_context
from src.common.infrastructure.dependencies.tenant import get_required_tenant_user, required_tenant_for
from src.common.infrastructure.responses.api_json import ApiJSONResponse
from src.tenants.presentation.presenters.tenant_user import TenantUserPresenter
from src.users.application.use_cases.tenant_user.getter import TenantUserGetter
from src.users.application.use_cases.tenant_user.remover import TenantUserRemover
from src.users.application.use_cases.tenant_user.updater import TenantUserUpdater


async def get_tenant_user(
    tenant_user_id: UUID,
    current_tenant_user: TenantUser = Depends(get_required_tenant_user),
    app_context: AppContext = Depends(get_app_context),
):
    check_tenant_permission(current_tenant_user, permissions=[TenantUserPermission.view])

    tenant = required_tenant_for(current_tenant_user)
    tenant_user = await TenantUserGetter(
        tenant_id=tenant.uuid,
        tenant_user_id=tenant_user_id,
        query_bus=app_context.bus.query_bus,
    ).execute()

    return ApiJSONResponse(
        content=TenantUserPresenter(tenant_user).to_dict,
        status_code=status.HTTP_200_OK,
    )


class UpdateTenantUserRequest(CamelCaseRequest):
    first_name: str | None = Field(default=None, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    status: TenantUserStatus | None = Field(default=None)
    tenant_role_id: UUID | None = Field(default=None)
    is_owner: bool | None = Field(default=None)
    is_support: bool | None = Field(default=None)
    email: str | None = Field(default=None)
    phone_number: RawPhoneNumber | None = Field(default=None)


async def update_tenant_user(
    tenant_user_id: UUID,
    request: UpdateTenantUserRequest,
    current_tenant_user: TenantUser = Depends(get_required_tenant_user),
    app_context: AppContext = Depends(get_app_context),
):
    check_tenant_permission(current_tenant_user, permissions=[TenantUserPermission.update])

    payload = request.model_dump(exclude_none=True)
    email = payload.pop("email", None)
    payload.pop("phone_number", None)
    # Owner/support flags are platform-sensitive. Only superusers can toggle
    # them — silently drop them if a regular tenant admin tries to send them.
    is_superuser = bool(current_tenant_user.user and current_tenant_user.user.is_superuser)
    if not is_superuser:
        payload.pop("is_owner", None)
        payload.pop("is_support", None)
    tenant = required_tenant_for(current_tenant_user)
    updated_tenant_user = await TenantUserUpdater(
        tenant_id=tenant.uuid,
        tenant_user_id=tenant_user_id,
        payload=payload,
        email=email,
        phone_number=request.phone_number,
        query_bus=app_context.bus.query_bus,
        command_bus=app_context.bus.command_bus,
        phone_number_repository=app_context.domain.phone_repository,
        email_repository=app_context.domain.email_repository,
    ).execute()

    return ApiJSONResponse(
        content=TenantUserPresenter(updated_tenant_user).to_dict,
        status_code=status.HTTP_200_OK,
    )


async def delete_tenant_user(
    tenant_user_id: UUID,
    current_tenant_user: TenantUser = Depends(get_required_tenant_user),
    app_context: AppContext = Depends(get_app_context),
):
    check_tenant_permission(current_tenant_user, permissions=[TenantUserPermission.delete])

    tenant = required_tenant_for(current_tenant_user)
    await TenantUserRemover(
        tenant_id=tenant.uuid,
        tenant_user_id=tenant_user_id,
        query_bus=app_context.bus.query_bus,
        command_bus=app_context.bus.command_bus,
    ).execute()

    return ApiJSONResponse(
        content=TaskResult.success(),
        status_code=status.HTTP_200_OK,
    )
