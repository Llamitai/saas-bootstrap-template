from dataclasses import dataclass
from typing import Self

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue, AbstractRobustConnection

from src.common.application.logging import get_logger
from src.common.infrastructure.buses.rabbitmq_command_enqueuer import RabbitMQCommandEnqueuer
from src.common.infrastructure.rabbitmq.topology import CommandQueueTopology, declare_topology

logger = get_logger(__name__)


@dataclass
class RabbitMQBroker:
    """One robust connection per process with a publisher-confirm channel.

    Created once by the API lifespan or the worker and closed on shutdown. The
    robust connection reconnects and restores channels, exchanges, queues and
    consumers after a broker restart; publications in flight during the outage
    fail and are reported to the caller.
    """

    connection: AbstractRobustConnection
    publisher_channel: AbstractChannel
    exchange: AbstractExchange
    topology: CommandQueueTopology
    publish_timeout: float

    @classmethod
    async def connect(
        cls,
        url: str,
        topology: CommandQueueTopology,
        *,
        connection_name: str,
        publish_timeout: float = 10.0,
    ) -> Self:
        connection = await aio_pika.connect_robust(url, client_properties={"connection_name": connection_name})
        try:
            # on_return_raises: an unroutable mandatory message raises instead of
            # being returned silently.
            channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
            exchange, _ = await declare_topology(channel, topology)
        except BaseException:
            await connection.close()
            raise
        logger.info(
            "rabbitmq.connected",
            connection_name=connection_name,
            exchange=topology.exchange,
            queue=topology.queue,
        )
        return cls(
            connection=connection,
            publisher_channel=channel,
            exchange=exchange,
            topology=topology,
            publish_timeout=publish_timeout,
        )

    def command_enqueuer(self) -> RabbitMQCommandEnqueuer:
        return RabbitMQCommandEnqueuer(
            exchange=self.exchange,
            routing_key=self.topology.routing_key,
            publish_timeout=self.publish_timeout,
        )

    async def consumer_queue(self, prefetch_count: int) -> AbstractQueue:
        """Open a dedicated consumer channel limited to ``prefetch_count`` unacked messages."""
        channel = await self.connection.channel(publisher_confirms=False)
        await channel.set_qos(prefetch_count=prefetch_count)
        _, queue = await declare_topology(channel, self.topology)
        return queue

    async def close(self) -> None:
        await self.connection.close()
        logger.info("rabbitmq.closed")
