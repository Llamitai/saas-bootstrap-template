from fastapi import APIRouter, status

from src.admin.presentation.endpoints.hash_directus_api_key import hash_directus_api_key
from src.admin.presentation.endpoints.set_user_password import set_user_password
from src.admin.presentation.schemas import ApiKeyResponse
from src.common.presentation.schemas.envelopes import Envelope, TaskResultResponse

tasks_router = router = APIRouter(tags=["tasks"])


tasks_router.add_api_route(
    path="/admin/users/set-password",
    endpoint=set_user_password,
    methods=["POST"],
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[TaskResultResponse],
)

tasks_router.add_api_route(
    path="/admin/api-keys/{api_key_id}/directus/hash-key",
    endpoint=hash_directus_api_key,
    methods=["POST"],
    response_model=Envelope[ApiKeyResponse],
)
