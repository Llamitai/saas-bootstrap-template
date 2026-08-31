from uuid import UUID

from fastapi import Depends

from src.admin.infrastructure.dependencies import get_api_key
from src.common.application.commands.users import SetUserPasswordCommand
from src.common.domain.constants import status
from src.common.domain.entities.admin.api_key import ApiKey
from src.common.domain.entities.common.requests import CamelCaseRequest
from src.common.domain.entities.common.task_result import TaskResult
from src.common.domain.permissions.checker import check_admin_permission
from src.common.domain.permissions.namespaces.admin.user import AdminUserPermission
from src.common.infrastructure.context_builder import AppContext
from src.common.infrastructure.dependencies.common import get_app_context
from src.common.infrastructure.responses.api_json import ApiJSONResponse


class SetUserPasswordRequest(CamelCaseRequest):
    user_id: UUID
    password: str


async def set_user_password(
    request: SetUserPasswordRequest,
    app_context: AppContext = Depends(get_app_context),
    api_key: ApiKey = Depends(get_api_key),
) -> ApiJSONResponse:

    check_admin_permission(api_key, [AdminUserPermission.set_password])

    await app_context.bus.command_bus.dispatch(
        command=SetUserPasswordCommand(
            user_id=request.user_id,
            password=request.password,
        ),
    )
    return ApiJSONResponse(
        content=TaskResult.success().to_dict,
        status_code=status.HTTP_201_CREATED,
    )
