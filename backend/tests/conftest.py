"""Shared test fixtures and test-environment setup."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def pytest_configure() -> None:
    """Provide safe defaults for required settings before the app is imported."""
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault(
        "JWT_SECRET_KEY", "insecure-test-only-jwt-secret-do-not-use-in-prod-0123456789"
    )
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


# --------------------------------------------------------------------------- #
# PostgreSQL test harness (repository / service tests)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def database_url() -> str:
    """The database URL for tests, guarded so it can never be a real database."""
    from app.core.config import settings

    url_str = str(settings.DATABASE_URL)
    database = make_url(url_str).database
    if not database or "test" not in database:
        raise RuntimeError(
            "Refusing to run database tests: DATABASE_URL points at "
            f"{database!r}, which does not look like a test database. Set "
            "DATABASE_URL to a database whose name contains 'test'."
        )
    return url_str


@pytest.fixture(scope="session")
def _schema_at_head(database_url: str) -> Iterator[None]:
    """Bring the test database's schema to Alembic head, then tear it back down.

    Uses the real migrations rather than ``Base.metadata.create_all`` so tests
    run against the exact application schema.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(_BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    # ``alembic/env.py`` derives the URL from ``settings.DATABASE_URL`` (the
    # guarded test database in this process); set it here too for clarity.
    config.set_main_option("sqlalchemy.url", database_url)

    try:
        command.upgrade(config, "head")
    except OperationalError as exc:
        raise RuntimeError(
            f"Could not reach the test database at {make_url(database_url).render_as_string()}.\n"
            "Start it and create the database, e.g.:\n"
            "  docker compose up -d db\n"
            "  docker compose exec db createdb -U cloudpet cloudpet_test"
        ) from exc

    try:
        yield
    finally:
        command.downgrade(config, "base")


@pytest.fixture(scope="session")
def test_engine(database_url: str, _schema_at_head: None) -> Iterator[Engine]:
    """A session-scoped engine bound to the migrated test database."""
    engine = create_engine(database_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    """A function-scoped session wrapped in a transaction that is always rolled back.

    The session joins an outer connection-level transaction via a SAVEPOINT
    (``join_transaction_mode="create_savepoint"``), so code under test may call
    ``Session.commit()`` freely while every change is discarded at teardown.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
