from datetime import timedelta

import pytest
from expects import be_none, equal, expect

from src.common.domain.enums.jwt import JwtTokenScope
from src.common.infrastructure.services.jwt_token_builder import JwtTokenBuilder
from src.common.settings import settings

# Issued by the previous implementation (authlib.jose, HS256) with this secret and
# `exp` in 2100. Tokens already in browsers must keep validating after the migration.
LEGACY_SECRET = "legacy-authlib-secret-with-at-least-32-chars"
LEGACY_REFRESH_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzYWFzLWJvb3RzdHJhcCIsInN1YiI6IjAxOTBjOWUyLTdhNTUtN2QxZS05YzdmLTBkN2Y1YThlMWIxMSIsImlhdCI6MTc5MDAwMDAwMCwi"
    "ZXhwIjo0MTAyNDQ0ODAwLCJqdGkiOiJsZWdhY3ktcmVmcmVzaC1qdGkiLCJucyI6IkpXVCIsInNjb3BlIjoicmVmcmVzaCJ9."
    "2jsv6hmLjvoqfTZY90tKw7mRojxlUNdKBDgpYMWbHyA"
)


@pytest.fixture
def legacy_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", LEGACY_SECRET)
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    return LEGACY_SECRET


def test_verify_token__accepts_a_token_issued_by_the_previous_library(legacy_secret: str):
    claims = JwtTokenBuilder().verify_token(LEGACY_REFRESH_TOKEN, expected_scope=JwtTokenScope.REFRESH)

    expect(claims.sub).to(equal("0190c9e2-7a55-7d1e-9c7f-0d7f5a8e1b11"))
    expect(claims.jti).to(equal("legacy-refresh-jti"))
    expect(claims.ns).to(equal("JWT"))


def test_verify_token__round_trips_a_new_token():
    builder = JwtTokenBuilder()
    token = builder.create_token(
        sub="user-1",
        scope=JwtTokenScope.ACCESS,
        exp_delta=timedelta(minutes=5),
        namespace="TENANT",
        jti="jti-1",
        extra_claims={"sub": "ignored", "tenant": "acme"},
    )

    claims = builder.verify_token(token, expected_scope=JwtTokenScope.ACCESS)

    expect(claims.sub).to(equal("user-1"))
    expect(claims.jti).to(equal("jti-1"))
    expect(claims.ns).to(equal("TENANT"))
    expect(claims.iss).to(equal(settings.JWT_ISSUER))


def test_verify_token__rejects_a_different_scope():
    builder = JwtTokenBuilder()
    token = builder.create_token(sub="user-1", scope=JwtTokenScope.ACCESS, exp_delta=timedelta(minutes=5))

    expect(builder.verify_token(token, expected_scope=JwtTokenScope.REFRESH)).to(be_none)


def test_verify_token__rejects_an_expired_token():
    builder = JwtTokenBuilder()
    token = builder.create_token(sub="user-1", scope=JwtTokenScope.ACCESS, exp_delta=timedelta(minutes=-1))

    expect(builder.verify_token(token, expected_scope=JwtTokenScope.ACCESS)).to(be_none)


def test_verify_token__rejects_a_token_signed_with_another_secret(legacy_secret: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "another-secret-with-at-least-32-characters")

    expect(JwtTokenBuilder().verify_token(LEGACY_REFRESH_TOKEN, expected_scope=JwtTokenScope.REFRESH)).to(be_none)


def test_verify_token__rejects_malformed_input():
    expect(JwtTokenBuilder().verify_token("not-a-jwt", expected_scope=JwtTokenScope.ACCESS)).to(be_none)


def test_verify_token__rejects_an_unsigned_token():
    unsigned = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0." + LEGACY_REFRESH_TOKEN.split(".")[1] + "."

    expect(JwtTokenBuilder().verify_token(unsigned, expected_scope=JwtTokenScope.REFRESH)).to(be_none)
