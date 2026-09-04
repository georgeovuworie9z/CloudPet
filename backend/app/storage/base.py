"""The storage capability interface.

``StorageService`` is a structural protocol, so callers depend on the behaviour
rather than on boto3 or any particular backend. Implementations know nothing
about pets, owners, or authorization; constructing safe, server-controlled keys
and enforcing ownership are the caller's responsibility.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageService(Protocol):
    """Presigned-URL object storage for opaque keys."""

    def create_upload_url(self, *, key: str, content_type: str) -> str:
        """Return a short-lived presigned URL the client can ``PUT`` ``key`` to.

        ``content_type`` is bound into the signature: the client's ``PUT`` must
        send exactly this ``Content-Type``.
        """
        ...

    def create_download_url(self, *, key: str) -> str:
        """Return a short-lived presigned URL the client can ``GET`` ``key`` from."""
        ...

    def delete(self, *, key: str) -> None:
        """Delete ``key``. Deleting a key that does not exist is not an error."""
        ...
