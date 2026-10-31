"""
tests/test_auth_config.py
=========================
Unit tests for AstroOS JWT authentication configuration (Phase 5B.1).

These tests reload ``app.core.config`` in isolation using ``importlib.reload``
and ``monkeypatch`` so that they do not depend on a real ``.env`` file.

Each test sets ``DATABASE_URL`` to a dummy value to satisfy the existing
startup requirement that the variable must be non-empty.
"""

import importlib
import os

import pytest

_DUMMY_DB_URL = "postgresql+psycopg://user:pass@localhost/test"
_VALID_SECRET = "a" * 32  # 32 bytes — meets the minimum length requirement


def _reload(monkeypatch, overrides: dict) -> object:
    """Apply *overrides* and reload app.core.config, returning the module.

    Patches ``dotenv.load_dotenv`` to a no-op so tests run in pure isolation
    from any developer ``.env`` file on disk.
    """
    import dotenv
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)

    import app.core.config as config_module

    # Always provide a valid DATABASE_URL so the existing startup check passes.
    env = {"DATABASE_URL": _DUMMY_DB_URL}
    env.update(overrides)

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    return importlib.reload(config_module)


# ---------------------------------------------------------------------------
# 1. JWT settings load correctly from environment variables
# ---------------------------------------------------------------------------
class TestJwtSettingsLoad:
    def test_jwt_settings_loaded_from_env(self, monkeypatch):
        config = _reload(
            monkeypatch,
            {
                "JWT_SECRET_KEY": _VALID_SECRET,
                "JWT_ALGORITHM": "HS384",
                "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
                "REFRESH_TOKEN_EXPIRE_DAYS": "14",
                "ENABLE_PUBLIC_REGISTRATION": "false",
                "ENVIRONMENT": "development",
            },
        )

        assert config.JWT_SECRET_KEY == _VALID_SECRET
        assert config.JWT_ALGORITHM == "HS384"
        assert config.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert config.REFRESH_TOKEN_EXPIRE_DAYS == 14
        assert config.ENABLE_PUBLIC_REGISTRATION is False


# ---------------------------------------------------------------------------
# 2. Default algorithm is HS256 when JWT_ALGORITHM is not set
# ---------------------------------------------------------------------------
class TestDefaultAlgorithm:
    def test_default_algorithm_is_hs256(self, monkeypatch):
        monkeypatch.delenv("JWT_ALGORITHM", raising=False)
        config = _reload(monkeypatch, {"JWT_SECRET_KEY": _VALID_SECRET})

        assert config.JWT_ALGORITHM == "HS256"


# ---------------------------------------------------------------------------
# 3. Access-token and refresh-token lifetimes are positive
# ---------------------------------------------------------------------------
class TestTokenLifetimes:
    def test_default_access_token_expire_minutes_is_positive(self, monkeypatch):
        monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
        config = _reload(monkeypatch, {"JWT_SECRET_KEY": _VALID_SECRET})

        assert config.ACCESS_TOKEN_EXPIRE_MINUTES > 0

    def test_default_refresh_token_expire_days_is_positive(self, monkeypatch):
        monkeypatch.delenv("REFRESH_TOKEN_EXPIRE_DAYS", raising=False)
        config = _reload(monkeypatch, {"JWT_SECRET_KEY": _VALID_SECRET})

        assert config.REFRESH_TOKEN_EXPIRE_DAYS > 0

    def test_zero_access_token_expire_minutes_raises(self, monkeypatch):
        with pytest.raises(RuntimeError, match="ACCESS_TOKEN_EXPIRE_MINUTES"):
            _reload(
                monkeypatch,
                {
                    "JWT_SECRET_KEY": _VALID_SECRET,
                    "ACCESS_TOKEN_EXPIRE_MINUTES": "0",
                },
            )

    def test_negative_refresh_token_expire_days_raises(self, monkeypatch):
        with pytest.raises(RuntimeError, match="REFRESH_TOKEN_EXPIRE_DAYS"):
            _reload(
                monkeypatch,
                {
                    "JWT_SECRET_KEY": _VALID_SECRET,
                    "REFRESH_TOKEN_EXPIRE_DAYS": "-1",
                },
            )


# ---------------------------------------------------------------------------
# 4. ENABLE_PUBLIC_REGISTRATION defaults to True
# ---------------------------------------------------------------------------
class TestPublicRegistrationDefault:
    def test_enable_public_registration_defaults_to_true(self, monkeypatch):
        monkeypatch.delenv("ENABLE_PUBLIC_REGISTRATION", raising=False)
        config = _reload(monkeypatch, {"JWT_SECRET_KEY": _VALID_SECRET})

        assert config.ENABLE_PUBLIC_REGISTRATION is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no"])
    def test_enable_public_registration_falsy_values(self, monkeypatch, value):
        config = _reload(
            monkeypatch,
            {
                "JWT_SECRET_KEY": _VALID_SECRET,
                "ENABLE_PUBLIC_REGISTRATION": value,
            },
        )
        assert config.ENABLE_PUBLIC_REGISTRATION is False


# ---------------------------------------------------------------------------
# 5. Unsupported algorithm raises RuntimeError at startup
# ---------------------------------------------------------------------------
class TestUnsupportedAlgorithm:
    @pytest.mark.parametrize("algorithm", ["RS256", "ES256", "none", "NONE", "HS999"])
    def test_unsupported_algorithm_raises(self, monkeypatch, algorithm):
        with pytest.raises(RuntimeError, match="JWT_ALGORITHM"):
            _reload(
                monkeypatch,
                {
                    "JWT_SECRET_KEY": _VALID_SECRET,
                    "JWT_ALGORITHM": algorithm,
                },
            )

    @pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512"])
    def test_supported_algorithms_do_not_raise(self, monkeypatch, algorithm):
        config = _reload(
            monkeypatch,
            {
                "JWT_SECRET_KEY": _VALID_SECRET,
                "JWT_ALGORITHM": algorithm,
            },
        )
        assert config.JWT_ALGORITHM == algorithm


# ---------------------------------------------------------------------------
# 6. Missing JWT_SECRET_KEY in production raises RuntimeError
# ---------------------------------------------------------------------------
class TestProductionSecretRequired:
    def test_missing_secret_in_production_raises(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            _reload(monkeypatch, {"ENVIRONMENT": "production"})

    def test_missing_secret_in_development_does_not_raise(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        # Should NOT raise in development.
        config = _reload(monkeypatch, {"ENVIRONMENT": "development"})
        assert config.JWT_SECRET_KEY is None


# ---------------------------------------------------------------------------
# 7. Placeholder secret always raises RuntimeError (regardless of environment)
# ---------------------------------------------------------------------------
class TestPlaceholderSecret:
    @pytest.mark.parametrize(
        "placeholder",
        [
            "replace_with_a_secure_random_secret",
            "your-secret-key",
            "changeme",
            "secret",
            "jwt_secret",
        ],
    )
    def test_known_placeholder_raises(self, monkeypatch, placeholder):
        with pytest.raises(RuntimeError, match="placeholder"):
            _reload(
                monkeypatch,
                {
                    "JWT_SECRET_KEY": placeholder,
                    "ENVIRONMENT": "development",
                },
            )

    def test_placeholder_raises_in_production(self, monkeypatch):
        with pytest.raises(RuntimeError, match="placeholder"):
            _reload(
                monkeypatch,
                {
                    "JWT_SECRET_KEY": "changeme",
                    "ENVIRONMENT": "production",
                },
            )


# ---------------------------------------------------------------------------
# 8. Too-short secret (< 32 bytes) raises RuntimeError
# ---------------------------------------------------------------------------
class TestShortSecret:
    def test_short_secret_raises(self, monkeypatch):
        short_secret = "a" * 31  # one byte short
        with pytest.raises(RuntimeError, match="too short"):
            _reload(
                monkeypatch,
                {
                    "JWT_SECRET_KEY": short_secret,
                    "ENVIRONMENT": "development",
                },
            )

    def test_exactly_32_bytes_does_not_raise(self, monkeypatch):
        secret_32 = "b" * 32
        config = _reload(
            monkeypatch,
            {
                "JWT_SECRET_KEY": secret_32,
                "ENVIRONMENT": "development",
            },
        )
        assert config.JWT_SECRET_KEY == secret_32

    def test_empty_string_secret_in_production_raises(self, monkeypatch):
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            _reload(
                monkeypatch,
                {
                    "JWT_SECRET_KEY": "",
                    "ENVIRONMENT": "production",
                },
            )


# ---------------------------------------------------------------------------
# 9. Secret value is NOT present in any RuntimeError message
# ---------------------------------------------------------------------------
class TestSecretNotLeakedInErrors:
    def test_short_secret_not_in_error_message(self, monkeypatch):
        sensitive = "mysupersecretvalue123456789012"  # < 32 bytes
        with pytest.raises(RuntimeError) as exc_info:
            _reload(
                monkeypatch,
                {
                    "JWT_SECRET_KEY": sensitive,
                    "ENVIRONMENT": "development",
                },
            )
        assert sensitive not in str(exc_info.value)

    def test_placeholder_secret_value_not_in_error_message(self, monkeypatch):
        placeholder = "changeme"
        with pytest.raises(RuntimeError) as exc_info:
            _reload(
                monkeypatch,
                {
                    "JWT_SECRET_KEY": placeholder,
                    "ENVIRONMENT": "development",
                },
            )
        # The word "changeme" should not appear in the error message.
        assert placeholder not in str(exc_info.value)


# ---------------------------------------------------------------------------
# 10. Existing configuration still loads without regression
# ---------------------------------------------------------------------------
class TestExistingConfigRegression:
    def test_database_url_still_loaded(self, monkeypatch):
        config = _reload(
            monkeypatch,
            {"DATABASE_URL": _DUMMY_DB_URL, "JWT_SECRET_KEY": _VALID_SECRET},
        )
        assert config.DATABASE_URL == _DUMMY_DB_URL

    def test_cors_origins_still_parsed(self, monkeypatch):
        config = _reload(
            monkeypatch,
            {
                "JWT_SECRET_KEY": _VALID_SECRET,
                "CORS_ALLOWED_ORIGINS": "https://example.com,https://app.example.com",
            },
        )
        assert "https://example.com" in config.CORS_ALLOWED_ORIGINS
        assert "https://app.example.com" in config.CORS_ALLOWED_ORIGINS

    def test_enable_api_docs_still_works(self, monkeypatch):
        config = _reload(
            monkeypatch,
            {
                "JWT_SECRET_KEY": _VALID_SECRET,
                "ENABLE_API_DOCS": "false",
            },
        )
        assert config.ENABLE_API_DOCS is False

    def test_weather_cache_ttl_still_loaded(self, monkeypatch):
        config = _reload(
            monkeypatch,
            {
                "JWT_SECRET_KEY": _VALID_SECRET,
                "WEATHER_CACHE_TTL_SECONDS": "3600",
            },
        )
        assert config.WEATHER_CACHE_TTL_SECONDS == 3600

