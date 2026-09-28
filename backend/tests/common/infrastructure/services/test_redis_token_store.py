"""RedisTokenStore against the real Valkey, including a client without decode_responses."""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from expects import be_false, be_none, be_true, equal, expect
from redis.asyncio import Redis

from src.common.infrastructure.services.redis_token_store import RedisTokenStore
from src.common.settings import settings


@pytest.fixture
async def bytes_client() -> AsyncGenerator[Redis]:
    client = Redis.from_url(settings.redis_url)
    yield client
    await client.aclose()


@pytest.fixture
def store(bytes_client: Redis) -> RedisTokenStore:
    return RedisTokenStore(redis_client=bytes_client)


@pytest.fixture
def namespace() -> str:
    return f"TEST{uuid4().hex[:8]}"


async def test_current_jti__returns_text_even_with_a_bytes_client(store: RedisTokenStore, namespace: str):
    await store.open_session(sub="user-1", sid="sid-1", jti="jti-1", ttl=60, max_sessions=1, namespace=namespace)

    current = await store.current_jti(sub="user-1", sid="sid-1", namespace=namespace)

    expect(current).to(equal("jti-1"))


async def test_rotate_if_current__replaces_only_the_presented_current_jti(store: RedisTokenStore, namespace: str):
    await store.open_session(sub="user-1", sid="sid-1", jti="jti-1", ttl=60, max_sessions=1, namespace=namespace)

    rotated = await store.rotate_if_current(
        sub="user-1", sid="sid-1", current_jti="jti-1", new_jti="jti-2", ttl=60, namespace=namespace
    )
    stale = await store.rotate_if_current(
        sub="user-1", sid="sid-1", current_jti="jti-1", new_jti="jti-3", ttl=60, namespace=namespace
    )

    expect(rotated).to(be_true)
    expect(stale).to(be_false)
    expect(await store.current_jti(sub="user-1", sid="sid-1", namespace=namespace)).to(equal("jti-2"))


async def test_rotate_if_current__does_not_recreate_a_lost_session_index(
    store: RedisTokenStore, bytes_client: Redis, namespace: str
):
    await store.open_session(sub="user-1", sid="sid-1", jti="jti-1", ttl=60, max_sessions=1, namespace=namespace)
    await bytes_client.delete(f"{namespace}_SESS:user-1")

    rotated = await store.rotate_if_current(
        sub="user-1", sid="sid-1", current_jti="jti-1", new_jti="jti-2", ttl=60, namespace=namespace
    )

    expect(rotated).to(be_false)
    expect(await bytes_client.exists(f"{namespace}_SESS:user-1")).to(equal(0))


async def test_open_session__drops_index_members_whose_session_key_is_gone(
    store: RedisTokenStore, bytes_client: Redis, namespace: str
):
    await store.open_session(sub="user-1", sid="sid-1", jti="jti-1", ttl=60, max_sessions=2, namespace=namespace)
    await store.open_session(sub="user-1", sid="sid-2", jti="jti-2", ttl=60, max_sessions=2, namespace=namespace)
    await bytes_client.delete(f"{namespace}_RT:user-1:sid-1")

    await store.open_session(sub="user-1", sid="sid-3", jti="jti-3", ttl=60, max_sessions=2, namespace=namespace)

    expect(await store.current_jti(sub="user-1", sid="sid-2", namespace=namespace)).to(equal("jti-2"))
    expect(await store.current_jti(sub="user-1", sid="sid-3", namespace=namespace)).to(equal("jti-3"))
    expect(await bytes_client.zcard(f"{namespace}_SESS:user-1")).to(equal(2))


async def test_close_all_sessions__removes_every_session_key_and_the_index(
    store: RedisTokenStore, bytes_client: Redis, namespace: str
):
    await store.open_session(sub="user-1", sid="sid-1", jti="jti-1", ttl=60, max_sessions=2, namespace=namespace)
    await store.open_session(sub="user-1", sid="sid-2", jti="jti-2", ttl=60, max_sessions=2, namespace=namespace)

    await store.close_all_sessions(sub="user-1", namespace=namespace)

    expect(await store.current_jti(sub="user-1", sid="sid-1", namespace=namespace)).to(be_none)
    expect(await bytes_client.exists(f"{namespace}_RT:user-1:sid-2", f"{namespace}_SESS:user-1")).to(equal(0))


async def test_consume_one_shot__succeeds_once(store: RedisTokenStore, namespace: str):
    await store.allow_one_shot(jti="jti-1", ttl=60, namespace=namespace)

    first = await store.consume_one_shot(jti="jti-1", namespace=namespace)
    second = await store.consume_one_shot(jti="jti-1", namespace=namespace)

    expect(first).to(be_true)
    expect(second).to(be_false)
