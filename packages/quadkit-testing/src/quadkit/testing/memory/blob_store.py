"""In-memory blob store for testing and development.

Provides a lightweight, dict-backed :class:`InMemoryBlobStore` that
satisfies the ``BlobStoreProtocol`` protocol without any external dependencies.
Suitable for unit tests, local development, and any scenario where
file persistence is not required.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, BinaryIO

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass
class FileInfo:
    """Minimal file metadata returned by :class:`InMemoryBlobStore`."""

    path: str
    size: int
    content_type: str
    last_modified: datetime


class InMemoryBlobStore:
    """In-memory implementation of the ``BlobStoreProtocol`` protocol.

    Stores file content in a plain dict. No persistence between runs.
    Suitable for unit tests and local development only.

    Example::

        store = InMemoryBlobStore()
        info = await store.upload("reports/q1.pdf", b"PDF content")
        assert await store.exists("reports/q1.pdf")
        raw = await store.download("reports/q1.pdf")
    """

    def __init__(self) -> None:
        self._files: dict[str, tuple[bytes, str, datetime]] = {}

    async def upload(
        self,
        path: str,
        data: bytes | BinaryIO | AsyncIterator[bytes],
        content_type: str | None = None,
        **options: Any,
    ) -> FileInfo:
        """Upload file content into the in-memory store.

        Args:
            path: Storage path/key.
            data: File content as bytes, file-like object, or async iterator.
            content_type: Optional MIME type. Defaults to ``application/octet-stream``.
            **options: Ignored; present for protocol compatibility.

        Returns:
            :class:`FileInfo` with path, size, content_type, and last_modified.
        """
        if isinstance(data, bytes):
            content = data
        elif hasattr(data, "read"):
            raw = data.read()
            content = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        else:
            chunks: list[bytes] = []
            async for chunk in data:
                chunks.append(
                    chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
                )
            content = b"".join(chunks)

        mime = content_type or "application/octet-stream"
        now = datetime.now(UTC)
        self._files[path] = (content, mime, now)
        return FileInfo(
            path=path, size=len(content), content_type=mime, last_modified=now
        )

    async def download(self, path: str) -> bytes:
        """Download file content from the in-memory store.

        Args:
            path: Storage path/key.

        Returns:
            File content as bytes.

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        if path not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        return self._files[path][0]

    async def stream(self, path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file content in chunks.

        Args:
            path: Storage path/key.
            chunk_size: Bytes per chunk.

        Yields:
            Content in successive chunks.
        """
        content = await self.download(path)
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

    async def delete(self, path: str) -> None:
        """Delete a file from the store.

        Args:
            path: Storage path/key.
        """
        self._files.pop(path, None)

    async def exists(self, path: str) -> bool:
        """Check whether a path exists in the store.

        Args:
            path: Storage path/key.

        Returns:
            True if the file exists, False otherwise.
        """
        return path in self._files

    async def info(self, path: str) -> FileInfo:
        """Return metadata for a stored file.

        Args:
            path: Storage path/key.

        Returns:
            :class:`FileInfo` with path, size, content_type, and last_modified.

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        if path not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        content, content_type, last_modified = self._files[path]
        return FileInfo(
            path=path,
            size=len(content),
            content_type=content_type,
            last_modified=last_modified,
        )

    async def get_presigned_url(
        self,
        path: str,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        """Return a stub presigned URL (not a real signed URL).

        Args:
            path: Storage path/key.
            expires_in: Ignored; present for protocol compatibility.
            method: Ignored; present for protocol compatibility.

        Returns:
            A fake URL of the form ``/files/{path}?token=mock``.
        """
        return f"/files/{path}?token=mock"

    async def get_url(self, path: str) -> str:
        """Return a URL-like reference for a stored file.

        Args:
            path: Storage path/key.

        Returns:
            A non-empty string URL of the form ``/files/{path}?token=mock``.
        """
        return f"/files/{path}?token=mock"

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        """List stored paths matching a prefix.

        Args:
            prefix: Only paths starting with this prefix are yielded.

        Yields:
            Stored path strings in insertion order.
        """
        for path in list(self._files):
            if path.startswith(prefix):
                yield path

    async def health_check(self, timeout: float = 5.0) -> Any:
        """Return a healthy health-check result.

        Args:
            timeout: Ignored; present for protocol compatibility.

        Returns:
            A :class:`~quadkit.contracts.core.health.HealthCheckResult`
            with ``status`` set to healthy.
        """
        from quadkit.contracts.core.health import HealthCheckResult, HealthStatus

        return HealthCheckResult(
            component="in-memory-blob-store",
            status=HealthStatus.HEALTHY,
            message="in-memory blob store available",
        )

    def clear(self) -> None:
        """Remove all stored files (useful for test teardown)."""
        self._files.clear()
