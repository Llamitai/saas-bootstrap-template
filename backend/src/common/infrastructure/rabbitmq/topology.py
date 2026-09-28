from dataclasses import dataclass
from typing import Self

from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue
from pamqp.common import FieldTable

from src.common.settings import Settings


@dataclass(frozen=True)
class CommandQueueTopology:
    """Names and limits of the deferred-command topology.

    ``exchange`` (durable, direct) routes to ``queue`` (quorum) by the queue name.
    A message nacked more than ``delivery_limit`` times, or rejected without requeue,
    is dead-lettered through ``<exchange>.dlx`` into ``<queue>.dlq``.
    """

    exchange: str
    queue: str
    delivery_limit: int

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            exchange=settings.RABBITMQ_EXCHANGE,
            queue=settings.RABBITMQ_QUEUE,
            delivery_limit=settings.RABBITMQ_DELIVERY_LIMIT,
        )

    @property
    def routing_key(self) -> str:
        return self.queue

    @property
    def dead_letter_exchange(self) -> str:
        return f"{self.exchange}.dlx"

    @property
    def dead_letter_queue(self) -> str:
        return f"{self.queue}.dlq"

    @property
    def queue_arguments(self) -> FieldTable:
        return {
            "x-queue-type": "quorum",
            "x-delivery-limit": self.delivery_limit,
            "x-dead-letter-exchange": self.dead_letter_exchange,
            "x-dead-letter-routing-key": self.dead_letter_queue,
            # at-least-once dead-lettering keeps the message in the source queue until
            # the DLQ confirms it; RabbitMQ requires reject-publish overflow for it.
            "x-dead-letter-strategy": "at-least-once",
            "x-overflow": "reject-publish",
        }


async def declare_topology(
    channel: AbstractChannel, topology: CommandQueueTopology
) -> tuple[AbstractExchange, AbstractQueue]:
    """Idempotently declare exchanges, queues and bindings; returns the command exchange and queue.

    Re-declaring with different arguments fails with PRECONDITION_FAILED: change
    limits on an existing queue through a RabbitMQ policy or recreate the queue.
    """
    dead_letter_exchange = await channel.declare_exchange(
        topology.dead_letter_exchange, ExchangeType.DIRECT, durable=True
    )
    dead_letter_queue = await channel.declare_queue(
        topology.dead_letter_queue, durable=True, arguments={"x-queue-type": "quorum"}
    )
    await dead_letter_queue.bind(dead_letter_exchange, routing_key=topology.dead_letter_queue)

    exchange = await channel.declare_exchange(topology.exchange, ExchangeType.DIRECT, durable=True)
    queue = await channel.declare_queue(topology.queue, durable=True, arguments=topology.queue_arguments)
    await queue.bind(exchange, routing_key=topology.routing_key)
    return exchange, queue
