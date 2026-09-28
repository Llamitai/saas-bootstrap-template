from redis.asyncio import Redis

from src.common.settings import Settings


def create_redis_client(settings: Settings) -> Redis:
    """Process-wide Valkey/Redis client with a bounded, health-checked pool.

    ``decode_responses=True`` is required: token-store keys expect ``str``.
    """
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        encoding="utf-8",
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        socket_keepalive=True,
        health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL,
    )
