"""Google Cloud Storage driver using gcloud-aio-storage for native async I/O."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import time
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

# Optional dependency — gcloud-aio-storage provides native async GCS access.
try:
    from gcloud.aio.storage import (
        Storage as _GCSStorage,
    )

    _GCS_AVAILABLE = True
except ImportError:
    _GCSStorage = None
    _GCS_AVAILABLE = False

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.infra.storage import FileInfo, Uploadable, UploadOptions
from quadkit.storage.backends.base import AbstractDriver
from quadkit.storage.exceptions import StorageError, StorageFileNotFoundError
from quadkit.storage.lib.content_type import get_content_type
from quadkit.storage.lib.paths import sanitize_path

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from quadkit.contracts.core import HealthCheckResult

logger = get_logger(__name__)


class GCSDriver(AbstractDriver):
    """Google Cloud Storage driver.

    Wraps ``gcloud-aio-storage`` to provide fully async GCS operations.

    Install the optional dependency with::

        pip install quadkit-storage[gcs]
        # i.e.  gcloud-aio-storage>=9.0.0

    Args:
        bucket: GCS bucket name.
        project_id: Google Cloud project ID (used for logging / context only;
            the gcloud library resolves the project from ADC when needed).
        credentials_path: Path to a service-account JSON key file.  When
            ``None`` the driver falls back to Application Default Credentials
            (ADC), which covers Cloud Run, GKE Workload Identity, etc.
    """

    def __init__(
        self,
        bucket: str,
        project_id: str | None = None,
        credentials_path: str | None = None,
    ) -> None:
        """Initialise the GCS driver.

        Args:
            bucket: GCS bucket name.
            project_id: Google Cloud project ID (informational; ADC handles auth).
            credentials_path: Path to service-account JSON credentials file, or
                ``None`` to use Application Default Credentials.

        Raises:
            ImportError: When ``gcloud-aio-storage`` is not installed.
        """
        if not _GCS_AVAILABLE:
            raise ImportError(
                "GCS driver requires gcloud-aio-storage. "
                "Install with: pip install quadkit-storage[gcs]",
            )

        self.bucket = bucket
        self.project_id = project_id
        self.credentials_path = credentials_path

        # Instantiate client — service_file=None falls back to ADC.
        self._client: Any = _GCSStorage(service_file=credentials_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_path(self, path: str) -> str:
        """Return a sanitised GCS object name from *path*."""
        return sanitize_path(path)

    async def _to_bytes(self, data: Uploadable) -> bytes:
        """Coerce *data* to :class:`bytes` for upload."""
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        if hasattr(data, "read"):
            raw = data.read()
            return raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        if hasattr(data, "__aiter__"):
            chunks: list[bytes] = []
            async for chunk in data:
                chunks.append(
                    chunk.encode("utf-8") if isinstance(chunk, str) else bytes(chunk),
                )
            return b"".join(chunks)
        raise ValueError(f"Unsupported data type: {type(data)}")

    @staticmethod
    def _parse_gcs_datetime(value: str | None) -> datetime:
        """Parse a GCS RFC 3339 timestamp string into a timezone-aware datetime."""
        if not value:
            return datetime.now(UTC)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    # ------------------------------------------------------------------
    # AbstractDriver implementation
    # ------------------------------------------------------------------

    async def upload(
        self,
        path: str,
        data: Uploadable,
        content_type: UploadOptions | str | None = None,
        **options: Any,
    ) -> FileInfo:
        """Upload *data* to the GCS *path*.

        Args:
            path: Destination object name / key.
            data: Content to upload.
            content_type: Optional MIME type override.
            **options: Additional upload options.

        Returns:
            :class:`~quadkit.contracts.infra.storage.FileInfo` for the stored object.

        Raises:
            StorageError: On any GCS API error.
        """
        key = self._normalize_path(path)
        content = await self._to_bytes(data)
        upload_options = self._normalize_upload_options(content_type, options)
        resolved_content_type = (
            upload_options.content_type
            if upload_options and upload_options.content_type
            else get_content_type(key)
        )

        try:
            await self._client.upload(
                self.bucket,
                key,
                content,
                content_type=resolved_content_type,
            )
            logger.info(
                "gcs_upload_complete bucket=%s key=%s size=%d",
                self.bucket,
                key,
                len(content),
            )
            return FileInfo(
                path=key,
                size=len(content),
                content_type=resolved_content_type,
                last_modified=datetime.now(UTC),
                metadata=upload_options.metadata if upload_options else None,
            )
        except Exception as exc:
            logger.exception("gcs_upload_failed bucket=%s key=%s", self.bucket, key)
            raise StorageError(
                f"GCS upload failed for {key!r}: {exc}",
                details={
                    "bucket": self.bucket,
                    "key": key,
                    "project_id": self.project_id,
                },
                hint="Check GCS credentials, bucket write permissions, and network connectivity.",
            ) from exc

    async def download(self, path: str) -> bytes:
        """Download the object at *path* into memory.

        Args:
            path: Object name / key.

        Returns:
            Raw file bytes.

        Raises:
            FileNotFoundError: When the object does not exist.
            StorageError: On any other GCS API error.
        """
        key = self._normalize_path(path)
        try:
            response = await self._client.download(self.bucket, key)
            return response if isinstance(response, bytes) else response.encode("utf-8")
        except Exception as exc:
            exc_str = str(exc)
            if "404" in exc_str or "Not Found" in exc_str:
                raise StorageFileNotFoundError(
                    f"File not found: {path!r}",
                    details={"bucket": self.bucket, "path": path},
                    hint=f"Ensure the file was uploaded before downloading. Check bucket {self.bucket!r}.",
                ) from exc
            raise StorageError(
                f"GCS download failed for {path!r}: {exc}",
                details={"bucket": self.bucket, "path": path},
                hint="Check GCS credentials and bucket read permissions.",
            ) from exc

    async def stream(
        self,
        path: str,
        chunk_size: int = 8192,
    ) -> AsyncGenerator[bytes, None]:
        """Yield successive chunks from the GCS object at *path*.

        Downloads the entire object into memory first, then yields chunks from
        the in-memory buffer.  For objects larger than available RAM, prefer
        using a streaming-capable GCS library.

        Args:
            path: Object name / key.
            chunk_size: Bytes per chunk (default 8 KiB).

        Yields:
            Raw byte chunks.
        """
        content = await self.download(path)
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

    async def delete(self, path: str) -> None:
        """Delete the GCS object at *path*.

        Args:
            path: Object name / key.

        Raises:
            FileNotFoundError: When the object does not exist.
            StorageError: On any other GCS API error.
        """
        key = self._normalize_path(path)
        try:
            await self._client.delete(self.bucket, key)
        except Exception as exc:
            exc_str = str(exc)
            if "404" in exc_str or "Not Found" in exc_str:
                raise StorageFileNotFoundError(
                    f"File not found: {path!r}",
                    details={"bucket": self.bucket, "path": path},
                    hint=f"Verify the file exists before deleting. Check bucket {self.bucket!r}.",
                ) from exc
            raise StorageError(
                f"GCS delete failed for {path!r}: {exc}",
                details={"bucket": self.bucket, "path": path},
                hint="Check GCS credentials and bucket delete permissions.",
            ) from exc

    async def exists(self, path: str) -> bool:
        """Return ``True`` if *path* exists in the GCS bucket.

        Args:
            path: Object name / key.

        Returns:
            ``False`` when the object does not exist.

        Raises:
            StorageError: On any other GCS API error — a failed
                connectivity/credentials check must not be reported as
                "does not exist" (the old narrow except tuple also missed
                google-api-core error classes, which are not OSError
                subclasses).
        """
        key = self._normalize_path(path)
        try:
            await self._client.download_metadata(self.bucket, key)
            return True
        except Exception as exc:
            exc_str = str(exc)
            if "404" in exc_str or "Not Found" in exc_str:
                return False
            raise StorageError(
                f"GCS exists check failed for {path!r}: {exc}",
                details={"bucket": self.bucket, "path": path},
                hint="Check GCS credentials and bucket read permissions.",
            ) from exc

    async def info(self, path: str) -> FileInfo:
        """Return metadata for the GCS object at *path*.

        Args:
            path: Object name / key.

        Returns:
            :class:`~quadkit.contracts.infra.storage.FileInfo`.

        Raises:
            FileNotFoundError: When the object does not exist.
            StorageError: On any other GCS API error.
        """
        key = self._normalize_path(path)
        try:
            metadata: dict[str, Any] = await self._client.download_metadata(
                self.bucket, key
            )
            return FileInfo(
                path=key,
                size=int(metadata.get("size", 0)),
                content_type=metadata.get("contentType", "application/octet-stream"),
                last_modified=self._parse_gcs_datetime(
                    metadata.get("updated") or metadata.get("timeCreated")
                ),
                etag=metadata.get("etag", ""),
            )
        except Exception as exc:
            exc_str = str(exc)
            if "404" in exc_str or "Not Found" in exc_str:
                raise StorageFileNotFoundError(
                    f"File not found: {path!r}",
                    details={"bucket": self.bucket, "path": path},
                    hint=f"Verify the file exists in bucket {self.bucket!r}.",
                ) from exc
            raise StorageError(
                f"GCS info failed for {path!r}: {exc}",
                details={"bucket": self.bucket, "path": path},
                hint="Check GCS credentials and bucket read permissions.",
            ) from exc

    async def list(self, prefix: str = "") -> AsyncGenerator[FileInfo, None]:
        """Yield :class:`~quadkit.contracts.infra.storage.FileInfo` for objects matching *prefix*.

        Args:
            prefix: Key prefix filter (empty string lists all objects).

        Yields:
            :class:`~quadkit.contracts.infra.storage.FileInfo` entries.

        Raises:
            StorageError: On any GCS API error.
        """
        normalized_prefix = self._normalize_path(prefix) if prefix else ""
        params: dict[str, str] = {}
        if normalized_prefix:
            params["prefix"] = normalized_prefix

        try:
            response: dict[str, Any] = await self._client.list_objects(
                self.bucket, params=params
            )
            for item in response.get("items", []):
                yield FileInfo(
                    path=item["name"],
                    size=int(item.get("size", 0)),
                    content_type=item.get("contentType", "application/octet-stream"),
                    last_modified=self._parse_gcs_datetime(
                        item.get("updated") or item.get("timeCreated")
                    ),
                    etag=item.get("etag", ""),
                )
        except Exception as exc:
            raise StorageError(
                f"GCS list failed for bucket={self.bucket} prefix={prefix!r}: {exc}"
            ) from exc

    async def get_url(self, path: str) -> str:
        """Return a public URL for the GCS object at *path*.

        The URL is only accessible when the object (or bucket) has been made
        publicly readable.  For private objects, use :meth:`get_presigned_url`.

        Args:
            path: Object name / key.
        """
        key = self._normalize_path(path)
        return f"https://storage.googleapis.com/{self.bucket}/{key}"

    async def get_presigned_url(
        self,
        path: str,
        expires_in: timedelta = timedelta(hours=1),
        method: str = "GET",
    ) -> str:
        """Return a signed URL for the GCS object at *path*.

        Uses the V4 signing API from ``gcloud-aio-storage`` when available,
        falling back to an unsigned public URL for read access.

        Args:
            path: Object name / key.
            expires_in: Validity window (default one hour).
            method: HTTP verb (``"GET"`` or ``"PUT"``).

        Returns:
            A signed (or public) URL string.

        Raises:
            StorageError: When URL signing fails.
        """
        key = self._normalize_path(path)
        expires_seconds = int(expires_in.total_seconds())
        try:
            # gcloud-aio-storage >=9 exposes sign_download_url / sign_upload_url
            if method.upper() == "PUT" and hasattr(self._client, "sign_upload_url"):
                signed: str = await self._client.sign_upload_url(
                    self.bucket, key, expires=expires_seconds
                )
                return signed
            if hasattr(self._client, "sign_download_url"):
                signed_url: str = await self._client.sign_download_url(
                    self.bucket, key, expires=expires_seconds
                )
                return signed_url
            # Fallback: unsigned public URL
            return f"https://storage.googleapis.com/{self.bucket}/{key}"
        except Exception as exc:
            raise StorageError(
                f"GCS presigned URL failed for {path!r}: {exc}",
                details={"bucket": self.bucket, "path": path},
                hint="Check GCS credentials and ensure the service account has storage.objects.get permission.",
            ) from exc

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight connectivity check against GCS.

        Lists at most one object from the bucket to verify credentials and
        bucket accessibility.

        Returns:
            :class:`~quadkit.contracts.types.HealthCheckResult`.
        """
        from quadkit.contracts.core import HealthCheckResult

        start_time = time.time()
        try:
            await self._client.list_objects(self.bucket, params={"maxResults": "1"})
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=self.bucket,
                status=HealthStatus.HEALTHY,
                details={
                    "bucket": self.bucket,
                    "project_id": self.project_id,
                },
                duration_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000
            logger.exception("gcs_health_check_failed bucket=%s", self.bucket)
            return HealthCheckResult(
                component=self.bucket,
                status=HealthStatus.UNHEALTHY,
                error=str(exc),
                details={"bucket": self.bucket},
                duration_ms=latency_ms,
            )


__all__ = ["GCSDriver"]
