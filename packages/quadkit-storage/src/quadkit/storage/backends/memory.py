"""In-memory storage driver for testing"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.infra.storage import FileInfo, Uploadable
from quadkit.contracts.infra.storage import UploadOptions as UploadOptionsContract
from quadkit.logging import get_logger
from quadkit.storage.backends.base import AbstractDriver
from quadkit.storage.exceptions import (
    StorageFileNotFoundError,
    StorageUnsupportedOperationError,
)

logger = get_logger(__name__)


class MemoryDriver(AbstractDriver):
    """In-memory storage driver using a dictionary"""

    def __init__(self) -> None:
        # Store file records as dicts with typed values so mypy can reason about returns
        self._storage: dict[str, dict[str, Any]] = {}

    async def upload(
        self,
        path: str,
        data: Uploadable,
        content_type: UploadOptionsContract | str | None = None,
        **options: Any,
    ) -> FileInfo:
        """Upload data to memory storage"""
        # Support passing UploadOptions as the third positional argument
        if isinstance(content_type, UploadOptionsContract):
            opts = content_type
            content_type = opts.content_type
            extra_opts: dict[str, Any] = {}
            if opts.metadata:
                extra_opts["metadata"] = opts.metadata
            if opts.public:
                extra_opts["public"] = True
            if opts.cache_control:
                extra_opts["cache_control"] = opts.cache_control
            if options:
                extra_opts.update(options)
            options = extra_opts

        # Handle different data types
        content: bytes
        if isinstance(data, bytes):
            content = data
        elif isinstance(data, str):
            content = data.encode("utf-8")
        elif hasattr(data, "read"):  # BinaryIO
            raw = data.read()
            if isinstance(raw, str):
                content = raw.encode("utf-8")
            elif isinstance(raw, bytearray):
                content = bytes(raw)
            elif isinstance(raw, bytes):
                content = raw
            else:
                raise ValueError(f"Unsupported read() return type: {type(raw)}")
        elif hasattr(data, "__aiter__"):  # AsyncIterator
            chunks: list[bytes] = []
            async for chunk in data:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                chunks.append(chunk)
            content = b"".join(chunks)
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")

        # Store file info with precise types for mypy
        now: datetime = datetime.now(UTC)
        size: int = len(content)
        resolved_content_type: str = (
            content_type if content_type else "application/octet-stream"
        )
        metadata: dict[str, str] | None = (
            options.get("metadata") if options.get("metadata") else {}
        )

        self._storage[path] = {
            "content": content,
            "size": size,
            "content_type": resolved_content_type,
            "last_modified": now,
            "metadata": metadata,
        }

        return FileInfo(
            path=path,
            size=size,
            content_type=resolved_content_type,
            last_modified=now,
            etag=f'"{hash(content):x}"',
            metadata=metadata,
        )

    async def download(self, path: str) -> bytes:
        """Download file content from memory"""
        if path not in self._storage:
            raise StorageFileNotFoundError(
                f"File not found: {path!r}",
                details={"path": path},
                hint="Ensure the file was uploaded before downloading.",
            )
        return cast("bytes", self._storage[path]["content"])

    async def stream(
        self, path: str, chunk_size: int = 8192
    ) -> AsyncGenerator[bytes, None]:
        """Stream file content from memory"""
        if path not in self._storage:
            raise StorageFileNotFoundError(
                f"File not found: {path!r}",
                details={"path": path},
                hint="Ensure the file was uploaded before streaming.",
            )

        content = cast("bytes", self._storage[path]["content"])
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

    async def delete(self, path: str) -> None:
        """Delete file from memory"""
        if path not in self._storage:
            raise StorageFileNotFoundError(
                f"File not found: {path!r}",
                details={"path": path},
                hint="Verify the file exists before deleting.",
            )
        del self._storage[path]

    async def exists(self, path: str) -> bool:
        """Check if file exists in memory"""
        return path in self._storage

    async def info(self, path: str) -> FileInfo:
        """Get file info from memory"""
        if path not in self._storage:
            raise StorageFileNotFoundError(
                f"File not found: {path!r}",
                details={"path": path},
                hint="Verify the file exists.",
            )

        file_info = self._storage[path]
        return FileInfo(
            path=path,
            size=file_info["size"],
            content_type=file_info["content_type"],
            last_modified=file_info["last_modified"],
            etag=f'"{hash(file_info["content"]):x}"',
            metadata=file_info["metadata"],
        )

    async def list(self, prefix: str = "") -> AsyncGenerator[FileInfo, None]:
        """List files with prefix from memory"""
        for path, file_info in self._storage.items():
            if path.startswith(prefix):
                yield FileInfo(
                    path=path,
                    size=file_info["size"],
                    content_type=file_info["content_type"],
                    last_modified=file_info["last_modified"],
                    etag=f'"{hash(file_info["content"]):x}"',
                    metadata=file_info["metadata"],
                )

    async def get_url(self, path: str) -> str:
        """Get URL for memory storage (not applicable)"""
        return f"memory://{path}"

    async def get_presigned_url(
        self,
        path: str,
        expires_in: timedelta = timedelta(hours=1),
        method: str = "GET",
    ) -> str:
        """Raise StorageUnsupportedOperationError — not applicable to in-memory storage.

        The in-memory driver has no network endpoint, so presigned URLs
        cannot be generated.  Use a cloud-backed driver (S3, GCS, Azure)
        for presigned URL support.

        Args:
            path: File path that would have been signed.
            expires_in: Ignored.
            method: Ignored.

        Raises:
            StorageUnsupportedOperationError: Always — presigned URLs are not
                supported by the in-memory driver.
        """
        raise StorageUnsupportedOperationError(
            "Presigned URLs are not supported by the in-memory storage driver.",
            details={"path": path, "driver": "memory"},
            hint="Use a cloud-backed driver (S3, GCS, or Azure) to generate presigned URLs.",
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check on memory storage"""
        import time

        start_time = time.time()
        latency_ms = (time.time() - start_time) * 1000
        return HealthCheckResult(
            component="storage.memory",
            status=HealthStatus.HEALTHY,
            details={
                "driver": "memory",
                "file_count": len(self._storage),
                "total_size": sum(f["size"] for f in self._storage.values()),
            },
            duration_ms=latency_ms,
        )
