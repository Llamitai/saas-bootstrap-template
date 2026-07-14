from expects import equal, expect

from src.assets.domain.helpers.storage_url import build_storage_url
from src.common.settings import settings


def test_build_storage_url__prefixes_public_base(monkeypatch):
    monkeypatch.setattr(settings, "AWS_S3_PUBLIC_URL", "https://cdn.example.com")

    result = build_storage_url("tenants/abc/avatar.png")

    expect(result).to(equal("https://cdn.example.com/tenants/abc/avatar.png"))


def test_build_storage_url__strips_trailing_slash_from_base(monkeypatch):
    monkeypatch.setattr(settings, "AWS_S3_PUBLIC_URL", "https://cdn.example.com/")

    result = build_storage_url("tenants/abc/avatar.png")

    expect(result).to(equal("https://cdn.example.com/tenants/abc/avatar.png"))


def test_build_storage_url__returns_key_when_no_base_configured(monkeypatch):
    monkeypatch.setattr(settings, "AWS_S3_PUBLIC_URL", None)

    result = build_storage_url("tenants/abc/avatar.png")

    expect(result).to(equal("tenants/abc/avatar.png"))
