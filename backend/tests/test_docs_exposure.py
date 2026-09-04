"""Environment-gating tests for the OpenAPI docs endpoints (Step 3K).

/docs, /redoc, and /openapi.json must be disabled in production and remain
available everywhere else. Builds a fresh app via create_app(settings=...) so
each test reflects a specific environment without mutating global state.
"""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def _app_for(monkeypatch: pytest.MonkeyPatch, *, environment: str, database_url: str) -> TestClient:
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    return TestClient(create_app(settings=Settings()))


def test_docs_are_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app_for(
        monkeypatch,
        environment="production",
        database_url="postgresql+psycopg://u:p@db.example.com:5432/cloudpet?sslmode=require",
    )

    for path in _DOCS_PATHS:
        response = client.get(path)
        assert response.status_code == 404, path


@pytest.mark.parametrize("environment", ["local", "test", "staging"])
def test_docs_remain_enabled_outside_production(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    client = _app_for(
        monkeypatch,
        environment=environment,
        database_url="postgresql+psycopg://u:p@localhost:5432/cloudpet_test",
    )

    for path in _DOCS_PATHS:
        response = client.get(path)
        assert response.status_code == 200, path


def test_docs_are_enabled_on_the_real_test_environment_app(api_client: TestClient) -> None:
    # Regression: the process-wide app (built with the real test-environment
    # settings) is unaffected by the environment-gating logic.
    for path in _DOCS_PATHS:
        response = api_client.get(path)
        assert response.status_code == 200, path
