import asyncio

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.common.application.logging import get_logger

logger = get_logger(__name__)

# A readiness probe must answer before the orchestrator's own timeout.
PROBE_TIMEOUT_SECONDS = 2.0


async def database_is_ready(engine: AsyncEngine) -> bool:
    async def probe() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(probe(), timeout=PROBE_TIMEOUT_SECONDS)
    except Exception as error:
        logger.warning("health.database.unavailable", error_type=type(error).__name__)
        return False
    return True


async def redis_is_ready(redis_client: Redis) -> bool:
    try:
        await asyncio.wait_for(redis_client.ping(), timeout=PROBE_TIMEOUT_SECONDS)
    except Exception as error:
        logger.warning("health.redis.unavailable", error_type=type(error).__name__)
        return False
    return True
