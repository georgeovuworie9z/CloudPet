"""CloudPet FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.errors import install_error_handlers
from app.api.health import router as health_router
from app.api.middleware import RequestContextMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging(settings)

    app = FastAPI(
        title="CloudPet API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
