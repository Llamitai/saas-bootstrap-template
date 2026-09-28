import hmac
import ipaddress
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from src.common.domain.enums.jwt import JwtTokenScope
from src.common.infrastructure.services.jwt_token_builder import JwtTokenBuilder
from src.common.infrastructure.services.rate_limiter import (
    RateLimiter,
    RateLimitExceededError,
    RateLimitStrategy,
)
from src.common.settings import settings

# Set by the frontend server (proxy/BFF) to the browser's IP. Trusted only on requests
# that also carry the server-only X-Api-Key; otherwise anyone could pick a bucket.
CLIENT_IP_HEADER = "X-Client-IP"

KeyFunc = Callable[[Request], Awaitable[str]]


def client_ip(request: Request) -> str:
    """The rate-limit identity of the caller.

    Server-to-server calls from the frontend share one socket address, so the
    frontend forwards the browser IP in `X-Client-IP`. The header is honoured only
    with a valid X-Api-Key and when it holds a single IP address.
    """
    forwarded = (request.headers.get(CLIENT_IP_HEADER) or "").strip()
    api_key = request.headers.get("x-api-key") or ""
    if forwarded and api_key and hmac.compare_digest(api_key.encode(), settings.ADMIN_API_KEY.encode()):
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


async def ip_key(request: Request) -> str:
    return f"ip:{client_ip(request)}:{request.url.path}"


async def refresh_token_subject_or_ip(request: Request) -> str:
    """Key refreshes by the token subject so users behind one address don't share a bucket.

    Only a validly signed refresh token names a subject; anything else is keyed by IP.
    """
    try:
        body = json.loads(await request.body() or b"{}")
        token = body.get("refresh_token") or body.get("refreshToken") if isinstance(body, dict) else None
    except ValueError:
        token = None
    claims = JwtTokenBuilder().verify_token(token, expected_scope=JwtTokenScope.REFRESH) if token else None
    if claims is None:
        return await ip_key(request)
    return f"sub:{claims.sub}:{request.url.path}"


def get_redis_client(request: Request) -> Redis:
    """Get Redis client from app state"""
    return request.app.state.redis_client


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""

    limit: int  # Maximum requests allowed
    window: int  # Time window in seconds
    strategy: RateLimitStrategy = "fixed_window"
    key_func: KeyFunc | None = None  # Custom key function


def create_rate_limit_dependency(
    limit: int,
    window: int,
    strategy: RateLimitStrategy = "fixed_window",
    key_func: KeyFunc | None = None,
):
    """
    Create a FastAPI dependency for rate limiting.

    Args:
        limit: Maximum number of requests allowed
        window: Time window in seconds
        strategy: Rate limiting strategy ("fixed_window" or "sliding_window")
        key_func: Optional function to generate custom rate limit key from request

    Usage:
        # Rate limit by IP address (10 requests per minute)
        rate_limit_dep = create_rate_limit_dependency(limit=10, window=60)

        router.add_api_route("/endpoint", my_endpoint, methods=["GET"], dependencies=[Depends(rate_limit_dep)])

        # Rate limit by user ID (100 requests per hour)
        async def by_user(request: Request) -> str:
            return f"user:{request.state.user_id}"

        rate_limit_user = create_rate_limit_dependency(
            limit=100,
            window=3600,
            key_func=by_user
        )
    """

    async def rate_limit_dependency(
        request: Request,
        redis_client: Annotated[Redis, Depends(get_redis_client)],
    ) -> None:
        # Generate rate limit key
        key = await (key_func or ip_key)(request)

        # Check rate limit
        rate_limiter = RateLimiter(redis_client=redis_client)

        try:
            _allowed, remaining, _ = await rate_limiter.check_rate_limit(
                key=key, limit=limit, window=window, strategy=strategy
            )

            # Add rate limit headers to response
            request.state.rate_limit_limit = limit
            request.state.rate_limit_remaining = remaining
            request.state.rate_limit_window = window

        except RateLimitExceededError as e:
            # Headers will be added by exception handler
            request.state.rate_limit_limit = e.limit
            request.state.rate_limit_remaining = 0
            request.state.rate_limit_retry_after = e.retry_after
            raise

    return rate_limit_dependency


# Common rate limit presets
RateLimitStrict = create_rate_limit_dependency(limit=10, window=60)  # 10/min
RateLimitModerate = create_rate_limit_dependency(limit=60, window=60)  # 60/min
RateLimitGenerous = create_rate_limit_dependency(limit=100, window=60)  # 100/min
RateLimitPublic = create_rate_limit_dependency(limit=20, window=60)  # 20/min for public endpoints


# Type aliases for easier usage
RateLimitStrictDep = Annotated[None, Depends(RateLimitStrict)]
RateLimitModerateDep = Annotated[None, Depends(RateLimitModerate)]
RateLimitGenerousDep = Annotated[None, Depends(RateLimitGenerous)]
RateLimitPublicDep = Annotated[None, Depends(RateLimitPublic)]
