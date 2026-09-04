"""CloudPet FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.errors import install_error_handlers
from app.api.health import router as health_router
from app.api.middleware import RequestContextMiddleware
from app.api.router import api_router
from app.core.config import Settings, settings
from app.core.logging import configure_logging


def create_app(*, settings: Settings = settings) -> FastAPI:
    """Build the CloudPet ASGI application.

    ``settings`` defaults to the process-wide configuration singleton; tests
    may pass a different :class:`~app.core.config.Settings` instance to build
    an app reflecting a different environment (e.g. to verify production-only
    behaviour) without mutating global state.
    """
    configure_logging(settings)

    # The interactive OpenAPI docs describe the full API surface (routes,
    # schemas, auth flows) -- keep them available for local/test/staging use,
    # but do not expose them to unauthenticated production traffic.
    docs_enabled = settings.ENVIRONMENT != "production"

    app = FastAPI(
        title="CloudPet API",
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
