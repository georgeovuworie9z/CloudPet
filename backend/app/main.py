"""CloudPet FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="CloudPet API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.include_router(health_router)
    return app


app = create_app()
