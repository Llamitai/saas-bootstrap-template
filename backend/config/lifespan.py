from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI

from src.common.application.logging import get_logger
from src.common.database.config import get_database_config
from src.common.infrastructure.rabbitmq.broker import RabbitMQBroker
from src.common.infrastructure.rabbitmq.topology import CommandQueueTopology
from src.common.infrastructure.redis_client import create_redis_client
from src.common.settings import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --------- STARTUP ----------
    database_config = get_database_config()
    redis_client = create_redis_client(settings)
    # Fails fast when RabbitMQ is unreachable: deferred commands would otherwise
    # be lost at dispatch time.
    rabbitmq = await RabbitMQBroker.connect(
        settings.rabbitmq_url,
        CommandQueueTopology.from_settings(settings),
        connection_name=f"{settings.PROJECT_NAME} api",
        publish_timeout=settings.RABBITMQ_PUBLISH_TIMEOUT_SECONDS,
    )

    app_with_context = cast("Any", app)
    app_with_context.state.database_config = database_config
    app_with_context.state.redis_client = redis_client
    app_with_context.state.command_enqueuer = rabbitmq.command_enqueuer()

    yield

    # --------- SHUTDOWN ----------
    await rabbitmq.close()
    await database_config.dispose()
    await redis_client.aclose()
