import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from expects import equal, expect
from sqlalchemy.ext.asyncio import create_async_engine

from src.common.database.config import DatabaseConfig
from src.common.presentation.endpoints import health


class FakeRedis:
    def __init__(self, healthy: bool = True):
        self.healthy = healthy

    async def ping(self) -> bool:
        if not self.healthy:
            raise ConnectionError("redis is down")
        return True


def _request(engine: Any, redis_client: FakeRedis) -> Any:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(database_config=SimpleNamespace(engine=engine), redis_client=redis_client)
        )
    )


def _body(response) -> dict:
    return json.loads(bytes(response.body))


@pytest.fixture
def unreachable_engine():
    return create_async_engine("postgresql+asyncpg://postgres:postgres@127.0.0.1:1/unreachable")


async def test_health__answers_ok_without_touching_dependencies():
    response = await health.health()

    expect(response.status_code).to(equal(200))
    expect(_body(response)).to(equal({"status": "ok"}))


async def test_health_ready__is_ok_when_database_and_redis_answer(database_config: DatabaseConfig):
    response = await health.health_ready(_request(database_config.engine, FakeRedis()))  # ty: ignore[invalid-argument-type]

    expect(response.status_code).to(equal(200))
    expect(_body(response)).to(equal({"status": "ok", "checks": {"database": "ok", "redis": "ok"}}))


async def test_health_ready__is_unavailable_when_the_database_is_down(unreachable_engine):
    response = await health.health_ready(_request(unreachable_engine, FakeRedis()))  # ty: ignore[invalid-argument-type]

    expect(response.status_code).to(equal(503))
    expect(_body(response)).to(equal({"status": "unavailable", "checks": {"database": "error", "redis": "ok"}}))


async def test_health_ready__is_unavailable_when_redis_is_down(database_config: DatabaseConfig):
    request = _request(database_config.engine, FakeRedis(healthy=False))

    response = await health.health_ready(request)  # ty: ignore[invalid-argument-type]

    expect(response.status_code).to(equal(503))
    expect(_body(response)["checks"]).to(equal({"database": "ok", "redis": "error"}))


async def test_health__is_served_publicly_by_the_app():
    from config.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/py/health")

    expect(response.status_code).to(equal(200))
    expect(response.json()).to(equal({"status": "ok"}))


def test_health_routes__are_documented_without_parameters_or_security():
    from config.main import app

    paths = app.openapi()["paths"]

    for path in ("/api/py/health", "/api/py/health/ready"):
        operation = paths[path]["get"]
        expect(operation.get("parameters", [])).to(equal([]))
        expect(operation.get("security", [])).to(equal([]))
