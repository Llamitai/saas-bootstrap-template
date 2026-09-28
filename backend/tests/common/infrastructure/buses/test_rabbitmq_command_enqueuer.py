import json
from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from aio_pika import DeliveryMode
from aio_pika.abc import AbstractExchange
from aio_pika.exceptions import DeliveryError, PublishError
from aiormq.abc import DeliveredMessage
from expects import be_a, be_none, equal, expect
from pamqp.commands import Basic
from pamqp.header import ContentHeader

from src.common.application.commands.tenants import SoftDeleteTenantCommand
from src.common.infrastructure.buses.rabbitmq_command_enqueuer import CommandEnqueueError, RabbitMQCommandEnqueuer

NO_ROUTE = Basic.Return(reply_code=312, reply_text="NO_ROUTE", exchange="commands", routing_key="commands.default")
RETURNED = DeliveredMessage(delivery=NO_ROUTE, header=ContentHeader(), body=b"", channel=None)  # ty: ignore[invalid-argument-type]


@pytest.fixture
def exchange() -> AbstractExchange:
    exchange = create_autospec(spec=AbstractExchange, spec_set=True, instance=True)
    exchange.publish.return_value = Basic.Ack(delivery_tag=1)
    return exchange


@pytest.fixture
def enqueuer(exchange: AbstractExchange) -> RabbitMQCommandEnqueuer:
    return RabbitMQCommandEnqueuer(exchange=exchange, routing_key="commands.default", publish_timeout=3.0)


async def test_enqueue__publishes_a_persistent_confirmed_json_message(
    enqueuer: RabbitMQCommandEnqueuer, exchange: AbstractExchange
):
    tenant_id = uuid4()

    await enqueuer.enqueue(SoftDeleteTenantCommand(tenant_id=tenant_id))

    exchange.publish.assert_awaited_once()  # ty: ignore[unresolved-attribute]
    call = exchange.publish.await_args  # ty: ignore[unresolved-attribute]
    message = call.args[0]
    expect(call.kwargs).to(equal({"routing_key": "commands.default", "mandatory": True, "timeout": 3.0}))
    expect(json.loads(message.body)).to(
        equal({"command_name": "SoftDeleteTenantCommand", "payload": {"tenant_id": str(tenant_id)}})
    )
    expect(message.delivery_mode).to(equal(DeliveryMode.PERSISTENT))
    expect(message.content_type).to(equal("application/json"))
    expect(message.headers).to(equal({"x-command": "SoftDeleteTenantCommand"}))
    expect(message.message_id).to(be_a(str))
    expect(message.timestamp).not_to(be_none)


async def test_enqueue__uses_a_new_message_id_per_command(
    enqueuer: RabbitMQCommandEnqueuer, exchange: AbstractExchange
):
    await enqueuer.enqueue(SoftDeleteTenantCommand(tenant_id=uuid4()))
    await enqueuer.enqueue(SoftDeleteTenantCommand(tenant_id=uuid4()))

    ids = {call.args[0].message_id for call in exchange.publish.await_args_list}  # ty: ignore[unresolved-attribute]
    expect(len(ids)).to(equal(2))


@pytest.mark.parametrize(
    "error",
    [DeliveryError(None, Basic.Nack(delivery_tag=1)), PublishError(RETURNED, NO_ROUTE), TimeoutError()],
    ids=["nack", "unroutable", "confirm-timeout"],
)
async def test_enqueue__raises_when_the_broker_does_not_confirm(
    enqueuer: RabbitMQCommandEnqueuer, exchange: AbstractExchange, error: Exception
):
    exchange.publish.side_effect = error  # ty: ignore[unresolved-attribute]

    with pytest.raises(CommandEnqueueError):
        await enqueuer.enqueue(SoftDeleteTenantCommand(tenant_id=uuid4()))


async def test_enqueue__raises_when_the_confirmation_is_not_an_ack(
    enqueuer: RabbitMQCommandEnqueuer, exchange: AbstractExchange
):
    exchange.publish.return_value = None  # ty: ignore[unresolved-attribute]

    with pytest.raises(CommandEnqueueError):
        await enqueuer.enqueue(SoftDeleteTenantCommand(tenant_id=uuid4()))
