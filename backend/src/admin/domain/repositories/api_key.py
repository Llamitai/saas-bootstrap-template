from abc import ABC, abstractmethod
from uuid import UUID

from src.common.domain.entities.admin.api_key import ApiKey


class ApiKeyRepository(ABC):
    @abstractmethod
    async def find(
        self,
        instance_id: UUID,
    ) -> ApiKey | None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_hash(
        self,
        key_hash: str,
    ) -> ApiKey | None:
        raise NotImplementedError

    @abstractmethod
    async def persist(
        self,
        instance: ApiKey,
    ) -> ApiKey:
        raise NotImplementedError
