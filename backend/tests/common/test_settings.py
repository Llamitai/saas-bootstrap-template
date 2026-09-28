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
        "RABBITMQ_PASSWORD": "strong-rabbitmq-password",
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
                RABBITMQ_PASSWORD="",
            )
        )

    expect(str(exc_info.value)).to(
        contain(
            "Missing required production secret(s): "
            "JWT_SECRET_KEY, SECRET_KEY, ADMIN_API_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD, "
            "RABBITMQ_PASSWORD"
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


@pytest.mark.parametrize("password", ["app", "guest"])
def test_production_rejects_default_rabbitmq_password(password: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(**production_settings_kwargs(RABBITMQ_PASSWORD=password))

    expect(str(exc_info.value)).to(contain("RABBITMQ_PASSWORD must not be a default"))


def test_rabbitmq_url__encodes_credentials_and_vhost() -> None:
    local_settings = Settings(
        _env_file=None,
        ENVIRONMENT=Environment.testing,
        RABBITMQ_HOST="broker",
        RABBITMQ_PORT=5673,
        RABBITMQ_USER="worker@app",
        RABBITMQ_PASSWORD="p@ss/word:1",
        RABBITMQ_VHOST="/",
    )

    expect(local_settings.rabbitmq_url).to(equal("amqp://worker%40app:p%40ss%2Fword%3A1@broker:5673/%2F"))


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


def test_sentry_does_not_send_pii_by_default() -> None:
    local_settings = Settings(_env_file=None, ENVIRONMENT=Environment.testing)

    expect(local_settings.SENTRY_SEND_DEFAULT_PII).to(equal(False))


def test_worker_process_label_is_accepted() -> None:
    worker_settings = Settings(_env_file=None, ENVIRONMENT=Environment.testing, PROCESS_LABEL="worker")

    expect(worker_settings.PROCESS_LABEL.value).to(equal("worker"))
