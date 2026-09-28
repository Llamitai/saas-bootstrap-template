from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from src.common.application.commands.users import UpdateUserPasswordCommand
from src.common.domain.exceptions.auth import InvalidCredentialsError
from src.common.domain.services.token_service import TokenService
from src.users.application.commands.update_password import UpdateUserPasswordHandler
from src.users.domain.repositories.user import UserRepository


@pytest.fixture
def user_repository():
    return create_autospec(spec=UserRepository, spec_set=True, instance=True)


@pytest.fixture
def token_service():
    return create_autospec(spec=TokenService, spec_set=True, instance=True)


@pytest.fixture
def handler(user_repository, token_service) -> UpdateUserPasswordHandler:
    return UpdateUserPasswordHandler(user_repository=user_repository, token_service=token_service)


def _command(user_id) -> UpdateUserPasswordCommand:
    return UpdateUserPasswordCommand(user_id=user_id, current_password="old-secret", new_password="new-secret-123")


async def test_execute__sets_the_new_password_and_closes_every_session(handler, user_repository, token_service):
    user_id = uuid4()
    user_repository.check_password.return_value = True

    await handler.execute(_command(user_id))

    user_repository.set_password.assert_awaited_once_with(user_id=user_id, new_password="new-secret-123")
    token_service.revoke_all_sessions.assert_awaited_once_with(sub=str(user_id), namespace="USER")


async def test_execute__wrong_current_password_keeps_password_and_sessions(handler, user_repository, token_service):
    user_repository.check_password.return_value = False

    with pytest.raises(InvalidCredentialsError):
        await handler.execute(_command(uuid4()))

    user_repository.set_password.assert_not_awaited()
    token_service.revoke_all_sessions.assert_not_awaited()
