"""AC-04: the OpenAPI schema documents the wire format without changing it."""

import re
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY
from uuid import uuid4

import httpx
import pytest
from expects import be_empty, equal, expect
from fastapi import FastAPI

from config.main import app
from src.common.domain.models.email_address import EmailAddress
from src.common.domain.models.user import User
from src.common.infrastructure.dependencies.common import get_domain_context
from src.common.infrastructure.responses.api_json import ApiJSONResponse
from src.common.presentation.schemas.envelopes import Envelope, StatusResponse
from src.users.presentation import router as users_router
from src.users.presentation.endpoints import users as users_endpoint

OPERATION_ID = re.compile(r"^[a-z]+-[a-z_]+$")


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return app.openapi()


def _operations(spec: dict[str, Any]):
    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            yield f"{method.upper()} {path}", operation


def _resolve(spec: dict[str, Any], schema: dict[str, Any], seen: set[str]):
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        if name not in seen:
            seen.add(name)
            yield from _properties(spec, spec["components"]["schemas"][name], seen)
    for key in ("anyOf", "allOf", "oneOf"):
        for option in schema.get(key, []):
            yield from _resolve(spec, option, seen)
    if "items" in schema:
        yield from _resolve(spec, schema["items"], seen)


def _properties(spec: dict[str, Any], schema: dict[str, Any], seen: set[str]):
    for name, prop in schema.get("properties", {}).items():
        yield name
        yield from _resolve(spec, prop, seen)
    yield from _resolve(spec, {k: v for k, v in schema.items() if k != "properties"}, seen)


def test_openapi__every_operation_documents_a_successful_json_body(spec: dict[str, Any]):
    undocumented = [
        name
        for name, operation in _operations(spec)
        if not any(
            code.startswith("2") and response.get("content", {}).get("application/json", {}).get("schema")
            for code, response in operation["responses"].items()
        )
    ]

    expect(undocumented).to(be_empty)


def test_openapi__json_request_bodies_use_camel_case(spec: dict[str, Any]):
    snake = [
        f"{name}: {prop}"
        for name, operation in _operations(spec)
        for prop in _resolve(
            spec,
            operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}),
            set(),
        )
        if "_" in prop
    ]

    expect(snake).to(be_empty)


def test_openapi__envelopes_use_camel_case(spec: dict[str, Any]):
    snake = [
        f"{name}.{prop}"
        for name, schema in spec["components"]["schemas"].items()
        if not name.startswith(("Body_", "HTTPValidationError", "ValidationError"))
        for prop in schema.get("properties", {})
        if "_" in prop
    ]

    expect(snake).to(be_empty)


def test_openapi__operation_ids_are_readable_and_unique(spec: dict[str, Any]):
    operation_ids = [operation["operationId"] for _, operation in _operations(spec)]

    expect([op for op in operation_ids if not OPERATION_ID.match(op)]).to(be_empty)
    expect(len(set(operation_ids))).to(equal(len(operation_ids)))
    expect(spec["paths"]["/v1/auth/login"]["post"]["operationId"]).to(equal("auth-login"))


def test_openapi__update_password_accepts_no_query_parameters(spec: dict[str, Any]):
    expect(spec["paths"]["/v1/me/password"]["put"].get("parameters", [])).to(be_empty)


def test_openapi__documents_the_actual_success_status(spec: dict[str, Any]):
    expect(next(iter(spec["paths"]["/v1/users"]["post"]["responses"]))).to(equal("201"))
    expect(next(iter(spec["paths"]["/v1/tenants/{tenant_id}"]["delete"]["responses"]))).to(equal("202"))


async def test_register_user__wire_body_is_not_filtered_by_the_response_model(monkeypatch: pytest.MonkeyPatch):
    user = User(
        uuid=uuid4(),
        username="ada",
        email_address=EmailAddress(uuid=uuid4(), email="ada@example.com"),
    )

    class FixedRegisterer:
        def __init__(self, **_: Any):
            pass

        async def execute(self) -> User:
            return user

    monkeypatch.setattr(users_endpoint, "UserRegisterer", FixedRegisterer)
    app.dependency_overrides[users_router.register_rate_limit] = lambda: None
    app.dependency_overrides[get_domain_context] = lambda: SimpleNamespace(user_repository=object())
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/v1/users", json={"email": "ada@example.com", "password": "pass1234567"})
    finally:
        app.dependency_overrides.clear()

    expect(response.status_code).to(equal(201))
    expect(response.json()).to(
        equal(
            {
                "data": {
                    "uuid": str(user.uuid),
                    "username": "ada",
                    "firstName": None,
                    "lastName": None,
                    "emailAddress": {
                        "uuid": str(user.email_address.uuid),
                        "email": "ada@example.com",
                        "isVerified": False,
                    },
                },
                "timestamp": ANY,
            }
        )
    )


async def test_response_model__documents_without_rewriting_an_api_json_response():
    probe = FastAPI()

    async def endpoint() -> ApiJSONResponse:
        return ApiJSONResponse(content={"status": "OK", "undocumented_key": 1})

    probe.add_api_route("/probe", endpoint, methods=["GET"], response_model=Envelope[StatusResponse])

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=probe), base_url="http://test") as client:
        body = (await client.get("/probe")).json()

    expect(body["data"]).to(equal({"status": "OK", "undocumentedKey": 1}))
    expect(datetime.fromisoformat(body["timestamp"]).tzinfo).to(equal(UTC))
