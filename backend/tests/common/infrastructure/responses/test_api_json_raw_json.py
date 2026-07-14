"""ApiJSONResponse + RawJson preserves user-defined JSON keys."""

from expects import equal, expect, have_keys
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common.application.helpers.json_encoder import RawJson
from src.common.infrastructure.responses.api_json import ApiJSONResponse


def _build_client() -> TestClient:
    app = FastAPI(default_response_class=ApiJSONResponse)

    @app.get("/settings")
    def get_settings():
        return {
            "tenant_id": "tenant-1",
            "schema": RawJson(
                {
                    "display_name": {"type": "string"},
                    "x-custom-key": True,
                }
            ),
        }

    return TestClient(app)


def test_api_json_response__wraps_in_data_envelope_with_timestamp():
    body = _build_client().get("/settings").json()

    expect(body).to(have_keys("data", "timestamp"))


def test_api_json_response__camels_normal_keys():
    data = _build_client().get("/settings").json()["data"]

    expect(data).to(have_keys("tenantId", "schema"))


def test_api_json_response__raw_json_preserves_nested_keys():
    data = _build_client().get("/settings").json()["data"]

    expect(data["schema"]).to(have_keys("display_name", "x-custom-key"))
    expect(data["schema"]["display_name"]).to(equal({"type": "string"}))
