"""Domain exceptions raised by the service layer.

These are plain, framework-independent exceptions. Mapping them to HTTP
responses is the responsibility of the (future) route layer, not this module.
"""

from __future__ import annotations


class UserServiceError(Exception):
    """Base class for all user service/domain errors."""


class DuplicateEmailError(UserServiceError):
    """Registration was attempted with an email that already exists."""


class UserNotFoundError(UserServiceError):
    """A user lookup that was required to succeed found no matching row."""


class InvalidCredentialsError(UserServiceError):
    """Authentication failed.

    Raised identically whether the email is unknown, the password is wrong, or
    the account is inactive, so callers cannot tell the cases apart.
    """


class InvalidProfileUpdateError(UserServiceError):
    """A profile update supplied a value that is not acceptable.

    Currently this means an explicit ``null`` for ``first_name`` or
    ``last_name``, which are ``NOT NULL`` columns.
    """
