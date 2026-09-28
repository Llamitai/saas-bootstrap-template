import pytest
import requests
from expects import equal, expect

from tests.api.conftest import BASE_URL

pytestmark = [pytest.mark.api]


def test_health__is_live_without_credentials():
    response = requests.get(url=f"{BASE_URL}/api/py/health", timeout=30)

    expect(response.status_code).to(equal(200))
    expect(response.json()).to(equal({"status": "ok"}))


def test_health_ready__reports_database_and_redis():
    response = requests.get(url=f"{BASE_URL}/api/py/health/ready", timeout=30)

    expect(response.status_code).to(equal(200))
    expect(response.json()).to(equal({"status": "ok", "checks": {"database": "ok", "redis": "ok"}}))
