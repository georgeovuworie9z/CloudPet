"""Unit tests for Argon2id password hashing (no database)."""

from __future__ import annotations

from app.core.security import hash_password, needs_rehash, verify_password


def test_hash_is_argon2id_and_verifies() -> None:
    hashed = hash_password("correct-horse-battery-staple")

    assert hashed.startswith("$argon2id$")
    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_rejects_wrong_password() -> None:
    hashed = hash_password("the-right-passphrase")

    assert verify_password("the-wrong-passphrase", hashed) is False


def test_hash_uses_a_random_salt() -> None:
    first = hash_password("identical-input-value")
    second = hash_password("identical-input-value")

    assert first != second


def test_verify_returns_false_for_malformed_hash() -> None:
    assert verify_password("anything", "not-a-real-hash") is False


def test_hash_fits_user_password_hash_column() -> None:
    hashed = hash_password("x" * 128)

    assert len(hashed) <= 255


def test_needs_rehash_is_false_for_current_parameters() -> None:
    assert needs_rehash(hash_password("freshly-hashed-value")) is False


def test_needs_rehash_is_true_for_unidentifiable_hash() -> None:
    assert needs_rehash("not-a-real-hash") is True
