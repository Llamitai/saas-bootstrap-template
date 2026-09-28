"""Valkey allowlist of refresh-token sessions.

Keys (`ns` is the token namespace):
- `{ns}_RT:{sub}:{sid}`: current refresh jti of one session, TTL = refresh lifetime.
- `{ns}_SESS:{sub}`: sorted set of the subject's session ids scored by last use.
- `{ns}_ROT:{jti}`: rotation grace claim/payload, TTL = grace window.
- `{ns}_OST:{jti}`: allowance of a single-use token, TTL = token lifetime.

A session is valid only while its key holds the presented jti AND its id is in the
index, so losing either key (eviction, restart without AOF) only rejects tokens.
Scripts touch every key of one subject, so they assume a single Valkey node.
"""

import time
from dataclasses import dataclass, field

from redis.asyncio import Redis
from redis.commands.core import AsyncScript

from src.common.domain.services.token_store import ROTATION_PENDING, TokenStore

# KEYS: index. ARGV: session key prefix, sid, jti, ttl, now, max sessions.
_OPEN_SESSION = """
local index, prefix = KEYS[1], ARGV[1]
for _, member in ipairs(redis.call('ZRANGE', index, 0, -1)) do
  if redis.call('EXISTS', prefix .. member) == 0 then
    redis.call('ZREM', index, member)
  end
end
redis.call('SET', prefix .. ARGV[2], ARGV[3], 'EX', ARGV[4])
redis.call('ZADD', index, ARGV[5], ARGV[2])
while redis.call('ZCARD', index) > tonumber(ARGV[6]) do
  local oldest = redis.call('ZPOPMIN', index)
  redis.call('DEL', prefix .. oldest[1])
end
redis.call('EXPIRE', index, ARGV[4])
return 1
"""

# KEYS: session key, index. ARGV: sid.
_CURRENT_JTI = """
if not redis.call('ZSCORE', KEYS[2], ARGV[1]) then
  return false
end
return redis.call('GET', KEYS[1])
"""

# KEYS: session key, index. ARGV: sid, current jti, new jti, ttl, now.
# Never recreates a lost index: a session missing from it stays closed.
_ROTATE_IF_CURRENT = """
if not redis.call('ZSCORE', KEYS[2], ARGV[1]) or redis.call('GET', KEYS[1]) ~= ARGV[2] then
  return 0
end
redis.call('SET', KEYS[1], ARGV[3], 'EX', ARGV[4])
redis.call('ZADD', KEYS[2], ARGV[5], ARGV[1])
redis.call('EXPIRE', KEYS[2], ARGV[4])
return 1
"""

# KEYS: index. ARGV: session key prefix.
_CLOSE_ALL_SESSIONS = """
for _, member in ipairs(redis.call('ZRANGE', KEYS[1], 0, -1)) do
  redis.call('DEL', ARGV[1] .. member)
end
redis.call('DEL', KEYS[1])
return 1
"""


def _text(value: str | bytes | None) -> str | None:
    # The value type depends on the client's decode_responses; normalize it so it
    # compares with the `jti` claim instead of "b'...'".
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


@dataclass
class RedisTokenStore(TokenStore):
    redis_client: Redis
    _open_session: AsyncScript = field(init=False, repr=False)
    _current_jti: AsyncScript = field(init=False, repr=False)
    _rotate_if_current: AsyncScript = field(init=False, repr=False)
    _close_all_sessions: AsyncScript = field(init=False, repr=False)

    def __post_init__(self):
        self._open_session = self.redis_client.register_script(_OPEN_SESSION)
        self._current_jti = self.redis_client.register_script(_CURRENT_JTI)
        self._rotate_if_current = self.redis_client.register_script(_ROTATE_IF_CURRENT)
        self._close_all_sessions = self.redis_client.register_script(_CLOSE_ALL_SESSIONS)

    @staticmethod
    def _index(sub: str, namespace: str) -> str:
        return f"{namespace}_SESS:{sub}"

    @staticmethod
    def _session_prefix(sub: str, namespace: str) -> str:
        return f"{namespace}_RT:{sub}:"

    async def open_session(self, sub: str, sid: str, jti: str, ttl: int, max_sessions: int, namespace: str):
        await self._open_session(
            keys=[self._index(sub, namespace)],
            args=[self._session_prefix(sub, namespace), sid, jti, ttl, time.time(), max_sessions],
        )

    async def current_jti(self, sub: str, sid: str, namespace: str) -> str | None:
        value = await self._current_jti(
            keys=[self._session_prefix(sub, namespace) + sid, self._index(sub, namespace)],
            args=[sid],
        )
        return _text(value)

    async def rotate_if_current(
        self, sub: str, sid: str, current_jti: str, new_jti: str, ttl: int, namespace: str
    ) -> bool:
        rotated = await self._rotate_if_current(
            keys=[self._session_prefix(sub, namespace) + sid, self._index(sub, namespace)],
            args=[sid, current_jti, new_jti, ttl, time.time()],
        )
        return rotated == 1

    async def close_session(self, sub: str, sid: str, namespace: str):
        async with self.redis_client.pipeline(transaction=True) as pipe:
            pipe.delete(self._session_prefix(sub, namespace) + sid)
            pipe.zrem(self._index(sub, namespace), sid)
            await pipe.execute()

    async def close_all_sessions(self, sub: str, namespace: str):
        await self._close_all_sessions(
            keys=[self._index(sub, namespace)],
            args=[self._session_prefix(sub, namespace)],
        )

    async def claim_rotation(self, jti: str, ttl: int, namespace: str) -> bool:
        return bool(await self.redis_client.set(f"{namespace}_ROT:{jti}", ROTATION_PENDING, ex=ttl, nx=True))

    async def publish_rotation(self, jti: str, payload: str, ttl: int, namespace: str):
        await self.redis_client.set(f"{namespace}_ROT:{jti}", payload, ex=ttl)

    async def get_rotation(self, jti: str, namespace: str) -> str | None:
        return _text(await self.redis_client.get(f"{namespace}_ROT:{jti}"))

    async def release_rotation(self, jti: str, namespace: str):
        await self.redis_client.delete(f"{namespace}_ROT:{jti}")

    async def allow_one_shot(self, jti: str, ttl: int, namespace: str):
        await self.redis_client.set(f"{namespace}_OST:{jti}", 1, ex=ttl)

    async def consume_one_shot(self, jti: str, namespace: str) -> bool:
        return await self.redis_client.delete(f"{namespace}_OST:{jti}") == 1
