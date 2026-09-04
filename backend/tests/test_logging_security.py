"""Security/privacy tests for Step 3J logging: nothing sensitive ever reaches a log record.

Covers the "never log" list: passwords, password hashes, JWTs, Authorization
headers, presigned S3 URLs, and the email address of a failed login attempt.
"""

from __future__ import annotations

import logging
from typing import Any

import boto3
import pytest
from app.storage.s3 import S3Storage
from botocore.config import Config
from fastapi.testclient import TestClient
from moto import mock_aws

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PETS_URL = "/api/v1/pets"
AUTH_ME_URL = "/api/v1/auth/me"
PASSWORD = "s3cure-and-distinctive-passphrase-000"


def _register(client: TestClient, **overrides: object) -> dict[str, Any]:
    body: dict[str, object] = {
        "email": "george@example.com",
        "password": PASSWORD,
        "first_name": "George",
        "last_name": "Ovuworie",
    }
    body.update(overrides)
    response = client.post(REGISTER_URL, json=body)
    assert response.status_code == 201
    created: dict[str, object] = response.json()
    return created


def _all_record_text(records: list[logging.LogRecord]) -> str:
    """Every observable string representation of a batch of log records.

    Includes each record's ``__dict__`` (not just its formatted message) so a
    leak via a structured "extra" field is caught just as reliably as one in
    the message text.
    """
    parts: list[str] = []
    for record in records:
        parts.append(record.getMessage())
        parts.append(repr(record.__dict__))
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Passwords / password hashes
# --------------------------------------------------------------------------- #


def test_password_never_appears_in_any_log_record(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    _register(api_client)

    assert PASSWORD not in _all_record_text(caplog.records)


def test_password_hash_never_appears_in_any_log_record(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    created = _register(api_client)
    login = api_client.post(LOGIN_URL, json={"email": created["email"], "password": PASSWORD})
    assert login.status_code == 200

    text = _all_record_text(caplog.records)
    assert "$argon2id$" not in text
    assert "argon2" not in text.lower()


# --------------------------------------------------------------------------- #
# JWTs / Authorization headers
# --------------------------------------------------------------------------- #


def test_access_token_never_appears_in_any_log_record(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    created = _register(api_client)

    login = api_client.post(LOGIN_URL, json={"email": created["email"], "password": PASSWORD})
    token = login.json()["access_token"]

    api_client.get(AUTH_ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert token not in _all_record_text(caplog.records)


def test_authorization_header_never_appears_in_any_log_record(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    distinctive_token = "totally-distinctive-fake-token-value-123456"

    api_client.get(PETS_URL, headers={"Authorization": f"Bearer {distinctive_token}"})

    text = _all_record_text(caplog.records)
    assert distinctive_token not in text
    assert f"Bearer {distinctive_token}" not in text


# --------------------------------------------------------------------------- #
# Failed login: no identifying information
# --------------------------------------------------------------------------- #


def test_failed_login_does_not_log_the_attempted_email_or_password(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    response = api_client.post(
        LOGIN_URL,
        json={"email": "nobody-distinctive@example.com", "password": "wrong-password-value"},
    )

    assert response.status_code == 401
    text = _all_record_text(caplog.records)
    assert "nobody-distinctive@example.com" not in text
    assert "wrong-password-value" not in text


def test_successful_login_logs_info_with_user_id_only(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    created = _register(api_client)

    response = api_client.post(LOGIN_URL, json={"email": created["email"], "password": PASSWORD})

    assert response.status_code == 200
    auth_records = [
        r for r in caplog.records if r.name == "app.services.user" and r.levelno == logging.INFO
    ]
    assert len(auth_records) == 1
    assert auth_records[0].user_id == created["id"]  # type: ignore[attr-defined]
    assert created["email"] not in auth_records[0].getMessage()


def test_failed_login_logs_warning_with_no_identifying_information(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    created = _register(api_client)

    response = api_client.post(
        LOGIN_URL, json={"email": created["email"], "password": "definitely-wrong-password"}
    )

    assert response.status_code == 401
    auth_records = [
        r for r in caplog.records if r.name == "app.services.user" and r.levelno == logging.WARNING
    ]
    assert len(auth_records) == 1
    assert not hasattr(auth_records[0], "user_id")
    assert created["email"] not in auth_records[0].getMessage()


# --------------------------------------------------------------------------- #
# Presigned S3 URLs
# --------------------------------------------------------------------------- #


def test_presigned_url_is_never_logged_in_full(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    with mock_aws():
        client = boto3.client(
            "s3", region_name="us-east-1", config=Config(signature_version="s3v4")
        )
        client.create_bucket(Bucket="cloudpet-test-bucket")
        storage = S3Storage(bucket="cloudpet-test-bucket", region="us-east-1", client=client)

        url = storage.create_upload_url(key="pets/abc/images/img1", content_type="image/png")

    text = _all_record_text(caplog.records)
    assert url not in text
    assert "X-Amz-Signature" not in text
