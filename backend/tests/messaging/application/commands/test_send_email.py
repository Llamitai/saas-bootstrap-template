from unittest.mock import create_autospec

import pytest
from expects import equal, expect

from src.common.application.commands.common import SendEmailCommand
from src.common.settings import settings
from src.messaging.application.commands.send_email import SendEmailHandler
from src.messaging.domain.services.email import EmailService


@pytest.fixture
def email_service():
    return create_autospec(spec=EmailService, spec_set=True, instance=True)


@pytest.fixture
def handler(email_service):
    return SendEmailHandler(email_service=email_service)


async def test_execute__forwards_command_fields_to_email_service(handler, email_service):
    command = SendEmailCommand(
        to_emails=["member@test.com"],
        template_name="welcome",
        context={"name": "Ada"},
        from_email="team@test.com",
        subject="Welcome!",
    )

    await handler.execute(command)

    email_service.send_email.assert_awaited_once_with(
        subject="Welcome!",
        sender="team@test.com",
        recipients=["member@test.com"],
        template_name="welcome",
        context={"name": "Ada"},
    )


async def test_execute__falls_back_to_default_sender(handler, email_service, monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_FROM_EMAIL", "noreply@test.com")
    command = SendEmailCommand(
        to_emails=["member@test.com"],
        template_name="welcome",
        subject="Welcome!",
    )

    await handler.execute(command)

    sender = email_service.send_email.await_args.kwargs["sender"]
    expect(sender).to(equal("noreply@test.com"))


async def test_execute__defaults_missing_context_to_empty_dict(handler, email_service):
    command = SendEmailCommand(
        to_emails=["member@test.com"],
        template_name="welcome",
    )

    await handler.execute(command)

    context = email_service.send_email.await_args.kwargs["context"]
    expect(context).to(equal({}))
