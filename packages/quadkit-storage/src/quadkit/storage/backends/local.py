"""Local file system storage driver with atomic upload support"""

from __future__ import annotations

import asyncio

# Import formatting handled intentionally to match project grouping
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Any, cast

import aiofiles

from quadkit import serialization
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.infra.storage import FileInfo, Uploadable
from quadkit.contracts.infra.storage import UploadOptions as UploadOptionsContract
from quadkit.logging import get_logger
from quadkit.storage.backends.base import AbstractDriver
from quadkit.storage.exceptions import (
    StorageError,
    StorageFileNotFoundError,
    StorageUnsupportedOperationError,
)
from quadkit.storage.lib.content_type import get_content_type
from quadkit.storage.lib.paths import normalize_path

logger = get_logger(__name__)


class LocalDriver(AbstractDriver):
    """Local file system storage driver"""

    _METADATA_DIR = ".quadkit-metadata"

    def __init__(
        self,
        root_dir: str = "./storage",
        base_url: str = "http://localhost:8000/storage",
    ):
        self.root_dir = Path(root_dir).resolve()
        self.base_url = base_url.rstrip("/")

    def _get_full_path(self, path: str) -> Path:
        """Get the full path for a storage path, with security checks"""
        # Normalize path to prevent directory traversal
        normalized_path = normalize_path(path)
        if normalized_path == self._METADATA_DIR or normalized_path.startswith(
            f"{self._METADATA_DIR}/"
        ):
            raise StorageError(
                f"Invalid path: {path!r}",
                details={"path": path, "root_dir": str(self.root_dir)},
                hint="The QuadKit metadata namespace is reserved for storage-driver internals.",
            )

        # Check for directory traversal attempts
        if ".." in normalized_path.split("/"):
            raise StorageError(
                f"Invalid path: {path!r}",
                details={"path": path, "root_dir": str(self.root_dir)},
                hint="Paths must not contain '..' components. Use relative paths only.",
            )

        # Ensure path doesn't start with /
        if normalized_path.startswith("/"):
            normalized_path = normalized_path[1:]

        full_path = self.root_dir / normalized_path

        # Ensure the file is within the root directory
        try:
            full_path.resolve().relative_to(self.root_dir.resolve())
        except ValueError:
            raise StorageError(
                f"Path outside storage root: {path!r}",
                details={"path": path, "root_dir": str(self.root_dir)},
                hint=f"Paths must be within the storage root {str(self.root_dir)!r}. Directory traversal is not permitted.",
            ) from None

        return full_path

    def _metadata_path(self, full_path: Path) -> Path:
        """Return the hidden sidecar path for an already-validated file."""
        relative = full_path.relative_to(self.root_dir)
        return (
            self.root_dir
            / self._METADATA_DIR
            / relative.parent
            / f"{relative.name}.json"
        )

    async def _write_metadata(self, full_path: Path, record: dict[str, Any]) -> None:
        """Persist content type and caller metadata atomically beside the store."""
        metadata_path = self._metadata_path(full_path)
        await asyncio.to_thread(metadata_path.parent.mkdir, parents=True, exist_ok=True)
        fd, temp_path_str = await asyncio.to_thread(
            tempfile.mkstemp,
            dir=str(metadata_path.parent),
            prefix=".metadata_",
            suffix=".tmp",
        )
        temp_path = Path(temp_path_str)
        try:
            await asyncio.to_thread(os.close, fd)
            async with aiofiles.open(temp_path, "wb") as stream:
                await stream.write(serialization.dumps(record))
            await asyncio.to_thread(temp_path.replace, metadata_path)
        except Exception:
            if await asyncio.to_thread(temp_path.exists):
                await asyncio.to_thread(temp_path.unlink)
            raise

    async def _read_metadata(self, full_path: Path) -> dict[str, Any] | None:
        """Read a file's sidecar when present; malformed sidecars fail soft."""
        metadata_path = self._metadata_path(full_path)
        if not await asyncio.to_thread(metadata_path.is_file):
            return None
        try:
            async with aiofiles.open(metadata_path, "rb") as stream:
                payload = await stream.read()
            record = serialization.loads(payload)
            return record if isinstance(record, dict) else None
        except Exception:
            logger.exception("storage.local.metadata_read_failed", path=str(full_path))
            return None

    async def _delete_metadata(self, full_path: Path) -> None:
        """Remove a sidecar and its empty parent directories."""
        metadata_path = self._metadata_path(full_path)
        if await asyncio.to_thread(metadata_path.exists):
            await asyncio.to_thread(metadata_path.unlink)
        metadata_root = self.root_dir / self._METADATA_DIR
        parent = metadata_path.parent
        while parent not in {metadata_root, self.root_dir}:
            try:
                await asyncio.to_thread(parent.rmdir)
            except OSError:
                break
            parent = parent.parent
        if parent == metadata_root and await asyncio.to_thread(parent.exists):
            try:
                await asyncio.to_thread(parent.rmdir)
            except OSError:
                pass

    async def upload(
        self,
        path: str,
        data: Uploadable,
        content_type: UploadOptionsContract | str | None = None,
        **options: Any,
    ) -> FileInfo:
        """Upload data to local file system with atomic write guarantee.

        Uses temp file + atomic rename to ensure no partial writes on failure.
        Optionally validates checksum if provided in options.
        """
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

        full_path = self._get_full_path(path)

        # Ensure parent directory exists
        await asyncio.to_thread(full_path.parent.mkdir, parents=True, exist_ok=True)

        # Create temp file in same directory for atomic rename (same filesystem)
        temp_fd, temp_path_str = await asyncio.to_thread(
            tempfile.mkstemp,
            dir=str(full_path.parent),
            prefix=".upload_",
            suffix=".tmp",
        )
        temp_path = Path(temp_path_str)
        renamed = False

        logger.debug(
            "upload: starting atomic upload path=%s temp=%s",
            path,
            temp_path_str,
        )

        try:
            # Close the file descriptor (we'll use aiofiles)
            await asyncio.to_thread(os.close, temp_fd)

            # Calculate checksum during write if validation requested
            opt_metadata = options.get("metadata") if options else None
            hasher = (
                hashlib.sha256()
                if (opt_metadata and opt_metadata.get("checksum"))
                else None
            )

            # Handle different data types and write to temp file
            if isinstance(data, bytes):
                if hasher:
                    hasher.update(data)
                async with aiofiles.open(temp_path, "wb") as f:
                    await f.write(data)

            elif isinstance(data, str):
                data_bytes = data.encode("utf-8")
                if hasher:
                    hasher.update(data_bytes)
                async with aiofiles.open(temp_path, "wb") as f:
                    await f.write(data_bytes)

            elif hasattr(data, "read"):  # BinaryIO
                content = data.read()
                if isinstance(content, str):
                    content = content.encode("utf-8")
                if hasher:
                    hasher.update(content)
                async with aiofiles.open(temp_path, "wb") as f:
                    await f.write(content)

            elif hasattr(data, "__aiter__"):  # AsyncIterator
                async with aiofiles.open(temp_path, "wb") as f:
                    async for chunk in data:
                        if isinstance(chunk, str):
                            chunk = chunk.encode("utf-8")
                        if hasher:
                            hasher.update(chunk)
                        await f.write(chunk)
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")

            # Validate checksum if provided
            if hasher and opt_metadata:
                expected_checksum = opt_metadata.get("checksum")
                if expected_checksum:
                    actual_checksum = hasher.hexdigest()
                    if actual_checksum != expected_checksum:
                        logger.error(
                            "upload: checksum mismatch path=%s expected=%s actual=%s",
                            path,
                            expected_checksum,
                            actual_checksum,
                        )
                        raise StorageError(
                            f"Checksum mismatch expected={expected_checksum} actual={actual_checksum}",
                        )

            # Atomic rename (only succeeds if temp file fully written)
            await asyncio.to_thread(temp_path.rename, full_path)
            renamed = True
            logger.info("upload: atomic upload complete path=%s", path)

            # Persist metadata separately from the content so a later info/list
            # call (or a new process) returns the same information as upload.
            stat = await asyncio.to_thread(full_path.stat)
            resolved_content_type = (
                content_type if content_type else get_content_type(str(full_path))
            )
            await self._write_metadata(
                full_path,
                {"content_type": resolved_content_type, "metadata": opt_metadata},
            )

            return FileInfo(
                path=path,
                size=stat.st_size,
                content_type=resolved_content_type,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                etag=f'"{stat.st_mtime:.0f}"',
                metadata=opt_metadata,
            )

        except Exception as e:
            # Cleanup: always delete temp file on any error
            logger.warning(
                "upload: error during upload, cleaning up temp file path=%s temp=%s error=%s",
                path,
                temp_path_str,
                str(e),
            )
            if await asyncio.to_thread(temp_path.exists):
                try:
                    await asyncio.to_thread(temp_path.unlink)
                except OSError:
                    logger.exception(
                        "upload: failed to cleanup temp file temp=%s",
                        temp_path_str,
                    )
            if renamed:
                try:
                    if await asyncio.to_thread(full_path.exists):
                        await asyncio.to_thread(full_path.unlink)
                    await self._delete_metadata(full_path)
                except OSError:
                    logger.exception(
                        "upload: failed to cleanup incomplete object path=%s", path
                    )
            # Re-raise StorageError directly, wrap others
            if isinstance(e, StorageError):
                raise
            raise StorageError(
                f"Upload failed for {path!r}: {e}",
                details={"path": path, "root_dir": str(self.root_dir)},
                hint="Check disk space and write permissions for the storage root directory.",
            ) from e

    async def download(self, path: str) -> bytes:
        """Download file content from local file system"""
        full_path = self._get_full_path(path)

        if not await asyncio.to_thread(full_path.exists):
            raise StorageFileNotFoundError(
                f"File not found: {path!r}",
                details={"path": path, "root_dir": str(self.root_dir)},
                hint=f"Ensure the file was uploaded before downloading. Check root_dir {str(self.root_dir)!r}.",
            )

        async with aiofiles.open(full_path, "rb") as f:
            return cast("bytes", await f.read())

    async def stream(
        self, path: str, chunk_size: int = 8192
    ) -> AsyncGenerator[bytes, None]:
        """Stream file content from local file system"""
        full_path = self._get_full_path(path)

        if not await asyncio.to_thread(full_path.exists):
            raise StorageFileNotFoundError(
                f"File not found: {path!r}",
                details={"path": path, "root_dir": str(self.root_dir)},
                hint=f"Ensure the file was uploaded before streaming. Check root_dir {str(self.root_dir)!r}.",
            )

        async with aiofiles.open(full_path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete(self, path: str) -> None:
        """Delete file from local file system"""
        full_path = self._get_full_path(path)

        if not await asyncio.to_thread(full_path.exists):
            raise StorageFileNotFoundError(
                f"File not found: {path!r}",
                details={"path": path, "root_dir": str(self.root_dir)},
                hint=f"Verify the file exists before deleting. Check root_dir {str(self.root_dir)!r}.",
            )

        await asyncio.to_thread(full_path.unlink)
        await self._delete_metadata(full_path)

    async def exists(self, path: str) -> bool:
        """Check if file exists in local file system"""
        full_path = self._get_full_path(path)
        return await asyncio.to_thread(full_path.exists)

    async def info(self, path: str) -> FileInfo:
        """Get file info from local file system"""
        full_path = self._get_full_path(path)

        if not await asyncio.to_thread(full_path.exists):
            raise StorageFileNotFoundError(
                f"File not found: {path!r}",
                details={"path": path, "root_dir": str(self.root_dir)},
                hint=f"Verify the file exists. Check root_dir {str(self.root_dir)!r}.",
            )

        stat = await asyncio.to_thread(full_path.stat)
        stored = await self._read_metadata(full_path) or {}
        content_type = stored.get("content_type") or get_content_type(str(full_path))

        return FileInfo(
            path=path,
            size=stat.st_size,
            content_type=content_type,
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            etag=f'"{stat.st_mtime:.0f}"',
            metadata=stored.get("metadata"),
        )

    async def list(self, prefix: str = "") -> AsyncGenerator[FileInfo, None]:
        """List files with prefix from local file system"""
        search_path = self._get_full_path(prefix) if prefix else self.root_dir

        if await asyncio.to_thread(search_path.is_file):
            # If prefix points to a file, yield just that file
            stat = await asyncio.to_thread(search_path.stat)
            stored = await self._read_metadata(search_path) or {}
            yield FileInfo(
                path=search_path.relative_to(self.root_dir).as_posix(),
                size=stat.st_size,
                content_type=stored.get("content_type")
                or get_content_type(str(search_path)),
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                etag=f'"{stat.st_mtime:.0f}"',
                metadata=stored.get("metadata"),
            )
        else:
            # Hide the internal metadata sidecars from the public blob listing.
            def _get_files() -> Any:
                return list(filter(lambda f: f.is_file(), search_path.rglob("*")))

            file_paths = await asyncio.to_thread(_get_files)
            for file_path in file_paths:
                relative = file_path.relative_to(self.root_dir)
                if relative.parts and relative.parts[0] == self._METADATA_DIR:
                    continue
                stat = await asyncio.to_thread(file_path.stat)
                stored = await self._read_metadata(file_path) or {}
                yield FileInfo(
                    path=relative.as_posix(),
                    size=stat.st_size,
                    content_type=stored.get("content_type")
                    or get_content_type(str(file_path)),
                    last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    etag=f'"{stat.st_mtime:.0f}"',
                    metadata=stored.get("metadata"),
                )

    async def get_url(self, path: str) -> str:
        """Get public URL for local file"""
        return f"{self.base_url}/{path.lstrip('/')}"

    async def get_presigned_url(
        self,
        path: str,
        expires_in: timedelta = timedelta(hours=1),
        method: str = "GET",
    ) -> str:
        """Get a pre-signed URL for local file.

        Local driver does not support presigned URLs; callers
        must fall back to the public URL via :meth:`get_url`.
        """
        raise StorageUnsupportedOperationError(
            "Local storage does not support presigned URLs"
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check on local storage"""
        import time

        start_time = time.time()
        try:
            # Check if root directory exists and is writable
            is_dir = await asyncio.to_thread(self.root_dir.is_dir)
            if not is_dir:
                latency_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    component="storage.local",
                    status=HealthStatus.UNHEALTHY,
                    error=f"Root directory does not exist: {self.root_dir}",
                    duration_ms=latency_ms,
                )

            is_writable = await asyncio.to_thread(os.access, self.root_dir, os.W_OK)
            if not is_writable:
                latency_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    component="storage.local",
                    status=HealthStatus.UNHEALTHY,
                    error=f"Root directory is not writable: {self.root_dir}",
                    duration_ms=latency_ms,
                )

            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component="storage.local",
                status=HealthStatus.HEALTHY,
                details={
                    "root_dir": str(self.root_dir),
                    "base_url": self.base_url,
                },
                duration_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.exception("Local storage health check failed")
            return HealthCheckResult(
                component="storage.local",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                duration_ms=latency_ms,
            )

    async def copy(self, src: str, dst: str) -> FileInfo:
        """Copy a file efficiently within the local filesystem."""
        import shutil

        src_path = self._get_full_path(src)
        dst_path = self._get_full_path(dst)

        if not await asyncio.to_thread(src_path.exists):
            raise StorageFileNotFoundError(
                f"File not found: {src!r}",
                details={"path": src, "root_dir": str(self.root_dir)},
                hint=f"Verify the file exists before copying. Check root_dir {str(self.root_dir)!r}.",
            )

        await asyncio.to_thread(dst_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, str(src_path), str(dst_path))
        return await self.info(dst)

    async def move(self, src: str, dst: str) -> FileInfo:
        """Move a file efficiently within the local filesystem."""
        import shutil

        src_path = self._get_full_path(src)
        dst_path = self._get_full_path(dst)

        if not await asyncio.to_thread(src_path.exists):
            raise StorageFileNotFoundError(
                f"File not found: {src!r}",
                details={"path": src, "root_dir": str(self.root_dir)},
                hint=f"Verify the file exists before moving. Check root_dir {str(self.root_dir)!r}.",
            )

        await asyncio.to_thread(dst_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.move, str(src_path), str(dst_path))
        return await self.info(dst)
