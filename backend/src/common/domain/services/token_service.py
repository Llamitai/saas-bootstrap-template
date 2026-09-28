from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any

from src.common.domain.entities.common.jtw_session import JwtSession
from src.common.domain.enums.jwt import JwtTokenScope
from src.common.domain.services.token_builder import JwtTokenClaims

# Namespace of the sessions opened by the login flows.
USER_SESSION_NAMESPACE = "USER"


class TokenService(ABC):
    @abstractmethod
    async def generate_token(
        self,
        sub: str,
        namespace: str = "JWT",
        extra_claims: dict[str, Any] | None = None,
    ) -> JwtSession:
        raise NotImplementedError

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> tuple[JwtTokenClaims, JwtSession]:
        raise NotImplementedError

    @abstractmethod
    async def get_claims(self, token: str, scope: JwtTokenScope) -> JwtTokenClaims | None:
        raise NotImplementedError

    @abstractmethod
    async def expire_refresh_token(self, refresh_token: str):
        """Close the session of this refresh token (logout)."""
        raise NotImplementedError

    @abstractmethod
    async def revoke_all_sessions(self, sub: str, namespace: str = USER_SESSION_NAMESPACE):
        """Close every session of the subject (password change or reset)."""
        raise NotImplementedError

    @abstractmethod
    async def create_one_shot_token(
        self,
        sub: str,
        scope: JwtTokenScope,
        ttl: timedelta,
        namespace: str = "JWT",
    ) -> str:
        """Issue a single-purpose, short-lived token (no session pair) that
        `consume_one_shot_token` accepts once. Used for password reset."""
        raise NotImplementedError

    @abstractmethod
    async def consume_one_shot_token(self, token: str, scope: JwtTokenScope) -> JwtTokenClaims | None:
        """The token's claims the first time it is presented, otherwise None."""
        raise NotImplementedError
