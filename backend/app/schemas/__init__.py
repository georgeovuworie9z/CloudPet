"""Pydantic v2 API schema layer for the CloudPet HTTP API."""

from __future__ import annotations

from app.schemas.auth import LoginRequest, TokenResponse, UserCreate
from app.schemas.pet import PetCreate, PetResponse, PetUpdate
from app.schemas.user import UserResponse, UserUpdate

__all__ = [
    "LoginRequest",
    "PetCreate",
    "PetResponse",
    "PetUpdate",
    "TokenResponse",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
]
