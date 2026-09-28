import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, create_autospec

import pytest
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue
from expects import be_none, equal, expect

from src.common.domain.entities.common.async_task import AsyncTask
from src.common.infrastructure.rabbitmq.consumer import CommandConsumer, parse_command_payload

VALID_PAYLOAD = {"command_name": "SoftDeleteTenantCommand", "payload": {"tenant_id": "t-1"}}


MAX_ATTEMPTS = 3


def incoming(body: bytes, headers: dict[str, Any] | None = None) -> AbstractIncomingMessage:
    message = create_autospec(spec=AbstractIncomingMessage, instance=True)
    message.body = body
    message.message_id = "m-1"
    message.headers = headers or {}
    return message


def consumer_for(process: AsyncMock, task_timeout: float = 5.0) -> CommandConsumer:
    queue = create_autospec(spec=AbstractQueue, instance=True)
    queue.name = "commands.default"
    return CommandConsumer(
        queue=queue, process=process, task_timeout=task_timeout, max_attempts=MAX_ATTEMPTS, retry_backoff=0
    )


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"\xff\xfe",
        b"[]",
        b'{"command_name": "X"}',
        b'{"command_name": 1, "payload": {}}',
        b'{"command_name": "X", "payload": []}',
        b'{"command_name": "X", "payload": {}, "extra": 1}',
    ],
)
def test_parse_command_payload__rejects_malformed_bodies(body: bytes):
    expect(parse_command_payload(body)).to(be_none)


def test_parse_command_payload__returns_the_meta_command_dict():
    expect(parse_command_payload(json.dumps(VALID_PAYLOAD).encode())).to(equal(VALID_PAYLOAD))


async def test_on_message__acks_after_a_successful_command():
    process = AsyncMock(return_value=AsyncTask(operation="SoftDeleteTenantCommand", is_success=True))
    message = incoming(json.dumps(VALID_PAYLOAD).encode())

    await consumer_for(process).on_message(message)

    process.assert_awaited_once_with(VALID_PAYLOAD)
    message.ack.assert_awaited_once_with()  # ty: ignore[unresolved-attribute]
    message.nack.assert_not_awaited()  # ty: ignore[unresolved-attribute]


async def test_on_message__rejects_malformed_payload_without_requeue():
    process = AsyncMock()
    message = incoming(b"not json")

    await consumer_for(process).on_message(message)

    process.assert_not_awaited()
    message.reject.assert_awaited_once_with(requeue=False)  # ty: ignore[unresolved-attribute]


async def test_on_message__dead_letters_an_unregistered_command():
    process = AsyncMock(return_value=AsyncTask(operation="Unknown", is_success=False, reason="NotRegisteredCommand"))
    message = incoming(json.dumps(VALID_PAYLOAD).encode())

    await consumer_for(process).on_message(message)

    message.reject.assert_awaited_once_with(requeue=False)  # ty: ignore[unresolved-attribute]
    message.ack.assert_not_awaited()  # ty: ignore[unresolved-attribute]


@pytest.mark.parametrize(
    "outcome",
    [AsyncTask(operation="SoftDeleteTenantCommand", is_success=False), RuntimeError("boom")],
    ids=["failed-task", "exception"],
)
async def test_on_message__requeues_a_failed_command(outcome: Any):
    process = AsyncMock(side_effect=[outcome])
    message = incoming(json.dumps(VALID_PAYLOAD).encode(), headers={"x-acquired-count": MAX_ATTEMPTS - 2})

    await consumer_for(process).on_message(message)

    message.nack.assert_awaited_once_with(requeue=True)  # ty: ignore[unresolved-attribute]
    message.ack.assert_not_awaited()  # ty: ignore[unresolved-attribute]


@pytest.mark.parametrize(
    "headers",
    [{"x-acquired-count": MAX_ATTEMPTS - 1}, {"x-delivery-count": MAX_ATTEMPTS - 1}],
    ids=["acquired-count", "delivery-count"],
)
async def test_on_message__dead_letters_the_last_failed_attempt(headers: dict[str, Any]):
    process = AsyncMock(side_effect=RuntimeError("boom"))
    message = incoming(json.dumps(VALID_PAYLOAD).encode(), headers=headers)

    await consumer_for(process).on_message(message)

    message.reject.assert_awaited_once_with(requeue=False)  # ty: ignore[unresolved-attribute]
    message.nack.assert_not_awaited()  # ty: ignore[unresolved-attribute]


async def test_on_message__requeues_a_command_that_exceeds_the_timeout():
    async def slow(_: dict[str, Any]) -> AsyncTask:
        await asyncio.sleep(1)
        return AsyncTask(operation="SoftDeleteTenantCommand", is_success=True)

    message = incoming(json.dumps(VALID_PAYLOAD).encode())

    await consumer_for(AsyncMock(side_effect=slow), task_timeout=0.01).on_message(message)

    message.nack.assert_awaited_once_with(requeue=True)  # ty: ignore[unresolved-attribute]
    message.ack.assert_not_awaited()  # ty: ignore[unresolved-attribute]


async def test_stop__cancels_the_consumer_and_waits_for_in_flight_messages():
    finished = asyncio.Event()

    async def slow(_: dict[str, Any]) -> AsyncTask:
        await asyncio.sleep(0.05)
        finished.set()
        return AsyncTask(operation="SoftDeleteTenantCommand", is_success=True)

    consumer = consumer_for(AsyncMock(side_effect=slow))
    consumer.queue.consume.return_value = "ctag"  # ty: ignore[unresolved-attribute]
    message = incoming(json.dumps(VALID_PAYLOAD).encode())
    await consumer.start()
    in_flight = asyncio.create_task(consumer.on_message(message))
    await asyncio.sleep(0)

    await consumer.stop(grace_period=5)

    consumer.queue.cancel.assert_awaited_once_with("ctag")  # ty: ignore[unresolved-attribute]
    expect(finished.is_set()).to(equal(True))
    message.ack.assert_awaited_once_with()  # ty: ignore[unresolved-attribute]
    await in_flight
