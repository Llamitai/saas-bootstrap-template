import json
from dataclasses import dataclass
from uuid import uuid4

from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractExchange
from pamqp.commands import Basic

from src.common.application.helpers.datetimes import utc_now
from src.common.application.logging import get_logger
from src.common.domain.buses.async_commands import CommandEnqueuer
from src.common.domain.buses.commands import Command
from src.common.domain.buses.meta_command import MetaCommand

logger = get_logger(__name__)

COMMAND_HEADER = "x-command"


class CommandEnqueueError(RuntimeError):
    """The broker did not confirm the command (nack, unroutable or timeout)."""


@dataclass
class RabbitMQCommandEnqueuer(CommandEnqueuer):
    """Publishes deferred commands to RabbitMQ with publisher confirms.

    ``exchange`` belongs to the process-wide confirm channel opened by
    :class:`~src.common.infrastructure.rabbitmq.broker.RabbitMQBroker`; the
    enqueuer never opens connections. ``enqueue`` returns only after the broker
    confirmed the persistent message was routed to the durable queue.
    """

    exchange: AbstractExchange
    routing_key: str
    publish_timeout: float = 10.0

    async def enqueue(self, command: Command) -> None:
        meta_command = MetaCommand.from_command(command)
        message = Message(
            body=json.dumps(meta_command.to_dict).encode(),
            content_type="application/json",
            content_encoding="utf-8",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=uuid4().hex,
            timestamp=utc_now(),
            type=meta_command.command_name,
            headers={COMMAND_HEADER: meta_command.command_name},
        )
        try:
            confirmation = await self.exchange.publish(
                message,
                routing_key=self.routing_key,
                mandatory=True,
                timeout=self.publish_timeout,
            )
        except Exception as error:
            logger.error(
                "rabbitmq.command.enqueue_error",
                command=meta_command.command_name,
                message_id=message.message_id,
                error=str(error),
                error_type=error.__class__.__name__,
            )
            msg = f"Failed to enqueue command {meta_command.command_name}"
            raise CommandEnqueueError(msg) from error

        if not isinstance(confirmation, Basic.Ack):
            # A returned (unroutable) message or a channel without confirms.
            logger.error(
                "rabbitmq.command.enqueue_unconfirmed",
                command=meta_command.command_name,
                message_id=message.message_id,
                confirmation=type(confirmation).__name__,
            )
            msg = f"Broker did not confirm command {meta_command.command_name}"
            raise CommandEnqueueError(msg)

        logger.info(
            "rabbitmq.command.enqueued",
            command=meta_command.command_name,
            message_id=message.message_id,
            routing_key=self.routing_key,
        )
