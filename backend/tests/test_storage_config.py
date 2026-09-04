"""Tests for the optional S3 settings added in Step 3I.

The settings must default to ``None`` (so the application boots without S3
configuration) and read from the environment when present, without disturbing
the existing settings behaviour.
"""

from __future__ import annotations

import pytest
from app.core.config import Settings

_S3_ENV_NAMES = ("S3_BUCKET_NAME", "AWS_REGION", "S3_ENDPOINT_URL")


@pytest.fixture(autouse=True)
def _clear_s3_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _S3_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_s3_settings_default_to_none() -> None:
    settings = Settings()

    assert settings.S3_BUCKET_NAME is None
    assert settings.AWS_REGION is None
    assert settings.S3_ENDPOINT_URL is None


def test_s3_settings_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_BUCKET_NAME", "cloudpet-images")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:4566")

    settings = Settings()

    assert settings.S3_BUCKET_NAME == "cloudpet-images"
    assert settings.AWS_REGION == "eu-west-1"
    assert settings.S3_ENDPOINT_URL == "http://localhost:4566"


def test_existing_required_settings_are_unchanged() -> None:
    settings = Settings()

    # Provided by conftest's pytest_configure defaults.
    assert str(settings.DATABASE_URL).startswith("postgresql+psycopg://")
    assert settings.JWT_SECRET_KEY
    assert settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 30


def test_unknown_environment_variables_are_still_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLOUDPET_TOTALLY_UNRELATED", "boom")

    settings = Settings()  # extra="ignore" -> must not raise

    assert not hasattr(settings, "CLOUDPET_TOTALLY_UNRELATED")
