from fastapi import APIRouter, Depends, status

from src.common.infrastructure.dependencies.rate_limit import create_rate_limit_dependency
from src.common.presentation.schemas.envelopes import Envelope
from src.users.presentation.endpoints.users import register_user
from src.users.presentation.schemas import RegisteredUserResponse

user_router = APIRouter(prefix="/users", tags=["users"])

# Per-IP limit on account creation: slows down mass sign-ups and email probing
# while leaving room for a household or office behind one address.
register_rate_limit = create_rate_limit_dependency(limit=10, window=10 * 60)

user_router.add_api_route(
    "",
    register_user,
    methods=["POST"],
    summary="Register a new user",
    dependencies=[Depends(register_rate_limit)],
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[RegisteredUserResponse],
)
