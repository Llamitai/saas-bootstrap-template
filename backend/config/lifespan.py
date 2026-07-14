from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from redis.asyncio import Redis

from src.common.application.logging import get_logger
from src.common.database.config import get_database_config
from src.common.settings import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --------- STARTUP ----------
    database_config = get_database_config()

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        encoding="utf-8",
    )

    app_with_context = cast("Any", app)
    app_with_context.state.database_config = database_config
    app_with_context.state.redis_client = redis_client

    yield

    # --------- SHUTDOWN ----------
    await database_config.dispose()
    await redis_client.aclose()
