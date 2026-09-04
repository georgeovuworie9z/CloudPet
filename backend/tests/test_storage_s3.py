"""Behavioural tests for :class:`app.storage.s3.S3Storage`.

Uses moto (``@mock_aws``) -- no real AWS, no network, deterministic. Presigned
URL generation is a client-side botocore operation, so these assertions inspect
the signed URL rather than any S3 round-trip.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from app.core.config import Settings
from app.storage.base import StorageService
from app.storage.exceptions import StorageConfigurationError, StorageOperationError
from app.storage.s3 import S3Storage
from botocore.config import Config
from botocore.exceptions import ClientError
from moto import mock_aws

_BUCKET = "cloudpet-test-bucket"
_REGION = "us-east-1"
# Matches the SigV4 config S3Storage's own client uses (see app/storage/s3.py) --
# this fixture builds its client directly (to inject into S3Storage), so it must
# opt into the same signature version to produce comparable presigned URLs.
_SIGV4_CONFIG = Config(signature_version="s3v4")
_GENERIC_MESSAGE = "The storage operation could not be completed."

# An AWS error response full of detail that must never reach the caller.
_LEAKY_ERROR_RESPONSE = {
    "Error": {"Code": "AccessDenied", "Message": "arn:aws:s3:::secret-bucket denied"},
    "ResponseMetadata": {"RequestId": "REQ-1234567890", "HTTPStatusCode": 403},
}


@pytest.fixture
def s3_client() -> Iterator[Any]:
    with mock_aws():
        client: Any = boto3.client("s3", region_name=_REGION, config=_SIGV4_CONFIG)
        client.create_bucket(Bucket=_BUCKET)
        yield client


@pytest.fixture
def storage(s3_client: Any) -> S3Storage:
    return S3Storage(bucket=_BUCKET, region=_REGION, client=s3_client)


class _BoomClient:
    """A client whose every call raises a ``ClientError`` carrying AWS detail."""

    def generate_presigned_url(
        self, ClientMethod: str, *, Params: Mapping[str, str], ExpiresIn: int
    ) -> str:
        raise ClientError(_LEAKY_ERROR_RESPONSE, "GeneratePresignedUrl")

    def delete_object(self, *, Bucket: str, Key: str) -> Mapping[str, object]:
        raise ClientError(_LEAKY_ERROR_RESPONSE, "DeleteObject")


def _assert_scrubbed(message: str) -> None:
    assert message == _GENERIC_MESSAGE
    lowered = message.lower()
    for leak in ("accessdenied", "req-1234567890", "secret-bucket", "arn:aws", "clienterror"):
        assert leak not in lowered


# --------------------------------------------------------------------------- #
# Presigned upload URL
# --------------------------------------------------------------------------- #


def test_create_upload_url_is_generated_for_the_key(storage: S3Storage) -> None:
    url = storage.create_upload_url(key="pets/abc/images/img1", content_type="image/png")

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert _BUCKET in parsed.netloc or _BUCKET in parsed.path
    assert "pets/abc/images/img1" in parsed.path
    assert "X-Amz-Signature" in parse_qs(parsed.query)


def test_create_upload_url_binds_the_content_type(storage: S3Storage) -> None:
    url = storage.create_upload_url(key="pets/abc/images/img1", content_type="image/png")

    signed_headers = parse_qs(urlparse(url).query).get("X-Amz-SignedHeaders", [""])[0]
    assert "content-type" in signed_headers.lower()


def test_upload_url_expiry_is_within_the_ttl(storage: S3Storage) -> None:
    url = storage.create_upload_url(key="pets/abc/images/img1", content_type="image/png")

    expires = int(parse_qs(urlparse(url).query)["X-Amz-Expires"][0])
    assert 0 < expires <= 300


# --------------------------------------------------------------------------- #
# Presigned download URL
# --------------------------------------------------------------------------- #


def test_create_download_url_is_generated_for_the_key(storage: S3Storage) -> None:
    url = storage.create_download_url(key="pets/abc/images/img1")

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert _BUCKET in parsed.netloc or _BUCKET in parsed.path
    assert "pets/abc/images/img1" in parsed.path
    assert "X-Amz-Signature" in parse_qs(parsed.query)


def test_download_url_expiry_is_within_the_ttl(storage: S3Storage) -> None:
    url = storage.create_download_url(key="pets/abc/images/img1")

    expires = int(parse_qs(urlparse(url).query)["X-Amz-Expires"][0])
    assert 0 < expires <= 300


# --------------------------------------------------------------------------- #
# Delete
# --------------------------------------------------------------------------- #


def test_delete_removes_an_existing_object(storage: S3Storage, s3_client: Any) -> None:
    s3_client.put_object(Bucket=_BUCKET, Key="pets/a/images/x", Body=b"bytes")

    storage.delete(key="pets/a/images/x")

    listing = s3_client.list_objects_v2(Bucket=_BUCKET)
    assert listing.get("KeyCount", 0) == 0


def test_delete_missing_object_is_idempotent(storage: S3Storage) -> None:
    storage.delete(key="pets/a/images/never-existed")  # must not raise


# --------------------------------------------------------------------------- #
# Error translation / scrubbing
# --------------------------------------------------------------------------- #


def test_upload_url_operation_failure_becomes_storage_operation_error() -> None:
    storage = S3Storage(bucket="b", region=_REGION, client=_BoomClient())

    with pytest.raises(StorageOperationError) as exc_info:
        storage.create_upload_url(key="pets/a/images/x", content_type="image/png")

    _assert_scrubbed(str(exc_info.value))
    assert exc_info.value.__cause__ is None


def test_delete_operation_failure_becomes_storage_operation_error() -> None:
    storage = S3Storage(bucket="b", region=_REGION, client=_BoomClient())

    with pytest.raises(StorageOperationError) as exc_info:
        storage.delete(key="pets/a/images/x")

    _assert_scrubbed(str(exc_info.value))
    assert exc_info.value.__cause__ is None


# --------------------------------------------------------------------------- #
# Object-key shape validation (not authorization)
# --------------------------------------------------------------------------- #


_UNSAFE_KEYS = [
    "",
    "/pets/x",
    "pets/../x",
    "pets//x",
    "pets\\x",
    "pets/\x00x",
    "pets/x\ny",
    "pets/x y",
    "pets/x?y",
    "pets/x#y",
    "x" * (1024 + 1),
]

_VALID_KEYS = [
    "pets/123/images/abc",
    "pets/1a2b-3c4d/images/xyz-789",
    "a_b.c!d*e'f(g)h-i",
    "single",
    "x" * 1024,
]


@pytest.mark.parametrize("bad_key", _UNSAFE_KEYS)
def test_unsafe_keys_are_rejected_before_calling_s3(storage: S3Storage, bad_key: str) -> None:
    with pytest.raises(ValueError):
        storage.create_upload_url(key=bad_key, content_type="image/png")
    with pytest.raises(ValueError):
        storage.create_download_url(key=bad_key)
    with pytest.raises(ValueError):
        storage.delete(key=bad_key)


@pytest.mark.parametrize("good_key", _VALID_KEYS)
def test_valid_keys_pass_shape_validation(storage: S3Storage, good_key: str) -> None:
    url = storage.create_upload_url(key=good_key, content_type="image/png")
    assert url.startswith("https://")


# --------------------------------------------------------------------------- #
# Configuration gating
# --------------------------------------------------------------------------- #


def _make_settings(
    monkeypatch: pytest.MonkeyPatch, *, bucket: str | None, region: str | None
) -> Settings:
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    if bucket is not None:
        monkeypatch.setenv("S3_BUCKET_NAME", bucket)
    if region is not None:
        monkeypatch.setenv("AWS_REGION", region)
    return Settings()


def test_from_settings_builds_storage_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(monkeypatch, bucket="cloudpet-images", region=_REGION)

    assert isinstance(S3Storage.from_settings(settings), S3Storage)


def test_from_settings_without_bucket_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _make_settings(monkeypatch, bucket=None, region=_REGION)

    with pytest.raises(StorageConfigurationError):
        S3Storage.from_settings(settings)


def test_from_settings_without_region_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _make_settings(monkeypatch, bucket="cloudpet-images", region=None)

    with pytest.raises(StorageConfigurationError):
        S3Storage.from_settings(settings)


# --------------------------------------------------------------------------- #
# Protocol conformance
# --------------------------------------------------------------------------- #


def test_s3storage_satisfies_the_storage_service_protocol(storage: S3Storage) -> None:
    service: StorageService = storage
    assert isinstance(service, StorageService)
