"""Delivery semantics against a real RabbitMQ (RABBITMQ_* settings; CI and the test stack provide one)."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import pytest
from aio_pika import Message
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue
from aio_pika.exceptions import ChannelPreconditionFailed
from expects import equal, expect

from src.common.application.commands.tenants import SoftDeleteTenantCommand
from src.common.domain.entities.common.async_task import AsyncTask
from src.common.infrastructure.buses.rabbitmq_command_enqueuer import CommandEnqueueError, RabbitMQCommandEnqueuer
from src.common.infrastructure.rabbitmq.broker import RabbitMQBroker
from src.common.infrastructure.rabbitmq.consumer import CommandConsumer
from src.common.infrastructure.rabbitmq.topology import CommandQueueTopology, declare_topology
from src.common.settings import settings

pytestmark = pytest.mark.rabbitmq

DELIVERY_LIMIT = 2
WAIT_SECONDS = 15


@pytest.fixture
async def broker() -> AsyncGenerator[RabbitMQBroker]:
    name = f"test.{uuid4().hex[:12]}"
    topology = CommandQueueTopology(exchange=name, queue=f"{name}.commands", delivery_limit=DELIVERY_LIMIT)
    broker = await RabbitMQBroker.connect(settings.rabbitmq_url, topology, connection_name="pytest")
    yield broker
    channel = await broker.connection.channel()
    await channel.queue_delete(topology.queue)
    await channel.queue_delete(topology.dead_letter_queue)
    await channel.exchange_delete(topology.exchange)
    await channel.exchange_delete(topology.dead_letter_exchange)
    await broker.close()


class Recorder:
    def __init__(self, outcome: AsyncTask | Exception) -> None:
        self.outcome = outcome
        self.payloads: list[dict[str, Any]] = []
        self.called = asyncio.Event()

    async def __call__(self, payload: dict[str, Any]) -> AsyncTask:
        self.payloads.append(payload)
        self.called.set()
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


async def start_consumer(broker: RabbitMQBroker, recorder: Recorder) -> CommandConsumer:
    queue = await broker.consumer_queue(prefetch_count=10)
    consumer = CommandConsumer(
        queue=queue, process=recorder, task_timeout=5, max_attempts=DELIVERY_LIMIT, retry_backoff=0
    )
    await consumer.start()
    return consumer


async def message_count(broker: RabbitMQBroker, queue_name: str) -> int:
    channel = await broker.connection.channel()
    try:
        queue = await channel.declare_queue(queue_name, passive=True)
        return queue.declaration_result.message_count or 0
    finally:
        await channel.close()


async def next_message(queue: AbstractQueue, *, no_ack: bool) -> AbstractIncomingMessage:
    async with asyncio.timeout(WAIT_SECONDS):
        while True:
            message = await queue.get(no_ack=no_ack, fail=False)
            if message is not None:
                return message
            await asyncio.sleep(0.1)


async def wait_for_dead_letter(broker: RabbitMQBroker) -> AbstractIncomingMessage:
    channel = await broker.connection.channel()
    queue = await channel.declare_queue(broker.topology.dead_letter_queue, passive=True)
    return await next_message(queue, no_ack=True)


async def test_enqueued_command__is_consumed_and_acknowledged(broker: RabbitMQBroker):
    recorder = Recorder(AsyncTask(operation="SoftDeleteTenantCommand", is_success=True))
    consumer = await start_consumer(broker, recorder)
    tenant_id = str(uuid4())

    await broker.command_enqueuer().enqueue(SoftDeleteTenantCommand.from_dict({"tenant_id": tenant_id}))
    async with asyncio.timeout(WAIT_SECONDS):
        await recorder.called.wait()
    await consumer.stop(grace_period=5)
    await consumer.queue.channel.close()

    expect(recorder.payloads).to(
        equal([{"command_name": "SoftDeleteTenantCommand", "payload": {"tenant_id": tenant_id}}])
    )
    expect(await message_count(broker, broker.topology.queue)).to(equal(0))
    expect(await message_count(broker, broker.topology.dead_letter_queue)).to(equal(0))


async def test_failing_command__is_retried_up_to_the_delivery_limit_then_dead_lettered(broker: RabbitMQBroker):
    recorder = Recorder(RuntimeError("handler failed"))
    consumer = await start_consumer(broker, recorder)

    await broker.command_enqueuer().enqueue(SoftDeleteTenantCommand(tenant_id=uuid4()))
    dead_letter = await wait_for_dead_letter(broker)
    await consumer.stop(grace_period=5)

    expect(len(recorder.payloads)).to(equal(DELIVERY_LIMIT))
    expect(json.loads(dead_letter.body)["command_name"]).to(equal("SoftDeleteTenantCommand"))
    expect(dead_letter.headers["x-first-death-reason"]).to(equal("rejected"))
    expect(await message_count(broker, broker.topology.queue)).to(equal(0))


async def test_malformed_payload__goes_straight_to_the_dead_letter_queue(broker: RabbitMQBroker):
    recorder = Recorder(AsyncTask(operation="unused", is_success=True))
    consumer = await start_consumer(broker, recorder)

    await broker.exchange.publish(Message(body=b"{not json"), routing_key=broker.topology.routing_key)
    dead_letter = await wait_for_dead_letter(broker)
    await consumer.stop(grace_period=5)

    expect(recorder.payloads).to(equal([]))
    expect(dead_letter.body).to(equal(b"{not json"))
    expect(dead_letter.headers["x-first-death-reason"]).to(equal("rejected"))


async def test_unroutable_command__raises_instead_of_being_dropped(broker: RabbitMQBroker):
    enqueuer = RabbitMQCommandEnqueuer(exchange=broker.exchange, routing_key="no.such.queue")

    with pytest.raises(CommandEnqueueError):
        await enqueuer.enqueue(SoftDeleteTenantCommand(tenant_id=uuid4()))


async def test_topology__declaration_is_idempotent(broker: RabbitMQBroker):
    channel = await broker.connection.channel()

    exchange, queue = await declare_topology(channel, broker.topology)

    expect(exchange.name).to(equal(broker.topology.exchange))
    expect(queue.name).to(equal(broker.topology.queue))
    await channel.close()


async def test_topology__server_holds_the_quorum_and_dead_letter_arguments(broker: RabbitMQBroker):
    channel = await broker.connection.channel()
    changed = {**broker.topology.queue_arguments, "x-delivery-limit": DELIVERY_LIMIT + 1}

    # A mismatching re-declaration proves the broker stored the declared arguments.
    with pytest.raises(ChannelPreconditionFailed):
        await channel.declare_queue(broker.topology.queue, durable=True, arguments=changed)


async def test_consumer_crash__counts_as_a_failed_delivery_for_the_broker_limit(broker: RabbitMQBroker):
    await broker.command_enqueuer().enqueue(SoftDeleteTenantCommand(tenant_id=uuid4()))

    # Each consumer takes the message and closes its channel without acking.
    for _ in range(DELIVERY_LIMIT + 1):
        channel = await broker.connection.channel()
        queue = await channel.declare_queue(broker.topology.queue, passive=True)
        await next_message(queue, no_ack=False)
        await channel.close()
    dead_letter = await wait_for_dead_letter(broker)

    expect(dead_letter.headers["x-first-death-reason"]).to(equal("delivery_limit"))
