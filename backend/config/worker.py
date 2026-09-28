"""RabbitMQ worker for deferred commands.

Launch with:  python -m config.worker

Consumes the quorum command queue with manual acknowledgement, runs each command
in its own database session through the same builders as the API and stops
gracefully on SIGTERM/SIGINT (no new deliveries, in-flight commands finish).
"""

import asyncio
import signal
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from src.common.application.async_tasks.resolver import AsyncTaskResolver
from src.common.application.helpers.task_tracker import log_task_result, track_async_task
from src.common.application.logging import get_logger
from src.common.constants import AWS_LAMBDA_MAX_TIMEOUT
from src.common.database.config import DatabaseConfig, get_database_config
from src.common.domain.buses.async_commands import CommandEnqueuer
from src.common.domain.entities.common.async_task import AsyncTask
from src.common.infrastructure.bus_builder import build_async_bus
from src.common.infrastructure.domain_builder import build_async_domain
from src.common.infrastructure.rabbitmq.broker import RabbitMQBroker
from src.common.infrastructure.rabbitmq.consumer import CommandConsumer
from src.common.infrastructure.rabbitmq.topology import CommandQueueTopology
from src.common.infrastructure.redis_client import create_redis_client
from src.common.settings import settings

logger = get_logger()


@dataclass
class CommandRunner:
    """Runs one deferred command in its own session, like the former SAQ job."""

    database_config: DatabaseConfig
    redis_client: Redis
    enqueuer: CommandEnqueuer

    async def __call__(self, payload: dict[str, Any]) -> AsyncTask:
        command_name = payload.get("command_name", "unknown")
        async with track_async_task(command_name), self.database_config.session_maker() as session:
            bus = build_async_bus(
                session=session,
                domain=build_async_domain(session=session, redis_client=self.redis_client),
                enqueuer=self.enqueuer,
            )
            task_result = await AsyncTaskResolver(command_bus=bus.command_bus, payload=payload).execute()
        log_task_result(task_result)
        return task_result


async def run_worker(stop: asyncio.Event) -> None:
    database_config = get_database_config()
    redis_client = create_redis_client(settings)
    broker = await RabbitMQBroker.connect(
        settings.rabbitmq_url,
        CommandQueueTopology.from_settings(settings),
        connection_name=f"{settings.PROJECT_NAME} worker",
        publish_timeout=settings.RABBITMQ_PUBLISH_TIMEOUT_SECONDS,
    )
    try:
        consumer = CommandConsumer(
            queue=await broker.consumer_queue(prefetch_count=settings.RABBITMQ_PREFETCH),
            process=CommandRunner(
                database_config=database_config,
                redis_client=redis_client,
                enqueuer=broker.command_enqueuer(),
            ),
            task_timeout=AWS_LAMBDA_MAX_TIMEOUT,
            max_attempts=settings.RABBITMQ_DELIVERY_LIMIT,
            retry_backoff=settings.RABBITMQ_RETRY_BACKOFF_SECONDS,
        )
        await consumer.start()
        logger.info("rabbitmq.worker.started", prefetch=settings.RABBITMQ_PREFETCH)
        await stop.wait()
        await consumer.stop(grace_period=settings.RABBITMQ_SHUTDOWN_GRACE_SECONDS)
    finally:
        await broker.close()
        await database_config.dispose()
        await redis_client.aclose()
        logger.info("rabbitmq.worker.stopped")


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    await run_worker(stop)


if __name__ == "__main__":
    asyncio.run(main())
