from dataclasses import dataclass
from uuid import UUID

from src.admin.application.helpers.api_key_secret import get_api_key_prefix, hash_api_key_secret
from src.admin.domain.exceptions import ApiKeyNotFoundError
from src.admin.domain.repositories.api_key import ApiKeyRepository
from src.common.domain.entities.admin.api_key import ApiKey
from src.common.domain.interfaces.use_case import UseCase


@dataclass
class ApiKeyHasher(UseCase):
    api_key_id: UUID
    api_key_repository: ApiKeyRepository

    async def execute(self) -> ApiKey:
        api_key = await self.api_key_repository.find(instance_id=self.api_key_id)
        if api_key is None:
            raise ApiKeyNotFoundError()
        raw_secret = api_key.key_hash
        api_key.key_prefix = get_api_key_prefix(raw_secret)
        api_key.key_hash = hash_api_key_secret(raw_secret)

        return await self.api_key_repository.persist(api_key)
