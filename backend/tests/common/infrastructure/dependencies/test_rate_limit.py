from collections.abc import AsyncGenerator
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from expects import equal, expect
from fastapi import Depends, FastAPI
from redis.asyncio import Redis

from src.common.domain.enums.jwt import JwtTokenScope
from src.common.infrastructure.dependencies.rate_limit import (
    CLIENT_IP_HEADER,
    client_ip,
    create_rate_limit_dependency,
    refresh_token_subject_or_ip,
)
from src.common.infrastructure.handlers.rate_limit_handler import rate_limit_exception_handler
from src.common.infrastructure.services.jwt_token_builder import JwtTokenBuilder
from src.common.infrastructure.services.rate_limiter import RateLimitExceededError
from src.common.settings import settings


def _request(headers: dict[str, str], body: bytes = b"", host: str = "10.0.0.5"):
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/auth/refresh",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (host, 1234),
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def test_client_ip__trusts_the_forwarded_ip_only_with_the_server_api_key():
    trusted = _request({"x-api-key": settings.ADMIN_API_KEY, CLIENT_IP_HEADER: "203.0.113.7"})
    spoofed = _request({"x-api-key": "wrong", CLIENT_IP_HEADER: "203.0.113.7"})
    anonymous = _request({CLIENT_IP_HEADER: "203.0.113.7"})

    expect(client_ip(trusted)).to(equal("203.0.113.7"))
    expect(client_ip(spoofed)).to(equal("10.0.0.5"))
    expect(client_ip(anonymous)).to(equal("10.0.0.5"))


def test_client_ip__ignores_a_forwarded_value_that_is_not_an_ip():
    request = _request({"x-api-key": settings.ADMIN_API_KEY, CLIENT_IP_HEADER: "1.2.3.4, 5.6.7.8"})

    expect(client_ip(request)).to(equal("10.0.0.5"))


async def test_refresh_key__uses_the_subject_of_a_valid_refresh_token():
    token = JwtTokenBuilder().create_token(sub="user-42", scope=JwtTokenScope.REFRESH, exp_delta=timedelta(minutes=5))
    request = _request({}, body=f'{{"refresh_token": "{token}"}}'.encode())

    expect(await refresh_token_subject_or_ip(request)).to(equal("sub:user-42:/v1/auth/refresh"))


async def test_refresh_key__falls_back_to_the_client_ip_for_invalid_tokens():
    request = _request({}, body=b'{"refresh_token": "forged"}')

    expect(await refresh_token_subject_or_ip(request)).to(equal("ip:10.0.0.5:/v1/auth/refresh"))


@pytest.fixture
async def limited_app() -> AsyncGenerator[FastAPI]:
    app = FastAPI()
    app.state.redis_client = Redis.from_url(settings.redis_url, decode_responses=True, encoding="utf-8")
    limit = create_rate_limit_dependency(limit=1, window=60)

    async def endpoint() -> dict:
        return {}

    app.add_api_route(f"/limited-{uuid4().hex}", endpoint, methods=["GET"], dependencies=[Depends(limit)])
    app.add_exception_handler(RateLimitExceededError, rate_limit_exception_handler)  # ty: ignore[invalid-argument-type]
    yield app
    await app.state.redis_client.aclose()


async def test_rate_limit__gives_each_forwarded_client_its_own_bucket(limited_app: FastAPI):
    path = limited_app.routes[-1].path  # ty: ignore[unresolved-attribute]

    def headers(ip: str) -> dict[str, str]:
        return {"X-Api-Key": settings.ADMIN_API_KEY, CLIENT_IP_HEADER: ip}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=limited_app), base_url="http://test") as client:
        first = await client.get(path, headers=headers("203.0.113.1"))
        other_client = await client.get(path, headers=headers("203.0.113.2"))
        same_client = await client.get(path, headers=headers("203.0.113.1"))

    expect([first.status_code, other_client.status_code, same_client.status_code]).to(equal([200, 200, 429]))
