"""A new or reset password closes every session of the user."""

import os
import re
import time
from dataclasses import dataclass
from uuid import uuid4

import pytest
import requests
from expects import equal, expect

from src.common.domain.constants.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_401_UNAUTHORIZED
from tests.api.conftest import BASE_URL

pytestmark = [pytest.mark.api]

MAILPIT_URL = os.environ.get("E2E_MAILPIT_URL", "http://mailpit:8025")
PASSWORD = "pass1234567890"
NEW_PASSWORD = "renewed1234567890"
RESET_LINK = re.compile(r"/reset_password/([\w-]+\.[\w-]+\.[\w-]+)")


@dataclass
class Account:
    email: str
    headers: dict


@pytest.fixture
def account(api_key_header: dict) -> Account:
    # A dedicated user (the shared one keeps its password) and a client IP of its
    # own, so these logins do not spend the suite's per-IP login budget.
    client_ip = f"10.{uuid4().int % 250}.{uuid4().int % 250}.{uuid4().int % 250 + 1}"
    headers = {**api_key_header, "X-Client-IP": client_ip}
    email = f"revoke-{uuid4().hex[:8]}@test.com"
    response = requests.post(
        url=f"{BASE_URL}/v1/users",
        json={"email": email, "password": PASSWORD},
        headers=headers,
        timeout=30,
    )
    expect(response.status_code).to(equal(HTTP_201_CREATED))
    return Account(email=email, headers=headers)


def _login(account: Account, password: str = PASSWORD) -> dict:
    response = requests.post(
        url=f"{BASE_URL}/v1/auth/login",
        json={"email": account.email, "password": password},
        headers=account.headers,
        timeout=30,
    )
    expect(response.status_code).to(equal(HTTP_201_CREATED))
    return response.json()["data"]["session"]


def _refresh(refresh_token: str) -> requests.Response:
    return requests.post(url=f"{BASE_URL}/v1/auth/refresh", json={"refreshToken": refresh_token}, timeout=30)


def _reset_token(email: str) -> str:
    for _ in range(50):
        found = requests.get(f"{MAILPIT_URL}/api/v1/search", params={"query": f"to:{email}"}, timeout=10).json()
        if found["messages"]:
            message = requests.get(f"{MAILPIT_URL}/api/v1/message/{found['messages'][0]['ID']}", timeout=10).json()
            match = RESET_LINK.search(message["Text"] or message["HTML"])
            if match:
                return match.group(1)
        time.sleep(0.2)
    pytest.fail(f"No password-reset email reached {email}")


def test_update_password__closes_every_session_of_the_user(account: Account):
    session = _login(account)

    response = requests.put(
        url=f"{BASE_URL}/v1/me/password",
        json={"currentPassword": PASSWORD, "newPassword": NEW_PASSWORD},
        headers={"Authorization": f"Bearer {session['accessToken']}"},
        timeout=30,
    )

    expect(response.status_code).to(equal(HTTP_200_OK))
    expect(_refresh(session["refreshToken"]).status_code).to(equal(HTTP_401_UNAUTHORIZED))
    expect(_refresh(_login(account, NEW_PASSWORD)["refreshToken"]).status_code).to(equal(HTTP_200_OK))


def test_reset_password_confirm__closes_every_session_and_burns_the_link(account: Account):
    session = _login(account)
    requests.post(
        url=f"{BASE_URL}/v1/auth/reset-password",
        json={"email": account.email},
        headers=account.headers,
        timeout=30,
    )
    token = _reset_token(account.email)

    confirm = requests.post(
        url=f"{BASE_URL}/v1/auth/reset-password/confirm",
        json={"token": token, "password": NEW_PASSWORD},
        headers=account.headers,
        timeout=30,
    )
    replay = requests.post(
        url=f"{BASE_URL}/v1/auth/reset-password/confirm",
        json={"token": token, "password": PASSWORD},
        headers=account.headers,
        timeout=30,
    )

    expect(confirm.status_code).to(equal(HTTP_200_OK))
    expect(replay.status_code).not_to(equal(HTTP_200_OK))
    expect(_refresh(session["refreshToken"]).status_code).to(equal(HTTP_401_UNAUTHORIZED))
    expect(_refresh(_login(account, NEW_PASSWORD)["refreshToken"]).status_code).to(equal(HTTP_200_OK))
