import os
from collections.abc import Generator
from dataclasses import dataclass

import pytest
import requests
from redis import Redis
from requests import Response

from src.common.application.logging import get_logger
from src.common.domain.constants.status import HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from src.common.settings import settings

logger = get_logger()

BASE_URL = os.environ.get("E2E_BASE_URL", "http://api:8200")
USER_EMAIL = "user@test.com"
USER_PASSWORD = "pass1234567890"
TENANT_NAME = "tenant-test"
RATE_LIMIT_KEY_PATTERN = "rate_limit:*"
USER_ALREADY_EXISTS_CODE = "users.UserAlreadyExist"


@pytest.fixture(scope="session")
def api_key_header() -> dict:
    """Provides the admin API key header, fetching from env var or using a default test key."""
    admin_api_key = os.environ.get("ADMIN_API_KEY", "test-super-secret-key")
    return {"x-api-key": admin_api_key}


def _clear_rate_limit_keys() -> None:
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True, encoding="utf-8")
    try:
        keys = list(redis_client.scan_iter(match=RATE_LIMIT_KEY_PATTERN))
        if keys:
            redis_client.delete(*keys)
    finally:
        redis_client.close()


@pytest.fixture(scope="session", autouse=True)
def clean_api_rate_limits() -> Generator[None]:
    _clear_rate_limit_keys()

    yield

    _clear_rate_limit_keys()


@dataclass
class LoginTestContext:
    access_token: str
    refresh_token: str
    tenant_slug: str | None = None
    tenant_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "LoginTestContext":
        tenant = data.get("tenant") or {}

        return cls(
            access_token=data["session"]["accessToken"],
            refresh_token=data["session"]["refreshToken"],
            tenant_slug=tenant.get("slug", None),
            tenant_id=tenant.get("uuid", None),
        )


def _login_user() -> Response:
    return requests.post(
        url=f"{BASE_URL}/v1/auth/login/",
        json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD,
        },
        timeout=30,
    )


def _response_error_codes(response: Response) -> set[str]:
    try:
        body = response.json()
    except ValueError:
        return set()

    if not isinstance(body, dict):
        return set()

    errors = body.get("errors")
    if not isinstance(errors, list):
        return set()

    return {error["code"] for error in errors if isinstance(error, dict) and isinstance(error.get("code"), str)}


@pytest.fixture(scope="session")
def new_registered_user(api_key_header: dict) -> bool:
    response = requests.post(
        url=f"{BASE_URL}/v1/users",
        json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD,
        },
        headers=api_key_header,
        timeout=30,
    )
    if response.status_code == HTTP_201_CREATED:
        logger.info("New user registered", email=USER_EMAIL)
        return True

    if response.status_code == HTTP_400_BAD_REQUEST and USER_ALREADY_EXISTS_CODE in _response_error_codes(response):
        logger.info("User already exists", email=USER_EMAIL)
        return False

    logger.error("User registration failed", status_code=response.status_code, response_text=response.text)
    pytest.fail(f"User registration failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="session")
def new_registered_tenant(new_registered_user, api_key_header: dict):
    _ = new_registered_user
    response = _login_user()
    if response.status_code != HTTP_201_CREATED:
        logger.error("Login failed", status_code=response.status_code, response_text=response.text)
        pytest.fail(f"Login failed: {response.status_code} - {response.text}")

    login_user = LoginTestContext.from_dict(response.json()["data"])

    headers = {
        "Authorization": f"Bearer {login_user.access_token}",
    }
    headers.update(api_key_header)
    tenant_response = requests.post(
        url=f"{BASE_URL}/v1/tenants",
        json={
            "name": TENANT_NAME,
            "countryCode": "BO",
        },
        headers=headers,
        timeout=30,
    )
    if tenant_response.status_code != HTTP_201_CREATED:
        logger.warning("Tenant creation status", status_code=tenant_response.status_code)
    logger.info("New Tenant registered", tenant_name=TENANT_NAME)


@pytest.fixture(scope="session")
def login_user(new_registered_user, new_registered_tenant) -> LoginTestContext:
    _ = (new_registered_user, new_registered_tenant)
    response = _login_user()
    assert response.status_code == HTTP_201_CREATED
    return LoginTestContext.from_dict(response.json()["data"])
