from uuid import UUID

from fastapi import Depends

from src.admin.application.use_cases.api_key.hasher import ApiKeyHasher
from src.admin.presentation.presenters.api_key import ApiKeyPresenter
from src.common.domain.constants import status
from src.common.domain.contexts.domain import DomainContext
from src.common.infrastructure.dependencies.api_keys import get_admin_api_key
from src.common.infrastructure.dependencies.common import get_domain_context
from src.common.infrastructure.responses.api_json import ApiJSONResponse


async def hash_directus_api_key(
    api_key_id: UUID,
    domain_context: DomainContext = Depends(get_domain_context),
    _master_api_key: str = Depends(get_admin_api_key),
) -> ApiJSONResponse:
    """
    Hashes the raw secret of a Directus API key.
    """
    hashed_api_key = await ApiKeyHasher(
        api_key_id=api_key_id,
        api_key_repository=domain_context.api_key_repository,
    ).execute()

    return ApiJSONResponse(
        content=ApiKeyPresenter(hashed_api_key).to_dict,
        status_code=status.HTTP_200_OK,
    )
