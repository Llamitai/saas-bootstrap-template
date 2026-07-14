"""Rate-limit behavior on sensitive auth endpoints.

NOTE: this file is named ``test_zz_rate_limit`` on purpose so it runs LAST
in the api suite: exhausting the login rate limit would otherwise make the
remaining tests that log in fail with 429 until the window expires.
"""

import pytest
import requests
from expects import be_above, equal, expect

from tests.api.conftest import BASE_URL, USER_EMAIL

pytestmark = [pytest.mark.api]

HTTP_429_TOO_MANY_REQUESTS = 429

# Must match ``login_rate_limit`` in src/auth/presentation/endpoints/../router.py.
LOGIN_RATE_LIMIT = 20


def test_login__rate_limited_after_too_many_attempts():
    """Hammering the login endpoint past its per-IP limit returns 429.

    Earlier tests in the suite already consumed part of the window, so the
    429 may arrive before ``LOGIN_RATE_LIMIT`` attempts — we only require
    that it shows up within limit + margin attempts.
    """
    last_status = None

    for _ in range(LOGIN_RATE_LIMIT + 5):
        response = requests.post(
            url=f"{BASE_URL}/v1/auth/login",
            json={"email": USER_EMAIL, "password": "definitely-wrong-password"},
            timeout=30,
        )
        last_status = response.status_code
        if last_status == HTTP_429_TOO_MANY_REQUESTS:
            break

    expect(last_status).to(equal(HTTP_429_TOO_MANY_REQUESTS))
    expect(int(response.headers["Retry-After"])).to(be_above(0))
    expect(response.headers["X-RateLimit-Remaining"]).to(equal("0"))
