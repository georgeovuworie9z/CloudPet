"""Shared constrained field types for the API schema layer.

Kept in one module so the ``auth`` and ``user`` schemas normalise and bound
their inputs identically.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, EmailStr, StringConstraints


def _normalize_email(value: object) -> object:
    """Trim and lower-case an email before format validation.

    Runs as a ``BeforeValidator`` so ``George@Example.COM`` and
    ``  george@example.com  `` both validate to ``george@example.com``.
    Non-strings pass through untouched for ``EmailStr`` to reject.
    """
    if isinstance(value, str):
        return value.strip().lower()
    return value


NormalizedEmailStr = Annotated[EmailStr, BeforeValidator(_normalize_email)]
"""A valid email address, normalised to trimmed lower-case."""

NameStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
"""A name component: trimmed, non-empty, at most 100 characters."""

PhoneStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]
"""A phone number: trimmed, non-empty, at most 32 characters. Format is not enforced."""
