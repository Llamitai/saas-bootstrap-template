from dataclasses import dataclass

from src.common.application.commands.users import UpdateUserPasswordCommand
from src.common.domain.buses.commands import CommandHandler
from src.common.domain.exceptions.auth import InvalidCredentialsError
from src.common.domain.services.token_service import USER_SESSION_NAMESPACE, TokenService
from src.users.domain.repositories.user import UserRepository


@dataclass
class UpdateUserPasswordHandler(CommandHandler[UpdateUserPasswordCommand]):
    user_repository: UserRepository
    token_service: TokenService

    async def execute(self, command: UpdateUserPasswordCommand):
        if not await self.user_repository.check_password(
            user_id=command.user_id,
            raw_password=command.current_password,
        ):
            raise InvalidCredentialsError

        await self.user_repository.set_password(
            user_id=command.user_id,
            new_password=command.new_password,
        )
        # A new password closes every session, including the caller's own.
        await self.token_service.revoke_all_sessions(sub=str(command.user_id), namespace=USER_SESSION_NAMESPACE)
