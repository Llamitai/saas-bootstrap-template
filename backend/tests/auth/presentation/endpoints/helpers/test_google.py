import time
from typing import Any

import pytest
from expects import be_none, equal, expect
from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

from src.auth.presentation.endpoints.helpers import google
from src.common.settings import settings

CLIENT_ID = "client-123.apps.googleusercontent.com"


@pytest.fixture
def signing_key() -> RSAKey:
    return RSAKey.generate_key(2048, parameters={"kid": "google-key-1", "use": "sig", "alg": "RS256"})


@pytest.fixture
def jwks_fetches(monkeypatch: pytest.MonkeyPatch, signing_key: RSAKey) -> list[int]:
    fetches: list[int] = []

    async def fake_fetch() -> dict[str, Any]:
        fetches.append(1)
        return KeySet([signing_key]).as_dict(private=False)

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(google, "_fetch_google_jwks", fake_fetch)
    google.clear_google_jwks_cache()
    yield fetches
    google.clear_google_jwks_cache()


def _id_token(key: RSAKey, **overrides: Any) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-user-1",
        "email": "ada@example.com",
        "given_name": "Ada",
        "iat": now,
        "exp": now + 300,
        **overrides,
    }
    return jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key)


@pytest.mark.parametrize("issuer", ["https://accounts.google.com", "accounts.google.com"])
async def test_verify_google_id_token__accepts_google_issuers(
    jwks_fetches: list[int], signing_key: RSAKey, issuer: str
):
    user = await google.verify_google_id_token(_id_token(signing_key, iss=issuer))

    expect(user.email).to(equal("ada@example.com"))
    expect(user.given_name).to(equal("Ada"))


async def test_verify_google_id_token__rejects_an_unexpected_issuer(jwks_fetches: list[int], signing_key: RSAKey):
    token = _id_token(signing_key, iss="https://evil.example.com")

    expect(await google.verify_google_id_token(token)).to(be_none)


async def test_verify_google_id_token__rejects_another_audience(jwks_fetches: list[int], signing_key: RSAKey):
    token = _id_token(signing_key, aud="another-client")

    expect(await google.verify_google_id_token(token)).to(be_none)


async def test_verify_google_id_token__rejects_an_expired_token(jwks_fetches: list[int], signing_key: RSAKey):
    token = _id_token(signing_key, exp=int(time.time()) - 600)

    expect(await google.verify_google_id_token(token)).to(be_none)


async def test_verify_google_id_token__rejects_a_token_without_email(jwks_fetches: list[int], signing_key: RSAKey):
    token = _id_token(signing_key, email=None)

    expect(await google.verify_google_id_token(token)).to(be_none)


async def test_verify_google_id_token__rejects_a_token_signed_by_an_unknown_key(jwks_fetches: list[int]):
    foreign_key = RSAKey.generate_key(2048, parameters={"kid": "foreign"})

    expect(await google.verify_google_id_token(_id_token(foreign_key))).to(be_none)


async def test_verify_google_id_token__caches_the_google_keys(jwks_fetches: list[int], signing_key: RSAKey):
    await google.verify_google_id_token(_id_token(signing_key))
    await google.verify_google_id_token(_id_token(signing_key))

    expect(len(jwks_fetches)).to(equal(1))


async def test_verify_google_id_token__refetches_keys_after_the_ttl(
    jwks_fetches: list[int], signing_key: RSAKey, monkeypatch: pytest.MonkeyPatch
):
    await google.verify_google_id_token(_id_token(signing_key))
    monkeypatch.setattr(google, "GOOGLE_JWKS_TTL_SECONDS", 0)

    await google.verify_google_id_token(_id_token(signing_key))

    expect(len(jwks_fetches)).to(equal(2))
