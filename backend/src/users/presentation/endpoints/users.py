from fastapi import status
from pydantic import EmailStr, Field

from src.common.domain.entities.common.requests import CamelCaseRequest
from src.common.domain.models.user import User
from src.common.infrastructure.dependencies.common import DomainContextDep
from src.common.infrastructure.responses.api_json import ApiJSONResponse
from src.users.application.use_cases.user.registerer import UserRegisterer
from src.users.presentation.presenters.user import RegisteredUserPresenter


class RegisterUserRequest(CamelCaseRequest):
    email: EmailStr
    password: str = Field(..., min_length=8)


async def register_user(
    request: RegisterUserRequest,
    domain_context: DomainContextDep,
) -> ApiJSONResponse:
    user = await UserRegisterer(
        user=User.from_raw(email=str(request.email)),
        password=request.password,
        user_repository=domain_context.user_repository,
    ).execute()

    return ApiJSONResponse(
        content=RegisteredUserPresenter(user).to_dict,
        status_code=status.HTTP_201_CREATED,
    )
