import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from uuid6 import uuid7

from src.common.application.logging import get_logger
from src.common.domain.entities.common.jtw_session import JwtSession
from src.common.domain.enums.jwt import JwtTokenScope
from src.common.domain.exceptions.common import InvalidOrExpiredRefreshTokenError
from src.common.domain.services.token_builder import JwtTokenClaims, TokenBuilder
from src.common.domain.services.token_service import USER_SESSION_NAMESPACE, TokenService
from src.common.domain.services.token_store import ROTATION_PENDING, TokenStore
from src.common.settings import settings

logger = get_logger(__name__)

# How long a duplicate refresh waits for the rotation another caller is issuing.
ROTATION_WAIT_SECONDS = 0.05
ROTATION_WAIT_ATTEMPTS = 100


@dataclass
class JwtTokenService(TokenService):
    """Stateless access tokens; refresh tokens valid only while their session allows them.

    Each login opens a session (`sid` claim in both tokens) whose current refresh jti
    lives in the token store. Refresh, logout and revocation act on that allowlist;
    access tokens are verified by signature alone.
    """

    token_store: TokenStore
    token_builder: TokenBuilder

    async def generate_token(
        self,
        sub: str,
        namespace: str = "JWT",
        extra_claims: dict[str, Any] | None = None,
    ) -> JwtSession:
        sid = uuid7().hex
        refresh_token_jti = uuid7().hex
        session = self._issue_pair(
            sub=sub,
            sid=sid,
            refresh_token_jti=refresh_token_jti,
            namespace=namespace,
            extra_claims=extra_claims,
        )
        await self.token_store.open_session(
            sub=sub,
            sid=sid,
            jti=refresh_token_jti,
            ttl=self._refresh_ttl(),
            max_sessions=settings.JWT_MAX_SESSIONS_PER_USER,
            namespace=namespace,
        )
        return session

    async def refresh_token(self, refresh_token: str) -> tuple[JwtTokenClaims, JwtSession]:
        """Rotate the session's current refresh token; duplicates within the grace window get the same pair.

        Concurrent callers (the frontend proxy and a route handler, or several
        instances) may present the same token. The first claims the rotation and
        publishes the pair it issued under the presented jti for
        `JWT_REFRESH_GRACE_SECONDS`; the others wait for and return that pair while
        the session still holds it. Any other token of the session, or a token of a
        closed or lost session, is rejected.
        """
        claims = self.token_builder.verify_token(
            token=refresh_token,
            expected_scope=JwtTokenScope.REFRESH,
        )
        if not claims:
            raise InvalidOrExpiredRefreshTokenError
        if not claims.sid:
            logger.warning("jwt.refresh.missing_session", jti=claims.jti, sub=claims.sub, namespace=claims.ns)
            raise InvalidOrExpiredRefreshTokenError

        current = await self.token_store.current_jti(sub=claims.sub, sid=claims.sid, namespace=claims.ns)
        if current != claims.jti:
            return claims, await self._shared_rotation(claims)

        grace = settings.JWT_REFRESH_GRACE_SECONDS
        if grace <= 0:
            return claims, await self._rotate(claims)
        if not await self.token_store.claim_rotation(jti=claims.jti, ttl=grace, namespace=claims.ns):
            return claims, await self._shared_rotation(claims)

        try:
            session = await self._rotate(claims)
        except BaseException:
            await self.token_store.release_rotation(jti=claims.jti, namespace=claims.ns)
            raise
        await self.token_store.publish_rotation(
            jti=claims.jti,
            payload=session.model_dump_json(),
            ttl=grace,
            namespace=claims.ns,
        )
        return claims, session

    async def _shared_rotation(self, claims: JwtTokenClaims) -> JwtSession:
        payload = await self.token_store.get_rotation(jti=claims.jti, namespace=claims.ns)
        for _ in range(ROTATION_WAIT_ATTEMPTS):
            if payload != ROTATION_PENDING:
                break
            await asyncio.sleep(ROTATION_WAIT_SECONDS)
            payload = await self.token_store.get_rotation(jti=claims.jti, namespace=claims.ns)

        if payload is None or payload == ROTATION_PENDING:
            logger.warning("jwt.refresh.not_current", jti=claims.jti, sub=claims.sub, namespace=claims.ns)
            raise InvalidOrExpiredRefreshTokenError

        session = JwtSession.model_validate_json(payload)
        issued = self.token_builder.verify_token(token=session.refresh_token, expected_scope=JwtTokenScope.REFRESH)
        # The shared pair is valid only while it is still the session's current one;
        # a closed, evicted or since-rotated session never gets it back.
        if issued is None or issued.sid is None:
            raise InvalidOrExpiredRefreshTokenError
        current = await self.token_store.current_jti(sub=issued.sub, sid=issued.sid, namespace=issued.ns)
        if current != issued.jti:
            raise InvalidOrExpiredRefreshTokenError
        return session

    async def _rotate(self, claims: JwtTokenClaims) -> JwtSession:
        if claims.sid is None:
            raise InvalidOrExpiredRefreshTokenError
        refresh_token_jti = uuid7().hex
        # The rotated pair keeps the session id and namespace of the presented token.
        session = self._issue_pair(
            sub=claims.sub,
            sid=claims.sid,
            refresh_token_jti=refresh_token_jti,
            namespace=claims.ns,
        )
        rotated = await self.token_store.rotate_if_current(
            sub=claims.sub,
            sid=claims.sid,
            current_jti=claims.jti,
            new_jti=refresh_token_jti,
            ttl=self._refresh_ttl(),
            namespace=claims.ns,
        )
        if not rotated:
            # Another caller rotated first, or the session was closed meanwhile.
            raise InvalidOrExpiredRefreshTokenError
        return session

    def _issue_pair(
        self,
        sub: str,
        sid: str,
        refresh_token_jti: str,
        namespace: str,
        extra_claims: dict[str, Any] | None = None,
    ) -> JwtSession:
        access_token = self.token_builder.create_token(
            jti=uuid7().hex,
            sub=sub,
            scope=JwtTokenScope.ACCESS,
            exp_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            namespace=namespace,
            extra_claims={**(extra_claims or {}), "sid": sid},
        )
        refresh_token = self.token_builder.create_token(
            jti=refresh_token_jti,
            sub=sub,
            scope=JwtTokenScope.REFRESH,
            exp_delta=timedelta(minutes=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES),
            namespace=namespace,
            extra_claims={"sid": sid},
        )
        return JwtSession(access_token=access_token, refresh_token=refresh_token)

    async def get_claims(self, token: str, scope: JwtTokenScope) -> JwtTokenClaims | None:
        return self.token_builder.verify_token(
            token=token,
            expected_scope=scope,
        )

    async def create_one_shot_token(
        self,
        sub: str,
        scope: JwtTokenScope,
        ttl: timedelta,
        namespace: str = "JWT",
    ) -> str:
        jti = uuid7().hex
        token = self.token_builder.create_token(
            jti=jti,
            sub=sub,
            scope=scope,
            exp_delta=ttl,
            namespace=namespace,
        )
        await self.token_store.allow_one_shot(jti=jti, ttl=int(ttl.total_seconds()), namespace=namespace)
        return token

    async def consume_one_shot_token(self, token: str, scope: JwtTokenScope) -> JwtTokenClaims | None:
        claims = self.token_builder.verify_token(token=token, expected_scope=scope)
        if claims is None:
            return None
        if not await self.token_store.consume_one_shot(jti=claims.jti, namespace=claims.ns):
            return None
        return claims

    async def expire_refresh_token(self, refresh_token: str):
        jwt_claims = await self.get_claims(refresh_token, scope=JwtTokenScope.REFRESH)
        assert jwt_claims is not None  # un token inválido ya explotaba aquí (AttributeError)
        if jwt_claims.sid is None:
            # A token without a session id is never accepted, so there is nothing to close.
            return
        await self.token_store.close_session(sub=jwt_claims.sub, sid=jwt_claims.sid, namespace=jwt_claims.ns)

    async def revoke_all_sessions(self, sub: str, namespace: str = USER_SESSION_NAMESPACE):
        await self.token_store.close_all_sessions(sub=sub, namespace=namespace)

    @staticmethod
    def _refresh_ttl() -> int:
        return settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES * 60
