"""Storage blob protocol class definitions."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.core.provider import ProviderProtocol
from quadkit.contracts.infra.storage.models import FileInfo, Uploadable, UploadOptions

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.core import HealthCheckResult


@runtime_checkable
class BlobStoreProtocol(Protocol):
    """Protocol for blob storage operations.

    This interface defines the contract for file storage backends
    (S3, GCS, Azure Blob, local filesystem, etc.).

    Example:
        ```python
        class S3BlobStore:
            async def upload(self, path: str, data: bytes, **options) -> FileInfo:
                await self._client.put_object(Bucket=self._bucket, Key=path, Body=data)
                return FileInfo(path=path, size=len(data), ...)
        ```
    """

    async def upload(
        self,
        path: str,
        data: Uploadable,
        content_type: UploadOptions | str | None = None,
        **options: Any,
    ) -> FileInfo:
        """Upload data to the storage backend.

        Args:
            path: Storage path/key.
            data: File content as bytes, text, file-like object, or async iterator.
            content_type: MIME type or :class:`UploadOptions` for metadata and
                other upload settings.
            **options: Additional upload options.

        Returns:
            FileInfo with path, size, and metadata.
        """
        ...

    async def download(self, path: str) -> bytes:
        """Download file content into memory.

        Args:
            path: Storage path/key.

        Returns:
            File content as bytes.
        """
        ...

    def stream(self, path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file content (memory efficient).

        Args:
            path: Storage path/key.
            chunk_size: Size of each chunk in bytes.

        Yields:
            File content in chunks.
        """
        ...

    async def delete(self, path: str) -> None:
        """Delete a file.

        Args:
            path: Storage path/key.
        """
        ...

    async def exists(self, path: str) -> bool:
        """Check if file exists.

        Args:
            path: Storage path/key.

        Returns:
            True if file exists.
        """
        ...

    async def info(self, path: str) -> FileInfo:
        """Get file metadata.

        Args:
            path: Storage path/key.

        Returns:
            FileInfo with size, content_type, etc.
        """
        ...

    def list(self, prefix: str = "") -> AsyncIterator[FileInfo]:
        """List files with a given prefix.

        Args:
            prefix: Path prefix to filter by.

        Yields:
            FileInfo for each matching file.
        """
        ...

    async def get_url(self, path: str) -> str:
        """Get public URL (if applicable).

        Args:
            path: Storage path/key.

        Returns:
            Public URL string.
        """
        ...

    async def get_presigned_url(
        self,
        path: str,
        expires_in: timedelta = timedelta(hours=1),
        method: str = "GET",
    ) -> str:
        """Get a temporary secure URL.

        Args:
            path: Storage path/key.
            expires_in: URL validity window as a :class:`~datetime.timedelta`
                (default one hour).  Pass ``timedelta(minutes=5)`` for secure
                short-lived downloads or ``timedelta(hours=24)`` for bulk exports.
            method: HTTP method (GET or PUT).

        Returns:
            Presigned URL string.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check.

        Returns:
            Structured health check result.
        """
        ...


@runtime_checkable
class StorageDriverProtocol(Protocol):
    """Protocol for storage driver implementations.

    This interface extends BlobStoreProtocol with driver-specific operations
    such as copy, move, and batch operations. Storage drivers
    (S3, GCS, Azure, local filesystem, memory) should implement this
    protocol or extend BaseDriver.

    Example:
        ```python
        class S3Driver:
            async def copy(self, source: str, destination: str) -> None:
                await self._client.copy_object(Bucket=self._bucket, Key=destination, CopySource=source)

            async def move(self, source: str, destination: str) -> None:
                await self.copy(source, destination)
                await self.delete(source)
        ```
    """

    async def copy(self, source: str, destination: str) -> None:
        """Copy a file from source to destination.

        Args:
            source: Source storage path/key.
            destination: Destination storage path/key.
        """
        ...

    async def move(self, source: str, destination: str) -> None:
        """Move a file from source to destination.

        Args:
            source: Source storage path/key.
            destination: Destination storage path/key.
        """
        ...

    async def copy_batch(self, operations: list[tuple[str, str]]) -> list[str]:
        """Execute batch copy operations.

        Args:
            operations: List of (source, destination) tuples.

        Returns:
            List of destination paths that were copied.
        """
        ...


@runtime_checkable
class StorageProviderProtocol(ProviderProtocol, Protocol):
    """Protocol for storage providers.

    Storage providers are responsible for setting up blob stores,
    file systems, and CDN integration.
    """


__all__ = [
    "BlobStoreProtocol",
    "FileInfo",
    "StorageDriverProtocol",
    "StorageProviderProtocol",
]
