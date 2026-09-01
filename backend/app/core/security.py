"""Password hashing.

Argon2id via ``pwdlib``. Password-strength rules (length bounds, allowed
characters, ...) are a validation concern and are enforced in the API schema
layer, not here. This module only turns a plaintext string into a stored hash
and checks a candidate against one.
"""

from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher

_argon2_hasher = Argon2Hasher()
_password_hash = PasswordHash((_argon2_hasher,))


def hash_password(password: str) -> str:
    """Return an Argon2id hash (encoded string) for ``password``."""
    return _password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return ``True`` iff ``password`` matches ``hashed_password``.

    A malformed or unrecognised ``hashed_password`` yields ``False`` rather than
    raising, so callers can treat "bad password" and "bad stored hash" alike.
    """
    try:
        return _password_hash.verify(password, hashed_password)
    except UnknownHashError:
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Return ``True`` if ``hashed_password`` should be replaced.

    True when the hash was produced with weaker Argon2 parameters than the
    current configuration, or when it is not a recognisable Argon2 hash at all
    (in which case the caller should re-hash on the next successful login).
    """
    if not _argon2_hasher.identify(hashed_password):
        return True
    return _argon2_hasher.check_needs_rehash(hashed_password)
