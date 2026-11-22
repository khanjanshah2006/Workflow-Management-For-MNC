"""Tests for central settings (W4-BE-0)."""
import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from app.core.config import DEFAULT_JWT_SECRET, ConfigError, Settings, settings
from app.features.auth.router import set_refresh_cookie
from app.main import app

STRONG_SECRET = "s" * 48
PROD_ENV = {
    "ENV": "production",
    "JWT_SECRET_KEY": STRONG_SECRET,
    "DATABASE_URL": "postgresql://user:pass@db.example.com:5432/app",
    "CORS_ORIGINS": "https://app.example.com",
}


def _prod(**overrides):
    env = {**PROD_ENV, **overrides}
    return Settings.from_env({k: v for k, v in env.items() if v is not None})


def test_production_requires_strong_jwt_secret():
    assert _prod().validate().is_production

    with pytest.raises(ConfigError, match="default"):
        _prod(JWT_SECRET_KEY=DEFAULT_JWT_SECRET).validate()
    with pytest.raises(ConfigError, match="at least 32"):
        _prod(JWT_SECRET_KEY="short-secret").validate()
    with pytest.raises(ConfigError, match="JWT_SECRET_KEY"):
        _prod(JWT_SECRET_KEY=None).validate()


def test_production_requires_database_url_and_cors_origins():
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        _prod(DATABASE_URL=None).validate()
    with pytest.raises(ConfigError, match="CORS_ORIGINS"):
        _prod(CORS_ORIGINS="  ").validate()


def test_development_allows_defaults():
    dev = Settings.from_env({}).validate()
    assert not dev.is_production
    assert dev.jwt_secret_key == DEFAULT_JWT_SECRET
    assert dev.cors_origins == ["http://localhost:5173"]
    assert dev.database_url.startswith("postgresql+psycopg2://")


def test_cors_origins_parsed_from_env():
    parsed = Settings.from_env(
        {"CORS_ORIGINS": " https://a.example.com , https://b.example.com/,,"}
    )
    assert parsed.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_unlisted_origin_gets_no_cors_header():
    client = TestClient(app)
    allowed = settings.cors_origins[0]

    ok = client.get("/health", headers={"Origin": allowed})
    assert ok.headers.get("access-control-allow-origin") == allowed
    assert ok.headers.get("access-control-allow-credentials") == "true"

    blocked = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in blocked.headers

    preflight = client.options(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in preflight.headers


def test_cookie_flags_follow_settings(monkeypatch):
    monkeypatch.setattr(settings, "cookie_secure", True)
    monkeypatch.setattr(settings, "cookie_samesite", "strict")
    monkeypatch.setattr(settings, "refresh_token_expire_days", 3)

    response = Response()
    set_refresh_cookie(response, "token-value")
    cookie = response.headers["set-cookie"]

    assert "refresh_token=token-value" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert f"Max-Age={3 * 24 * 3600}" in cookie
    assert "Path=/api/v1/auth" in cookie


def test_cookie_defaults_are_lax_and_not_secure():
    dev = Settings.from_env({})
    assert dev.cookie_secure is False
    assert dev.cookie_samesite == "lax"
    assert dev.refresh_cookie_max_age == 7 * 24 * 3600


def test_samesite_none_requires_secure():
    with pytest.raises(ConfigError, match="COOKIE_SECURE"):
        Settings.from_env({"COOKIE_SAMESITE": "none"}).validate()
    Settings.from_env({"COOKIE_SAMESITE": "none", "COOKIE_SECURE": "true"}).validate()


def test_docs_can_be_disabled():
    assert Settings.from_env({"ENABLE_DOCS": "false"}).enable_docs is False
    assert Settings.from_env({}).enable_docs is True
