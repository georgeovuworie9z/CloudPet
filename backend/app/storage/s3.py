"""S3-backed implementation of :class:`~app.storage.base.StorageService`.

Presigned ``PUT`` / ``GET`` for direct client <-> S3 transfer, plus delete.
Feature-agnostic: keys are opaque strings and are validated for *shape* only,
never for ownership. Credentials come from boto3's default provider chain --
never from constructor arguments or application settings.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.exceptions import StorageConfigurationError, StorageOperationError

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger("app.storage")

_PRESIGNED_URL_TTL_SECONDS = 300
_MAX_KEY_BYTES = 1024
_ALLOWED_KEY_PATTERN = re.compile(r"^[A-Za-z0-9!_.*'()/-]+$")
_CONTROL_CHARS = frozenset(map(chr, range(0x20))) | {chr(0x7F)}
_GENERIC_OPERATION_ERROR = "The storage operation could not be completed."


class S3ClientLike(Protocol):
    """The minimal slice of the boto3 S3 client that :class:`S3Storage` uses."""

    def generate_presigned_url(
        self,
        ClientMethod: str,
        *,
        Params: Mapping[str, str],
        ExpiresIn: int,
    ) -> str: ...

    def delete_object(self, *, Bucket: str, Key: str) -> Mapping[str, object]: ...


class S3Storage:
    """Store objects in a private S3 bucket, exchanging bytes via presigned URLs."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        client: S3ClientLike | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._region = region
        if client is None:
            client = _build_client(region=region, endpoint_url=endpoint_url)
        self._client: S3ClientLike = client

    @classmethod
    def from_settings(cls, settings: Settings) -> S3Storage:
        """Build an :class:`S3Storage` from application settings.

        Raises :class:`StorageConfigurationError` if ``S3_BUCKET_NAME`` or
        ``AWS_REGION`` is unset. The application boots without S3 configuration,
        so this failure only surfaces when storage is actually constructed.
        """
        bucket = settings.S3_BUCKET_NAME
        region = settings.AWS_REGION
        if not bucket or not region:
            raise StorageConfigurationError("Object storage is not configured.")
        return cls(bucket=bucket, region=region, endpoint_url=settings.S3_ENDPOINT_URL)

    def create_upload_url(self, *, key: str, content_type: str) -> str:
        """Presigned ``PUT`` URL for ``key`` (expires in 5 minutes).

        ``content_type`` is bound into the request, so the client must ``PUT``
        with exactly this ``Content-Type``.
        """
        self._validate_key(key)
        return self._presigned_url(
            "put_object",
            {"Bucket": self._bucket, "Key": key, "ContentType": content_type},
        )

    def create_download_url(self, *, key: str) -> str:
        """Presigned ``GET`` URL for ``key`` (expires in 5 minutes)."""
        self._validate_key(key)
        return self._presigned_url("get_object", {"Bucket": self._bucket, "Key": key})

    def delete(self, *, key: str) -> None:
        """Delete ``key``. S3 delete is idempotent, so a missing key is not an error."""
        self._validate_key(key)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError):
            logger.exception("S3 delete_object failed")
            raise StorageOperationError(_GENERIC_OPERATION_ERROR) from None

    def _presigned_url(self, client_method: str, params: Mapping[str, str]) -> str:
        try:
            url: str = self._client.generate_presigned_url(
                client_method,
                Params=params,
                ExpiresIn=_PRESIGNED_URL_TTL_SECONDS,
            )
        except (ClientError, BotoCoreError):
            logger.exception("S3 generate_presigned_url failed")
            raise StorageOperationError(_GENERIC_OPERATION_ERROR) from None
        return url

    @staticmethod
    def _validate_key(key: str) -> None:
        """Reject keys whose *shape* is unsafe. This is not an authorization check."""
        if not key:
            raise ValueError("Object key must not be empty.")
        if len(key.encode("utf-8")) > _MAX_KEY_BYTES:
            raise ValueError("Object key is too long.")
        if key.startswith("/"):
            raise ValueError("Object key must not start with '/'.")
        if ".." in key:
            raise ValueError("Object key must not contain '..'.")
        if "//" in key:
            raise ValueError("Object key must not contain '//'.")
        if "\\" in key:
            raise ValueError("Object key must not contain a backslash.")
        if any(char in _CONTROL_CHARS for char in key):
            raise ValueError("Object key must not contain control characters.")
        if _ALLOWED_KEY_PATTERN.fullmatch(key) is None:
            raise ValueError("Object key contains unsupported characters.")


def _build_client(*, region: str, endpoint_url: str | None) -> S3ClientLike:
    # boto3 otherwise defaults new S3 clients to the legacy SigV2 presigned-URL
    # style, which AWS has deprecated in most regions; SigV4 is required for
    # presigned URLs to actually work in production.
    client: S3ClientLike = boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint_url or None,
        config=Config(signature_version="s3v4"),
    )
    return client
