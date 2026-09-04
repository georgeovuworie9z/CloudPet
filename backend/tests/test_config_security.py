"""Settings-validation tests for Step 3K production hardening.

Constructs Settings() directly via monkeypatched environment variables
(bypassing the lru_cache'd get_settings() singleton), matching the pattern
established in test_storage_config.py / test_storage_s3.py.
"""

from __future__ import annotations

import pytest
from app.core.config import ConfigurationError, Settings, get_settings
from pydantic import ValidationError

_VALID_DATABASE_URL = "postgresql+psycopg://u:p@localhost:5432/cloudpet_test"
_VALID_PRODUCTION_DATABASE_URL = (
    "postgresql+psycopg://u:p@db.example.com:5432/cloudpet?sslmode=require"
)
_VALID_JWT_SECRET = "x" * 40


def _set_minimum_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    """Set exactly the required fields to valid values, then apply overrides."""
    base: dict[str, str] = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": _VALID_DATABASE_URL,
        "JWT_SECRET_KEY": _VALID_JWT_SECRET,
    }
    base.update(overrides)
    for name, value in base.items():
        monkeypatch.setenv(name, value)


# --------------------------------------------------------------------------- #
# JWT_SECRET_KEY strength (3K-2, 3K-3)
# --------------------------------------------------------------------------- #


def test_short_jwt_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch, JWT_SECRET_KEY="x" * 31)

    with pytest.raises(ValidationError):
        Settings()


def test_minimum_length_jwt_secret_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch, JWT_SECRET_KEY="x" * 32)

    assert Settings().JWT_SECRET_KEY == "x" * 32


def test_placeholder_jwt_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch, JWT_SECRET_KEY="replace-with-a-strong-random-secret")

    with pytest.raises(ValidationError):
        Settings()


# --------------------------------------------------------------------------- #
# ENVIRONMENT is required (3K-4)
# --------------------------------------------------------------------------- #


def test_missing_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_unknown_environment_value_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch, ENVIRONMENT="staging-ish")

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("environment", ["local", "test", "staging", "production"])
def test_each_known_environment_value_is_accepted(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    database_url = _VALID_PRODUCTION_DATABASE_URL if environment == "production" else None
    overrides = {"ENVIRONMENT": environment}
    if database_url is not None:
        overrides["DATABASE_URL"] = database_url
    _set_minimum_env(monkeypatch, **overrides)

    assert environment == Settings().ENVIRONMENT


# --------------------------------------------------------------------------- #
# Production DATABASE_URL must require SSL (3K-6)
# --------------------------------------------------------------------------- #


def test_production_database_url_without_sslmode_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_minimum_env(
        monkeypatch,
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+psycopg://u:p@db.example.com:5432/cloudpet",
    )

    with pytest.raises(ValidationError):
        Settings()


def test_production_database_url_with_sslmode_disable_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_minimum_env(
        monkeypatch,
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+psycopg://u:p@db.example.com:5432/cloudpet?sslmode=disable",
    )

    with pytest.raises(ValidationError):
        Settings()


def test_production_database_url_with_sslmode_require_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_minimum_env(
        monkeypatch, ENVIRONMENT="production", DATABASE_URL=_VALID_PRODUCTION_DATABASE_URL
    )

    assert Settings().ENVIRONMENT == "production"


def test_non_production_database_url_without_sslmode_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_minimum_env(monkeypatch, ENVIRONMENT="local", DATABASE_URL=_VALID_DATABASE_URL)

    assert Settings().ENVIRONMENT == "local"


# --------------------------------------------------------------------------- #
# get_settings() scrubs secret-bearing validation errors (3K-5)
# --------------------------------------------------------------------------- #


def test_get_settings_scrubs_the_invalid_database_url_from_its_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    distinctive_password = "super-secret-db-password-xyz"
    _set_minimum_env(monkeypatch, DATABASE_URL=f"not-a-valid-postgres-url-{distinctive_password}")
    get_settings.cache_clear()

    try:
        with pytest.raises(ConfigurationError) as exc_info:
            get_settings()
        assert distinctive_password not in str(exc_info.value)
        assert "DATABASE_URL" in str(exc_info.value)
    finally:
        get_settings.cache_clear()


def test_get_settings_scrubs_the_rejected_jwt_secret_from_its_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    distinctive_secret = "distinctive-but-too-short"
    _set_minimum_env(monkeypatch, JWT_SECRET_KEY=distinctive_secret)
    get_settings.cache_clear()

    try:
        with pytest.raises(ConfigurationError) as exc_info:
            get_settings()
        assert distinctive_secret not in str(exc_info.value)
        assert "JWT_SECRET_KEY" in str(exc_info.value)
    finally:
        get_settings.cache_clear()


# --------------------------------------------------------------------------- #
# Regression: real env sources used by the project must still validate
# --------------------------------------------------------------------------- #


def test_conftest_test_environment_values_are_still_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mirrors exactly what tests/conftest.py's pytest_configure sets.
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "insecure-test-only-jwt-secret-do-not-use-in-prod-0123456789"
    )
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://cloudpet:cloudpet@localhost:5432/cloudpet_test"
    )

    Settings()  # must not raise


def test_docker_compose_local_environment_values_are_still_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mirrors exactly what docker-compose.yml's api service sets.
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("JWT_SECRET_KEY", "local-dev-secret-not-for-production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://cloudpet:cloudpet@db:5432/cloudpet")

    Settings()  # must not raise


def test_ci_environment_values_are_still_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mirrors exactly what .github/workflows/ci.yml sets.
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "insecure-ci-only-jwt-secret-do-not-use-in-prod-0123456789"
    )
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://cloudpet:cloudpet@localhost:5432/cloudpet_test"
    )

    Settings()  # must not raise
