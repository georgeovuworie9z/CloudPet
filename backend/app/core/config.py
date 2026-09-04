"""Application configuration loaded from environment variables.

All configuration is supplied via the environment (or a local ``.env`` file that
is never committed). Nothing here has a production-ready default: the app fails
fast if required values are missing or invalid. Validation failures never echo
the attempted value of a field -- see :func:`get_settings`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, PostgresDsn, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]

# The exact placeholder from .env.example. It is long enough to pass a plain
# length check, so it needs its own explicit rejection.
_PLACEHOLDER_JWT_SECRET_KEY = "replace-with-a-strong-random-secret"

_SSL_MODES_REQUIRED_IN_PRODUCTION = frozenset({"require", "verify-ca", "verify-full"})


class ConfigurationError(RuntimeError):
    """Application settings failed validation.

    Raised instead of letting the underlying ``pydantic.ValidationError``
    propagate: that error can echo the attempted (invalid) value of a field --
    which might be a secret, such as a password embedded in ``DATABASE_URL``, or
    a rejected ``JWT_SECRET_KEY``. Only the names of the failing fields are
    included here, never their values.
    """


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required: a deployment that forgets to declare its environment must fail
    # to boot rather than silently behave like local development.
    ENVIRONMENT: Environment

    # PostgreSQL connection string, e.g.
    # postgresql+psycopg://user:password@host:5432/dbname
    # In production this must include sslmode=require (or stronger) -- see
    # _require_ssl_for_production_database below.
    DATABASE_URL: PostgresDsn

    # HS256 signing key for application-managed JWT auth. At least 32 characters
    # (256 bits), per RFC 7518's guidance for HS256, and must not be the
    # .env.example placeholder -- see the validators below.
    JWT_SECRET_KEY: str = Field(min_length=32)

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

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _reject_placeholder_jwt_secret(cls, value: str) -> str:
        if value == _PLACEHOLDER_JWT_SECRET_KEY:
            raise ValueError(
                "JWT_SECRET_KEY is still set to the .env.example placeholder value; "
                "generate a real secret and set it via the environment."
            )
        return value

    @model_validator(mode="after")
    def _require_ssl_for_production_database(self) -> Settings:
        if self.ENVIRONMENT == "production":
            query = urlsplit(str(self.DATABASE_URL)).query
            values = parse_qs(query).get("sslmode")
            sslmode = values[0] if values else None
            if sslmode not in _SSL_MODES_REQUIRED_IN_PRODUCTION:
                raise ValueError(
                    "DATABASE_URL must specify sslmode=require (or stronger) when "
                    "ENVIRONMENT=production."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Build the application :class:`Settings`, or fail with a scrubbed error.

    A ``pydantic.ValidationError`` is caught and replaced with
    :class:`ConfigurationError` naming only the invalid field(s) -- never their
    values -- so a malformed connection string or a rejected secret can never
    appear in startup/crash output.
    """
    try:
        return Settings()
    except ValidationError as exc:
        fields = ", ".join(".".join(str(part) for part in error["loc"]) for error in exc.errors())
        raise ConfigurationError(
            f"Invalid application configuration for: {fields}. "
            "Check the corresponding environment variables; values are not shown."
        ) from None


settings = get_settings()
