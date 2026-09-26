"""Base driver class for storage implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from datetime import timedelta
import mimetypes
from typing import TYPE_CHECKING, Any

from quadkit.contracts import BlobStoreProtocol
from quadkit.contracts.infra.storage import FileInfo, Uploadable, UploadOptions

if TYPE_CHECKING:
    from quadkit.contracts.core import HealthCheckResult


class AbstractDriver(ABC, BlobStoreProtocol):
    """Abstract base class for all storage drivers.

    Provides the canonical interface that every backend (local, S3, GCS, Azure,
    memory) must implement.  Extends the :class:`~quadkit.contracts.BlobStoreProtocol`
    protocol so any :class:`AbstractDriver` subclass satisfies the DI-registered
    contract type.
    """

    @staticmethod
    def _resolve_content_type(path: str, options: UploadOptions | None) -> str:
        """Resolve the MIME content type for an upload.

        Returns the explicit content type from *options* when provided;
        otherwise uses :mod:`mimetypes` to guess from the file extension.
        Falls back to ``"application/octet-stream"`` when guessing fails.

        Args:
            path: Destination storage path / key (used for extension guessing).
            options: Optional upload settings that may contain an explicit
                ``content_type``.

        Returns:
            A non-empty MIME type string.
        """
        if options and options.content_type:
            return options.content_type
        guessed, _ = mimetypes.guess_type(path)
        return guessed or "application/octet-stream"

    @staticmethod
    def _normalize_upload_options(
        content_type: UploadOptions | str | None,
        options: dict[str, Any],
    ) -> UploadOptions | None:
        """Normalize the positional options form and keyword options.

        ``UploadOptions`` is accepted as the third argument for parity with
        the public storage contract. Explicit keyword options win when both
        forms provide the same value.
        """
        if content_type is None and not options:
            return None
        if isinstance(content_type, UploadOptions):
            normalized: dict[str, Any] = {
                "content_type": content_type.content_type,
                "public": content_type.public,
                "metadata": content_type.metadata,
                "cache_control": content_type.cache_control,
            }
            normalized.update(options)
            return UploadOptions(**normalized)
        return UploadOptions(content_type=content_type, **options)

    @abstractmethod
    async def upload(
        self,
        path: str,
        data: Uploadable,
        content_type: UploadOptions | str | None = None,
        **options: Any,
    ) -> FileInfo:
        """Upload *data* to *path* and return metadata about the stored file.

        Args:
            path: Destination storage path / key.
            data: File content — bytes, str, BinaryIO, or AsyncIterator[bytes].
            content_type: Optional MIME type override.
            **options: Additional upload options (metadata, public, cache_control, etc.).

        Returns:
            :class:`~quadkit.contracts.infra.storage.FileInfo` with size, ETag, etc.
        """

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download the entire file at *path* into memory.

        Args:
            path: Storage path / key.

        Returns:
            Raw file bytes.
        """

    @abstractmethod
    async def stream(
        self,
        path: str,
        chunk_size: int = 8192,
    ) -> AsyncGenerator[bytes, None]:
        """Yield successive *chunk_size* byte chunks from *path*.

        Implementations **must** be async generators (``async def`` with
        ``yield``).  Callers iterate with ``async for chunk in driver.stream(path):``.

        Args:
            path: Storage path / key.
            chunk_size: Size of each yielded chunk in bytes.

        Yields:
            Raw byte chunks.
        """
        raise NotImplementedError
        yield b""  # type: ignore[unreachable]  # pragma: no cover — signature marker

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete the file at *path*.

        Args:
            path: Storage path / key.
        """

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Return ``True`` if *path* exists in the backend.

        Args:
            path: Storage path / key.
        """

    @abstractmethod
    async def info(self, path: str) -> FileInfo:
        """Return metadata for the file at *path*.

        Args:
            path: Storage path / key.

        Returns:
            :class:`~quadkit.contracts.infra.storage.FileInfo`.
        """

    @abstractmethod
    async def list(
        self,
        prefix: str = "",
    ) -> AsyncGenerator[FileInfo, None]:
        """Yield :class:`~quadkit.contracts.infra.storage.FileInfo` for every
        stored file whose key begins with *prefix*.

        Implementations **must** be async generators.  Callers iterate with
        ``async for fi in driver.list(prefix):``.

        Args:
            prefix: Key prefix to filter results.

        Yields:
            :class:`~quadkit.contracts.infra.storage.FileInfo` entries.
        """
        raise NotImplementedError
        yield FileInfo(  # type: ignore[unreachable]  # pragma: no cover — signature marker
            path="",
            size=0,
            content_type="",
            last_modified=__import__("datetime").datetime.min,
        )

    @abstractmethod
    async def get_url(self, path: str) -> str:
        """Return a public URL for *path* (if the backend supports it).

        Args:
            path: Storage path / key.
        """

    @abstractmethod
    async def get_presigned_url(
        self,
        path: str,
        expires_in: timedelta = timedelta(hours=1),
        method: str = "GET",
    ) -> str:
        """Return a short-lived signed URL for *path*.

        Args:
            path: Storage path / key.
            expires_in: Validity window as a :class:`~datetime.timedelta`
                (default one hour).  Different use cases can pass different
                windows — e.g. ``timedelta(minutes=5)`` for secure downloads,
                ``timedelta(hours=24)`` for bulk exports.
            method: HTTP verb the URL permits — ``"GET"`` or ``"PUT"``.
        """

    @abstractmethod
    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight connectivity check against the backend.

        Every concrete driver must implement this so the
        :class:`~quadkit.storage.providers.StorageProvider` can report
        storage health to the framework's health-check system.

        Returns:
            :class:`~quadkit.contracts.types.HealthCheckResult` with status and
            optional latency / error details.
        """

    # ── Optional enrichment methods (D6.1 / D10.1) ───────────────────────
    # These have default implementations so that existing drivers continue to
    # work without change.  Drivers that support these operations natively
    # should override them for better performance.

    async def write_stream(
        self,
        path: str,
        stream: AsyncGenerator[bytes, None],
        options: UploadOptions | None = None,
    ) -> FileInfo:
        """Stream-upload bytes from *stream* to *path*.

        The default implementation buffers the entire stream into memory and
        delegates to :meth:`upload`.  Drivers that support true streaming
        (S3 multipart, GCS resumable) should override this method.

        Args:
            path: Destination storage path / key.
            stream: Async generator that yields raw byte chunks.
            options: Optional upload settings.

        Returns:
            :class:`~quadkit.contracts.infra.storage.FileInfo` for the stored file.
        """
        chunks: list[bytes] = []
        async for chunk in stream:
            chunks.append(chunk)
        ct = options.content_type if options else None
        extra: dict[str, Any] = {}
        if options:
            if options.metadata:
                extra["metadata"] = options.metadata
            if options.public:
                extra["public"] = True
            if options.cache_control:
                extra["cache_control"] = options.cache_control
        return await self.upload(path, b"".join(chunks), ct, **extra)

    async def copy(self, src: str, dst: str) -> FileInfo:
        """Copy the file at *src* to *dst* within the same backend.

        The default implementation downloads and re-uploads the file.
        Drivers that support server-side copy should override this.

        Args:
            src: Source path.
            dst: Destination path.

        Returns:
            :class:`~quadkit.contracts.infra.storage.FileInfo` for the new file.
        """
        data = await self.download(src)
        src_info = await self.info(src)
        return await self.upload(dst, data, src_info.content_type)

    async def move(self, src: str, dst: str) -> FileInfo:
        """Move the file at *src* to *dst* within the same backend.

        Equivalent to :meth:`copy` followed by :meth:`delete`.

        Args:
            src: Source path.
            dst: Destination path.

        Returns:
            :class:`~quadkit.contracts.infra.storage.FileInfo` for the file at its
            new location.
        """
        info = await self.copy(src, dst)
        await self.delete(src)
        return info
