"""Consume a password-reset token and apply the new password."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.common.domain.enums.jwt import JwtTokenScope
from src.common.domain.exceptions.common import InvalidOrExpiredTokenError
from src.common.domain.interfaces.use_case import UseCase
from src.common.domain.services.token_service import TokenService
from src.common.domain.services.token_store import TokenStore
from src.users.domain.repositories.user import UserRepository


@dataclass
class PasswordResetter(UseCase):
    token: str
    new_password: str
    user_repository: UserRepository
    token_service: TokenService
    token_store: TokenStore

    async def execute(self) -> None:
        claims = await self.token_service.get_claims(
            self.token,
            scope=JwtTokenScope.PASSWORD_RESET,
        )
        if claims is None:
            raise InvalidOrExpiredTokenError

        # Single-use: a token whose jti was already consumed is rejected,
        # even if it has not expired yet.
        if await self.token_store.is_blacklisted(jti=claims.jti, namespace=claims.ns):
            raise InvalidOrExpiredTokenError

        try:
            user_id = UUID(claims.sub)
        except (TypeError, ValueError) as exc:
            raise InvalidOrExpiredTokenError from exc

        ok = await self.user_repository.set_password(
            user_id=user_id,
            new_password=self.new_password,
        )
        if not ok:
            raise InvalidOrExpiredTokenError

        # Burn the token for its remaining lifetime so it cannot be replayed.
        await self.token_store.blacklist_token_jti(
            jti=claims.jti,
            ttl=self._remaining_seconds(claims.exp),
            namespace=claims.ns,
        )

    @staticmethod
    def _remaining_seconds(exp: int) -> int:
        return max(exp - int(datetime.now(UTC).timestamp()), 0)
