"""Authentication request/response schemas.

These models only validate the *shape* of the payloads. Password hashing, token
issuing, and persistence live in the security and service layers.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.fields import NameStr, NormalizedEmailStr, PhoneStr

# Password policy for CloudPet: length only, no character-class rules.
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


class UserCreate(BaseModel):
    """Registration payload. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    email: NormalizedEmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    first_name: NameStr
    last_name: NameStr
    phone: PhoneStr | None = None


class LoginRequest(BaseModel):
    """Login payload. Unknown fields are rejected.

    The password is only checked for presence here; it is verified against the
    stored hash in the service layer.
    """

    model_config = ConfigDict(extra="forbid")

    email: NormalizedEmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Access-token response body.

    Serialises to ``{"access_token": "...", "token_type": "bearer"}``.
    """

    access_token: str
    token_type: str = "bearer"
