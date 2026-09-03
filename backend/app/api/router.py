"""Aggregate router for the versioned API, mounted at ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import auth, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
