from uuid import UUID

from fastapi import Depends, File, UploadFile, status

from src.common.domain.entities.common.in_memory_file import InMemoryFile
from src.common.domain.models.tenants.tenant_user import TenantUser
from src.common.domain.permissions.checker import check_tenant_permission
from src.common.domain.permissions.namespaces.tenant_settings import TenantSettingPermission
from src.common.infrastructure.dependencies.common import DomainContextDep
from src.common.infrastructure.dependencies.tenant import get_required_tenant_user, required_tenant_for
from src.common.infrastructure.helpers.image_upload import read_validated_image
from src.common.infrastructure.responses.api_json import ApiJSONResponse
from src.tenants.application.use_cases.tenant.updater import TenantUpdater
from src.tenants.presentation.presenters.tenant_settings import TenantSettingsPresenter


async def update_tenant_avatar(
    tenant_id: UUID,
    domain_context: DomainContextDep,
    avatar: UploadFile = File(...),
    current_tenant_user: TenantUser = Depends(get_required_tenant_user),
) -> ApiJSONResponse:
    check_tenant_permission(current_tenant_user, permissions=[TenantSettingPermission.update])

    file_bytes = await read_validated_image(avatar)
    await avatar.close()

    current_tenant = required_tenant_for(current_tenant_user)
    tenant = await TenantUpdater(
        tenant_id=current_tenant.uuid,
        tenant_repository=domain_context.tenant_repository,
        storage_service=domain_context.storage_service,
        logo=InMemoryFile(
            file_path=avatar.filename or "avatar",
            file_bytes=file_bytes,
        ),
    ).execute()

    return ApiJSONResponse(
        content=TenantSettingsPresenter(tenant).to_dict,
        status_code=status.HTTP_200_OK,
    )
