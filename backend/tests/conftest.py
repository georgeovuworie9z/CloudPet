"""Shared test fixtures and test-environment setup."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


def pytest_configure() -> None:
    """Provide safe defaults for required settings before the app is imported."""
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-production")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://cloudpet:cloudpet@localhost:5432/cloudpet_test",
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Imported lazily so pytest_configure has already populated the environment.
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
