"""Application configuration loaded from environment variables.

All configuration is supplied via the environment (or a local ``.env`` file that
is never committed). Nothing here has a production-ready default: the app fails
fast if required values are missing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Environment = "local"

    # PostgreSQL connection string, e.g.
    # postgresql+psycopg://user:password@host:5432/dbname
    DATABASE_URL: PostgresDsn

    # HS256 signing key for application-managed JWT auth (used by a later milestone).
    JWT_SECRET_KEY: str

    # Access token lifetime in minutes.
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # AWS S3 object storage (pet images arrive in a later milestone). Optional:
    # the application boots without these; the storage adapter only fails when it
    # is actually constructed and used. Credentials are never configured here --
    # they come from the AWS credential provider chain.
    S3_BUCKET_NAME: str | None = None
    AWS_REGION: str | None = None
    S3_ENDPOINT_URL: str | None = None

    # Level for CloudPet's own "app.*" loggers (Uvicorn's own logging is separate
    # and unaffected). One of the standard library's level names, e.g. DEBUG,
    # INFO, WARNING, ERROR, CRITICAL.
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
