from typing import Any

import pytest
from expects import contain, equal, expect
from pydantic import ValidationError

from src.common.domain.enums.common import Environment
from src.common.settings import Settings

STRONG_SECRET = "x" * 43


def production_settings_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "_env_file": None,
        "ENVIRONMENT": Environment.production,
        "JWT_SECRET_KEY": STRONG_SECRET,
        "SECRET_KEY": STRONG_SECRET,
        "ADMIN_API_KEY": STRONG_SECRET,
        "POSTGRES_PASSWORD": "strong-db-password",
        "REDIS_PASSWORD": "strong-redis-password",
    }
    kwargs.update(overrides)
    return kwargs


def test_production_requires_explicit_secrets() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            **production_settings_kwargs(
                JWT_SECRET_KEY="",
                SECRET_KEY="",
                ADMIN_API_KEY="",
                POSTGRES_PASSWORD="",
                REDIS_PASSWORD="",
            )
        )

    expect(str(exc_info.value)).to(
        contain(
            "Missing required production secret(s): "
            "JWT_SECRET_KEY, SECRET_KEY, ADMIN_API_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD"
        )
    )


def test_production_accepts_strong_secrets() -> None:
    production_settings = Settings(**production_settings_kwargs())

    expect(production_settings.JWT_SECRET_KEY).to(equal(STRONG_SECRET))
    expect(production_settings.SECRET_KEY).to(equal(STRONG_SECRET))


def test_production_rejects_placeholder_secrets() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(**production_settings_kwargs(JWT_SECRET_KEY="your-jwt-secret-key-here-1234567890"))

    expect(str(exc_info.value)).to(contain("JWT_SECRET_KEY looks like a placeholder value"))


def test_production_rejects_short_signing_secrets() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(**production_settings_kwargs(SECRET_KEY="short-secret"))

    expect(str(exc_info.value)).to(contain("SECRET_KEY must be at least 32 characters"))


def test_production_rejects_default_postgres_password() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(**production_settings_kwargs(POSTGRES_PASSWORD="postgres"))

    expect(str(exc_info.value)).to(contain("POSTGRES_PASSWORD must not be the default 'postgres'"))


def test_local_environment_generates_missing_secrets() -> None:
    local_settings = Settings(
        _env_file=None,
        ENVIRONMENT=Environment.development,
        JWT_SECRET_KEY="",
        SECRET_KEY="",
        ADMIN_API_KEY="",
    )

    assert local_settings.JWT_SECRET_KEY
    assert local_settings.SECRET_KEY
    assert local_settings.ADMIN_API_KEY


def test_session_token_ttls_match_cookie_policy() -> None:
    local_settings = Settings(_env_file=None, ENVIRONMENT=Environment.testing)

    assert local_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert local_settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES == 60 * 24 * 7
