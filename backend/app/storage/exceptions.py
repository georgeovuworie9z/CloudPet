"""Framework-independent exceptions for the storage layer.

Mapping these to HTTP responses is the responsibility of a consuming feature's
route layer, not this module.
"""

from __future__ import annotations


class StorageError(Exception):
    """Base class for storage errors."""


class StorageConfigurationError(StorageError):
    """Storage configuration is missing or invalid."""


class StorageOperationError(StorageError):
    """A storage operation failed.

    The message is deliberately generic. It never carries AWS error codes,
    request IDs, bucket names, object keys, credentials, or response details --
    those go to the log, not to the caller.
    """
