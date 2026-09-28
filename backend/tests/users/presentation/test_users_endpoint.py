import json
from types import SimpleNamespace

from expects import equal, expect
from fastapi import status

from src.common.domain.models.user import User
from src.users.presentation.endpoints import users as endpoint_module


async def test_register_user__presents_the_public_view_and_never_grants_superuser(monkeypatch):
    received: list[dict] = []

    class CapturingRegisterer:
        def __init__(self, **kwargs):
            received.append(kwargs)
            self.user = kwargs["user"]

        async def execute(self) -> User:
            return self.user

    monkeypatch.setattr(endpoint_module, "UserRegisterer", CapturingRegisterer)
    request = endpoint_module.RegisterUserRequest.model_validate(
        {"email": "ada@example.com", "password": "pass1234567890", "isSuperuser": True}
    )

    response = await endpoint_module.register_user(
        request=request,
        domain_context=SimpleNamespace(user_repository=object()),  # ty: ignore[invalid-argument-type]
    )

    body = json.loads(bytes(response.body))["data"]
    expect(response.status_code).to(equal(status.HTTP_201_CREATED))
    expect(sorted(body)).to(equal(["emailAddress", "firstName", "lastName", "username", "uuid"]))
    expect(body["emailAddress"]["email"]).to(equal("ada@example.com"))
    expect(received[0].get("is_superuser", False)).to(equal(False))
    expect(hasattr(request, "is_superuser")).to(equal(False))
