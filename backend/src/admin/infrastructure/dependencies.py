from typing import Annotated

from fastapi import Depends, Security
from fastapi.security.api_key import APIKeyHeader

from src.admin.application.helpers.api_key_secret import hash_api_key_secret
from src.common.domain.entities.admin.api_key import ApiKey
from src.common.domain.exceptions.common import UnauthorizedIntegrationError
from src.common.infrastructure.dependencies.common import DomainContextDep

admin_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    domain_context: DomainContextDep,
    raw_secret: str = Security(admin_api_key_header),
) -> ApiKey:
    if not raw_secret:
        raise UnauthorizedIntegrationError

    api_key = await domain_context.api_key_repository.find_by_hash(hash_api_key_secret(raw_secret))
    if not api_key or not api_key.is_active:
        raise UnauthorizedIntegrationError

    return api_key


AdminApiKeyDep = Annotated[ApiKey, Depends(get_api_key)]
