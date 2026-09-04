"""Object-storage capability layer.

Feature-agnostic: nothing in this package knows about pets, owners, authorization,
or database rows. It moves bytes for opaque keys behind the
:class:`~app.storage.base.StorageService` protocol, using presigned URLs for the
direct client <-> S3 transfer.
"""

from __future__ import annotations

from app.storage.base import StorageService
from app.storage.exceptions import (
    StorageConfigurationError,
    StorageError,
    StorageOperationError,
)
from app.storage.s3 import S3Storage

__all__ = [
    "S3Storage",
    "StorageConfigurationError",
    "StorageError",
    "StorageOperationError",
    "StorageService",
]
