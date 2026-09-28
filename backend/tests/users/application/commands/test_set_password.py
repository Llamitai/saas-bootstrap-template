from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from src.common.application.commands.users import SetUserPasswordCommand
from src.common.domain.buses.queries import QueryBus
from src.common.domain.exceptions.users import UserNotFoundError
from src.common.domain.services.token_service import TokenService
from src.users.application.commands.set_password import SetUserPasswordHandler
from src.users.domain.repositories.user import UserRepository


@pytest.fixture
def repository():
    return create_autospec(spec=UserRepository, spec_set=True, instance=True)


@pytest.fixture
def query_bus():
    return create_autospec(spec=QueryBus, spec_set=True, instance=True)


@pytest.fixture
def token_service():
    return create_autospec(spec=TokenService, spec_set=True, instance=True)


@pytest.fixture
def handler(repository, query_bus, token_service) -> SetUserPasswordHandler:
    return SetUserPasswordHandler(repository=repository, query_bus=query_bus, token_service=token_service)


async def test_execute__sets_the_password_and_closes_every_session(handler, repository, query_bus, token_service):
    user_id = uuid4()
    query_bus.ask.return_value = type("FoundUser", (), {"uuid": user_id})()

    await handler.execute(SetUserPasswordCommand(user_id=user_id, password="admin-set-123"))

    repository.set_password.assert_awaited_once_with(user_id=user_id, new_password="admin-set-123")
    token_service.revoke_all_sessions.assert_awaited_once_with(sub=str(user_id), namespace="USER")


async def test_execute__unknown_user_changes_nothing(handler, repository, query_bus, token_service):
    query_bus.ask.return_value = None

    with pytest.raises(UserNotFoundError):
        await handler.execute(SetUserPasswordCommand(user_id=uuid4(), password="admin-set-123"))

    repository.set_password.assert_not_awaited()
    token_service.revoke_all_sessions.assert_not_awaited()
