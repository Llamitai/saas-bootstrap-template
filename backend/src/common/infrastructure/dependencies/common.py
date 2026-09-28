from collections.abc import AsyncGenerator
from typing import Annotated, cast

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database.config import DatabaseConfig
from src.common.domain.buses.async_commands import CommandEnqueuer
from src.common.domain.contexts.bus import BusContext
from src.common.domain.contexts.domain import DomainContext
from src.common.infrastructure.bus_builder import build_async_bus
from src.common.infrastructure.context_builder import AppContext
from src.common.infrastructure.domain_builder import build_async_domain


async def get_database_session(request: Request) -> AsyncGenerator[AsyncSession]:
    database_config: DatabaseConfig = request.app.state.database_config
    async with database_config.session_maker() as session:
        request.state.db_session = session
        try:
            yield session
        finally:
            await session.close()


AsyncSessionDep = Annotated[AsyncSession, Depends(get_database_session)]


def get_redis_client(request: Request) -> Redis:
    return cast("Redis", request.app.state.redis_client)


RedisClientDep = Annotated[Redis, Depends(get_redis_client)]


def get_command_enqueuer(request: Request) -> CommandEnqueuer:
    return cast("CommandEnqueuer", request.app.state.command_enqueuer)


CommandEnqueuerDep = Annotated[CommandEnqueuer, Depends(get_command_enqueuer)]


async def get_domain_context(session: AsyncSessionDep, redis_client: RedisClientDep) -> DomainContext:
    return build_async_domain(session=session, redis_client=redis_client)


DomainContextDep = Annotated[DomainContext, Depends(get_domain_context)]


async def get_bus_context(
    session: AsyncSessionDep,
    domain: DomainContextDep,
    enqueuer: CommandEnqueuerDep,
) -> BusContext:
    return build_async_bus(session=session, domain=domain, enqueuer=enqueuer)


BusContextDep = Annotated[BusContext, Depends(get_bus_context)]


async def get_app_context(
    domain: DomainContextDep,
    bus: BusContextDep,
) -> AppContext:
    return AppContext(domain=domain, bus=bus)
