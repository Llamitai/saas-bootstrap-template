import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from aio_pika.abc import AbstractIncomingMessage, AbstractQueue, ConsumerTag

from src.common.application.logging import get_logger
from src.common.domain.entities.common.async_task import AsyncTask

logger = get_logger(__name__)

# Quorum-queue redelivery headers. RabbitMQ 4.x counts every earlier delivery in
# x-acquired-count, while x-delivery-count (checked against x-delivery-limit) only
# grows on "failed" returns such as a consumer crash, not on nack(requeue=True).
ACQUIRED_COUNT_HEADER = "x-acquired-count"
DELIVERY_COUNT_HEADER = "x-delivery-count"
# AsyncTaskResolver reason for a command missing from async_tasks_mapping; retrying
# cannot fix it, so the message goes straight to the dead-letter queue.
PERMANENT_FAILURE_REASONS = frozenset({"NotRegisteredCommand"})
MAX_RETRY_BACKOFF_SECONDS = 30.0

type CommandProcessor = Callable[[dict[str, Any]], Awaitable[AsyncTask]]


def parse_command_payload(body: bytes) -> dict[str, Any] | None:
    """Return the ``MetaCommand.to_dict`` payload, or ``None`` when the body is malformed."""
    try:
        payload = json.loads(body)
    except ValueError:  # includes UnicodeDecodeError and JSONDecodeError
        return None
    if not isinstance(payload, dict) or set(payload) != {"command_name", "payload"}:
        return None
    if not isinstance(payload["command_name"], str) or not isinstance(payload["payload"], dict):
        return None
    return payload


def previous_deliveries(message: AbstractIncomingMessage) -> int:
    headers = message.headers or {}
    counts = [headers.get(ACQUIRED_COUNT_HEADER, 0), headers.get(DELIVERY_COUNT_HEADER, 0)]
    return max((count for count in counts if isinstance(count, int)), default=0)


@dataclass
class CommandConsumer:
    """Consumes deferred commands with manual acknowledgement.

    - success: ack.
    - failure or timeout: nack with requeue after a bounded exponential pause, until
      the ``max_attempts``-th delivery fails; that one is rejected without requeue
      and dead-lettered. The queue's ``x-delivery-limit`` is the broker-side net
      for consumers that crash mid-message.
    - malformed body or unregistered command: reject without requeue (dead letter).

    Concurrency is bounded by the channel prefetch. ``stop`` cancels the consumer
    and waits for in-flight messages before the connection closes.
    """

    queue: AbstractQueue
    process: CommandProcessor
    task_timeout: float
    max_attempts: int
    retry_backoff: float = 1.0
    _consumer_tag: ConsumerTag | None = field(default=None, init=False)
    _in_flight: set[asyncio.Task[Any]] = field(default_factory=set, init=False)

    async def start(self) -> None:
        self._consumer_tag = await self.queue.consume(self.on_message)
        logger.info("rabbitmq.consumer.started", queue=self.queue.name)

    async def stop(self, grace_period: float) -> None:
        if self._consumer_tag is not None:
            await self.queue.cancel(self._consumer_tag)
            self._consumer_tag = None
        pending = {task for task in self._in_flight if not task.done()}
        logger.info("rabbitmq.consumer.stopping", queue=self.queue.name, in_flight=len(pending))
        if pending:
            _, still_running = await asyncio.wait(pending, timeout=grace_period)
            for task in still_running:
                # Unacked messages return to the queue when the channel closes.
                task.cancel()
        logger.info("rabbitmq.consumer.stopped", queue=self.queue.name)

    async def on_message(self, message: AbstractIncomingMessage) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._in_flight.add(task)
        try:
            await self._handle(message)
        finally:
            if task is not None:
                self._in_flight.discard(task)

    async def _handle(self, message: AbstractIncomingMessage) -> None:
        attempt = previous_deliveries(message) + 1
        context = {"message_id": message.message_id, "attempt": attempt}
        payload = parse_command_payload(message.body)
        if payload is None:
            logger.error("rabbitmq.message.malformed", **context)
            await message.reject(requeue=False)
            return

        command = payload["command_name"]
        logger.info("rabbitmq.message.received", command=command, **context)
        try:
            async with asyncio.timeout(self.task_timeout):
                result = await self.process(payload)
        except TimeoutError:
            logger.error("rabbitmq.message.timeout", command=command, timeout=self.task_timeout, **context)
            await self._retry(message, attempt)
            return
        except Exception:
            logger.exception("rabbitmq.message.error", command=command, **context)
            await self._retry(message, attempt)
            return

        if result.is_success:
            await message.ack()
            logger.info("rabbitmq.message.acked", command=command, **context)
        elif result.reason in PERMANENT_FAILURE_REASONS:
            logger.error("rabbitmq.message.dead_lettered", command=command, reason=result.reason, **context)
            await message.reject(requeue=False)
        else:
            logger.warning("rabbitmq.message.failed", command=command, reason=result.reason, **context)
            await self._retry(message, attempt)

    async def _retry(self, message: AbstractIncomingMessage, attempt: int) -> None:
        if attempt >= self.max_attempts:
            logger.error(
                "rabbitmq.message.dead_lettered",
                message_id=message.message_id,
                attempt=attempt,
                reason="max_attempts",
            )
            await message.reject(requeue=False)
            return
        pause = min(self.retry_backoff * 2 ** (attempt - 1), MAX_RETRY_BACKOFF_SECONDS)
        if pause > 0:
            await asyncio.sleep(pause)
        await message.nack(requeue=True)
        logger.info("rabbitmq.message.requeued", message_id=message.message_id, attempt=attempt)
