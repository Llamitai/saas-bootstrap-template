from expects import equal, expect

from src.common.domain.enums.common import Environment
from src.common.infrastructure.redis_client import create_redis_client
from src.common.settings import Settings


async def test_create_redis_client__applies_the_pool_settings():
    pool_settings = Settings(
        _env_file=None,
        ENVIRONMENT=Environment.testing,
        REDIS_MAX_CONNECTIONS=7,
        REDIS_SOCKET_TIMEOUT=1.5,
        REDIS_SOCKET_CONNECT_TIMEOUT=2.5,
        REDIS_HEALTH_CHECK_INTERVAL=11,
    )

    client = create_redis_client(pool_settings)

    pool = client.connection_pool
    expect(pool.max_connections).to(equal(7))
    expect(
        {
            key: pool.connection_kwargs[key]
            for key in ("socket_timeout", "socket_connect_timeout", "health_check_interval", "decode_responses")
        }
    ).to(
        equal(
            {
                "socket_timeout": 1.5,
                "socket_connect_timeout": 2.5,
                "health_check_interval": 11,
                "decode_responses": True,
            }
        )
    )
    await client.aclose()
