from fastapi import Depends, status
from pydantic import Field

from src.auth.application.use_cases.password_reset.resetter import PasswordResetter
from src.common.domain.entities.common.requests import CamelCaseRequest
from src.common.domain.entities.common.task_result import TaskResult
from src.common.infrastructure.context_builder import AppContext
from src.common.infrastructure.dependencies.common import RedisClientDep, get_app_context
from src.common.infrastructure.responses.api_json import ApiJSONResponse
from src.common.infrastructure.services.redis_token_store import RedisTokenStore


class ResetPasswordConfirmRequest(CamelCaseRequest):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=128)


async def reset_password_confirm(
    payload: ResetPasswordConfirmRequest,
    redis_client: RedisClientDep,
    app_context: AppContext = Depends(get_app_context),
):
    await PasswordResetter(
        token=payload.token,
        new_password=payload.password,
        user_repository=app_context.domain.user_repository,
        token_service=app_context.domain.token_service,
        token_store=RedisTokenStore(redis_client=redis_client),
    ).execute()

    return ApiJSONResponse(
        content=TaskResult.success(),
        status_code=status.HTTP_200_OK,
    )
