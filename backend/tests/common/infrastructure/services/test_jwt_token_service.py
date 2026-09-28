"""JwtTokenService against the real Valkey used by the API (lifespan client settings)."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from uuid import uuid4

import pytest
from expects import be_none, equal, expect
from redis.asyncio import Redis

from src.common.domain.entities.common.jtw_session import JwtSession
from src.common.domain.enums.jwt import JwtTokenScope
from src.common.domain.exceptions.common import InvalidOrExpiredRefreshTokenError
from src.common.domain.services.token_builder import JwtTokenClaims
from src.common.infrastructure.redis_client import create_redis_client
from src.common.infrastructure.services.jwt_token_builder import JwtTokenBuilder
from src.common.infrastructure.services.jwt_token_service import JwtTokenService
from src.common.infrastructure.services.redis_token_store import RedisTokenStore
from src.common.settings import settings


@pytest.fixture
async def redis_client() -> AsyncGenerator[Redis]:
    client = create_redis_client(settings)
    yield client
    await client.aclose()


@pytest.fixture
def token_service(redis_client: Redis) -> JwtTokenService:
    return JwtTokenService(token_store=RedisTokenStore(redis_client=redis_client), token_builder=JwtTokenBuilder())


@pytest.fixture
def namespace() -> str:
    return f"TEST{uuid4().hex[:8]}"


@pytest.fixture
def max_sessions(monkeypatch: pytest.MonkeyPatch):
    def set_max_sessions(value: int) -> None:
        monkeypatch.setattr(settings, "JWT_MAX_SESSIONS_PER_USER", value)

    set_max_sessions(1)
    return set_max_sessions


async def _refresh_claims(token_service: JwtTokenService, session: JwtSession) -> JwtTokenClaims:
    claims = await token_service.get_claims(session.refresh_token, scope=JwtTokenScope.REFRESH)
    if claims is None:
        pytest.fail("the issued refresh token does not verify")
    return claims


async def _expect_rejected(token_service: JwtTokenService, refresh_token: str) -> None:
    with pytest.raises(InvalidOrExpiredRefreshTokenError):
        await token_service.refresh_token(refresh_token)


# -> Rotation


async def test_refresh_token__without_grace_rejects_the_rotated_token_and_accepts_the_new_one(
    token_service: JwtTokenService, namespace: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "JWT_REFRESH_GRACE_SECONDS", 0)
    issued = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)
    _, rotated = await token_service.refresh_token(issued.refresh_token)

    await _expect_rejected(token_service, issued.refresh_token)
    claims, _ = await token_service.refresh_token(rotated.refresh_token)
    expect(claims.ns).to(equal(namespace))


async def test_refresh_token__rotation_keeps_the_session_id_in_both_tokens(
    token_service: JwtTokenService, namespace: str
):
    issued = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)
    issued_claims = await _refresh_claims(token_service, issued)

    _, rotated = await token_service.refresh_token(issued.refresh_token)

    rotated_claims = await _refresh_claims(token_service, rotated)
    access_claims = await token_service.get_claims(rotated.access_token, scope=JwtTokenScope.ACCESS)
    expect(issued_claims.sid).not_to(be_none)
    expect(rotated_claims.sid).to(equal(issued_claims.sid))
    expect(access_claims and access_claims.sid).to(equal(issued_claims.sid))


async def test_refresh_token__rejects_reuse_after_the_grace_window(
    token_service: JwtTokenService, namespace: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "JWT_REFRESH_GRACE_SECONDS", 1)
    issued = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)
    await token_service.refresh_token(issued.refresh_token)

    await asyncio.sleep(1.2)

    await _expect_rejected(token_service, issued.refresh_token)


async def test_refresh_token__concurrent_rotations_share_one_pair(token_service: JwtTokenService, namespace: str):
    issued = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)

    results = await asyncio.gather(*(token_service.refresh_token(issued.refresh_token) for _ in range(3)))

    sessions = {session.refresh_token for _, session in results}
    expect(len(sessions)).to(equal(1))
    claims, _ = await token_service.refresh_token(sessions.pop())
    expect(claims.ns).to(equal(namespace))


async def test_refresh_token__concurrent_rotations_without_grace_let_only_one_win(
    token_service: JwtTokenService, namespace: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "JWT_REFRESH_GRACE_SECONDS", 0)
    issued = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)

    results = await asyncio.gather(
        *(token_service.refresh_token(issued.refresh_token) for _ in range(3)), return_exceptions=True
    )

    winners = [result for result in results if not isinstance(result, BaseException)]
    expect(len(winners)).to(equal(1))


async def test_refresh_token__a_late_duplicate_within_grace_gets_the_same_pair(
    token_service: JwtTokenService, namespace: str
):
    issued = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)
    first_claims, first = await token_service.refresh_token(issued.refresh_token)

    second_claims, second = await token_service.refresh_token(issued.refresh_token)

    expect(second).to(equal(first))
    expect(second_claims).to(equal(first_claims))


async def test_refresh_token__rejects_a_refresh_token_without_session_id(
    token_service: JwtTokenService, namespace: str
):
    legacy = JwtTokenBuilder().create_token(
        sub=str(uuid4()),
        scope=JwtTokenScope.REFRESH,
        exp_delta=timedelta(minutes=5),
        namespace=namespace,
    )

    await _expect_rejected(token_service, legacy)


# -> Sessions per user


async def test_generate_token__with_one_session_per_user_a_new_login_closes_the_previous(
    token_service: JwtTokenService, namespace: str, max_sessions
):
    sub = str(uuid4())
    first = await token_service.generate_token(sub=sub, namespace=namespace)

    second = await token_service.generate_token(sub=sub, namespace=namespace)

    await _expect_rejected(token_service, first.refresh_token)
    await token_service.refresh_token(second.refresh_token)


async def test_generate_token__with_two_sessions_the_third_login_closes_the_least_recently_used(
    token_service: JwtTokenService, namespace: str, max_sessions
):
    max_sessions(2)
    sub = str(uuid4())
    first = await token_service.generate_token(sub=sub, namespace=namespace)
    second = await token_service.generate_token(sub=sub, namespace=namespace)
    await asyncio.sleep(0.01)
    _, first_rotated = await token_service.refresh_token(first.refresh_token)

    third = await token_service.generate_token(sub=sub, namespace=namespace)

    await _expect_rejected(token_service, second.refresh_token)
    await token_service.refresh_token(first_rotated.refresh_token)
    await token_service.refresh_token(third.refresh_token)


# -> Revocation


async def test_expire_refresh_token__closes_only_its_session(
    token_service: JwtTokenService, namespace: str, max_sessions
):
    max_sessions(2)
    sub = str(uuid4())
    closed = await token_service.generate_token(sub=sub, namespace=namespace)
    kept = await token_service.generate_token(sub=sub, namespace=namespace)

    await token_service.expire_refresh_token(closed.refresh_token)

    await _expect_rejected(token_service, closed.refresh_token)
    await token_service.refresh_token(kept.refresh_token)


async def test_revoke_all_sessions__closes_every_session_of_the_subject(
    token_service: JwtTokenService, namespace: str, max_sessions
):
    max_sessions(2)
    sub = str(uuid4())
    first = await token_service.generate_token(sub=sub, namespace=namespace)
    second = await token_service.generate_token(sub=sub, namespace=namespace)
    other = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)

    await token_service.revoke_all_sessions(sub=sub, namespace=namespace)

    await _expect_rejected(token_service, first.refresh_token)
    await _expect_rejected(token_service, second.refresh_token)
    await token_service.refresh_token(other.refresh_token)


async def test_refresh_token__grace_cannot_resurrect_a_logged_out_session(
    token_service: JwtTokenService, namespace: str
):
    issued = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)
    _, rotated = await token_service.refresh_token(issued.refresh_token)

    await token_service.expire_refresh_token(rotated.refresh_token)

    await _expect_rejected(token_service, issued.refresh_token)


async def test_refresh_token__grace_cannot_resurrect_a_session_evicted_by_a_new_login(
    token_service: JwtTokenService, namespace: str, max_sessions
):
    sub = str(uuid4())
    issued = await token_service.generate_token(sub=sub, namespace=namespace)
    await token_service.refresh_token(issued.refresh_token)

    await token_service.generate_token(sub=sub, namespace=namespace)

    await _expect_rejected(token_service, issued.refresh_token)


async def test_refresh_token__grace_cannot_resurrect_sessions_revoked_for_the_account(
    token_service: JwtTokenService, namespace: str
):
    sub = str(uuid4())
    issued = await token_service.generate_token(sub=sub, namespace=namespace)
    await token_service.refresh_token(issued.refresh_token)

    await token_service.revoke_all_sessions(sub=sub, namespace=namespace)

    await _expect_rejected(token_service, issued.refresh_token)


# -> Fail-closed store


async def test_refresh_token__a_lost_session_index_only_rejects(
    token_service: JwtTokenService, redis_client: Redis, namespace: str
):
    issued = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)
    claims = await _refresh_claims(token_service, issued)

    await redis_client.delete(f"{namespace}_SESS:{claims.sub}")

    await _expect_rejected(token_service, issued.refresh_token)


async def test_refresh_token__a_lost_session_key_only_rejects(
    token_service: JwtTokenService, redis_client: Redis, namespace: str
):
    issued = await token_service.generate_token(sub=str(uuid4()), namespace=namespace)
    claims = await _refresh_claims(token_service, issued)

    await redis_client.delete(f"{namespace}_RT:{claims.sub}:{claims.sid}")

    await _expect_rejected(token_service, issued.refresh_token)


async def test_revoke_all_sessions__a_lost_index_still_rejects_every_session(
    token_service: JwtTokenService, redis_client: Redis, namespace: str, max_sessions
):
    max_sessions(2)
    sub = str(uuid4())
    first = await token_service.generate_token(sub=sub, namespace=namespace)
    second = await token_service.generate_token(sub=sub, namespace=namespace)
    await redis_client.delete(f"{namespace}_SESS:{sub}")

    await token_service.revoke_all_sessions(sub=sub, namespace=namespace)

    await _expect_rejected(token_service, first.refresh_token)
    await _expect_rejected(token_service, second.refresh_token)


# -> One-shot tokens


async def test_consume_one_shot_token__accepts_a_token_only_once(token_service: JwtTokenService, namespace: str):
    sub = str(uuid4())
    token = await token_service.create_one_shot_token(
        sub=sub, scope=JwtTokenScope.PASSWORD_RESET, ttl=timedelta(minutes=5), namespace=namespace
    )

    claims = await token_service.consume_one_shot_token(token, scope=JwtTokenScope.PASSWORD_RESET)
    replayed = await token_service.consume_one_shot_token(token, scope=JwtTokenScope.PASSWORD_RESET)

    expect(claims and claims.sub).to(equal(sub))
    expect(replayed).to(be_none)


async def test_consume_one_shot_token__rejects_a_token_whose_store_entry_is_gone(
    token_service: JwtTokenService, redis_client: Redis, namespace: str
):
    token = await token_service.create_one_shot_token(
        sub=str(uuid4()), scope=JwtTokenScope.PASSWORD_RESET, ttl=timedelta(minutes=5), namespace=namespace
    )
    claims = await token_service.get_claims(token, scope=JwtTokenScope.PASSWORD_RESET)
    if claims is None:
        pytest.fail("the issued one-shot token does not verify")
    await redis_client.delete(f"{namespace}_OST:{claims.jti}")

    consumed = await token_service.consume_one_shot_token(token, scope=JwtTokenScope.PASSWORD_RESET)

    expect(consumed).to(be_none)


async def test_consume_one_shot_token__rejects_a_token_of_another_scope(
    token_service: JwtTokenService, namespace: str
):
    token = await token_service.create_one_shot_token(
        sub=str(uuid4()), scope=JwtTokenScope.PASSWORD_RESET, ttl=timedelta(minutes=5), namespace=namespace
    )

    consumed = await token_service.consume_one_shot_token(token, scope=JwtTokenScope.ACCESS)

    expect(consumed).to(be_none)
