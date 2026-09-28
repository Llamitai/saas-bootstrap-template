import pytest
import requests
from expects import equal, expect, have_key

from src.common.domain.constants.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED
from tests.api.conftest import BASE_URL, USER_EMAIL, USER_PASSWORD, LoginTestContext

pytestmark = [pytest.mark.api]


def _fresh_refresh_token() -> str:
    # Each login rotates the user's session, so a token from an earlier test may be revoked.
    response = requests.post(
        url=f"{BASE_URL}/v1/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        timeout=30,
    )
    return response.json()["data"]["session"]["refreshToken"]


def _refresh(refresh_token: str) -> requests.Response:
    return requests.post(url=f"{BASE_URL}/v1/auth/refresh", json={"refreshToken": refresh_token}, timeout=30)


def test_refresh__returns_new_tokens(login_user: LoginTestContext):
    _ = login_user
    response = _refresh(_fresh_refresh_token())

    expect(response.status_code).to(equal(HTTP_200_OK))
    data = response.json()["data"]
    expect(data).to(have_key("session"))
    expect(data["session"]).to(have_key("accessToken"))
    expect(data["session"]).to(have_key("refreshToken"))


def test_refresh__invalid_token_returns_401():
    response = requests.post(
        url=f"{BASE_URL}/v1/auth/refresh",
        json={"refreshToken": "invalid.token.here"},
        timeout=30,
    )

    expect(response.status_code).to(equal(HTTP_401_UNAUTHORIZED))


def test_refresh__empty_token_returns_401():
    response = requests.post(
        url=f"{BASE_URL}/v1/auth/refresh",
        json={"refreshToken": ""},
        timeout=30,
    )

    expect(response.status_code).to(equal(HTTP_401_UNAUTHORIZED))


def test_refresh__a_duplicate_within_the_grace_window_returns_the_same_pair(login_user: LoginTestContext):
    _ = login_user
    refresh_token = _fresh_refresh_token()
    first = _refresh(refresh_token)

    second = _refresh(refresh_token)

    expect(second.status_code).to(equal(HTTP_200_OK))
    expect(second.json()["data"]["session"]).to(equal(first.json()["data"]["session"]))


def test_refresh__a_rotated_token_is_rejected_after_logout(login_user: LoginTestContext):
    _ = login_user
    refresh_token = _fresh_refresh_token()
    rotated = _refresh(refresh_token).json()["data"]["session"]["refreshToken"]
    requests.post(url=f"{BASE_URL}/v1/auth/logout", json={"refreshToken": rotated}, timeout=30)

    response = _refresh(refresh_token)

    expect(response.status_code).to(equal(HTTP_401_UNAUTHORIZED))


def test_refresh__a_new_login_closes_the_previous_session(login_user: LoginTestContext):
    # One session per user by default (JWT_MAX_SESSIONS_PER_USER=1).
    _ = login_user
    previous = _fresh_refresh_token()
    current = _fresh_refresh_token()

    response = _refresh(previous)

    expect(response.status_code).to(equal(HTTP_401_UNAUTHORIZED))
    expect(_refresh(current).status_code).to(equal(HTTP_200_OK))
