from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.domain.repositories.api_key import ApiKeyRepository
from src.common.database.models.admin.api_key import ApiKeyORM
from src.common.domain.entities.admin.api_key import ApiKey
from src.common.domain.helpers.models import override_dict_properties
from src.common.infrastructure.builders.admin.api_key import build_api_key
from src.common.infrastructure.helpers.database import atomic_transaction


@dataclass
class SQLApiKeyRepository(ApiKeyRepository):
    session: AsyncSession

    async def find(
        self,
        instance_id: UUID,
    ) -> ApiKey | None:
        stmt = select(ApiKeyORM).where(ApiKeyORM.uuid == instance_id)
        result = await self.session.execute(stmt)
        orm_instance = result.scalar_one_or_none()

        return build_api_key(orm_instance) if orm_instance else None

    async def find_by_hash(
        self,
        key_hash: str,
    ) -> ApiKey | None:
        stmt = select(ApiKeyORM).where(ApiKeyORM.key_hash == key_hash)
        result = await self.session.execute(stmt)
        orm_instance = result.scalar_one_or_none()

        return build_api_key(orm_instance) if orm_instance else None

    async def persist(
        self,
        instance: ApiKey,
    ) -> ApiKey:
        async with atomic_transaction(self.session):
            orm_instance = await self.session.get(ApiKeyORM, instance.uuid)

            if orm_instance:
                override_dict_properties(orm_instance, instance.to_persist_dict)
            else:
                orm_instance = ApiKeyORM(
                    uuid=instance.uuid,
                    **instance.to_persist_dict,
                )
                self.session.add(orm_instance)
            await self.session.flush()
            await self.session.refresh(orm_instance)

        return build_api_key(orm_instance)
