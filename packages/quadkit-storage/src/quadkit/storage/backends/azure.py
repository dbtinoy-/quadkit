"""Azure Blob Storage driver using azure-storage-blob for async I/O."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import time
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.validation import SecretStr

# Optional dependency — azure-storage-blob provides async Blob Storage access.
try:
    from azure.storage.blob.aio import (
        BlobServiceClient as _BlobServiceClient,
    )
    from azure.storage.blob.aio import (
        ContainerClient as _ContainerClient,
    )

    _AZURE_AVAILABLE = True
except ImportError:
    _BlobServiceClient = None
    _ContainerClient = None
    _AZURE_AVAILABLE = False

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.infra.storage import FileInfo, Uploadable, UploadOptions
from quadkit.storage.backends._azure_helpers import (
    coerce_last_modified,
    is_blob_not_found,
    reraise_blob_error,
    to_bytes,
)
from quadkit.storage.backends.base import AbstractDriver
from quadkit.storage.exceptions import StorageError
from quadkit.storage.lib.content_type import get_content_type
from quadkit.storage.lib.paths import sanitize_path

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from quadkit.contracts.core import HealthCheckResult

logger = get_logger(__name__)


class AzureDriver(AbstractDriver):
    """Azure Blob Storage driver.

    Wraps ``azure-storage-blob`` (async variant) to provide fully async
    Blob Storage operations.

    Install the optional dependency with::

        pip install quadkit-storage[azure]
        # i.e.  azure-storage-blob>=12.20.0

    Args:
        account_name: Azure storage account name.
        account_key: Storage account access key (plain string or ``SecretStr``).
        container: Blob container (equivalent to a bucket).
    """

    def __init__(
        self,
        account_name: str,
        account_key: str | SecretStr,
        container: str,
    ) -> None:
        """Initialise the Azure Blob Storage driver.

        Args:
            account_name: Azure storage account name.
            account_key: Storage account access key.
            container: Blob container name.

        Raises:
            ImportError: When ``azure-storage-blob`` is not installed.
        """
        if not _AZURE_AVAILABLE:
            raise ImportError(
                "Azure driver requires azure-storage-blob. "
                "Install with: pip install quadkit-storage[azure]",
            )

        self.account_name = account_name
        self.container = container
        # Store key as SecretStr; unwrap only at the SDK boundary.
        self._account_key: SecretStr = (
            account_key
            if isinstance(account_key, SecretStr)
            else SecretStr(account_key)
        )

        account_url = f"https://{account_name}.blob.core.windows.net"
        self._service_client: Any = _BlobServiceClient(
            account_url=account_url,
            credential=self._account_key.get_secret_value(),
        )
        self._container_client: Any = self._service_client.get_container_client(
            container
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_path(self, path: str) -> str:
        """Return a sanitised Azure blob name from *path*."""
        return sanitize_path(path)

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
        """Upload *data* to Azure Blob Storage at *path*.

        Args:
            path: Destination blob name / key.
            data: Content to upload.
            content_type: Optional MIME type override.
            **options: Additional upload options.

        Returns:
            :class:`~quadkit.contracts.infra.storage.FileInfo` for the stored blob.

        Raises:
            StorageError: On any Azure SDK error.
        """
        key = self._normalize_path(path)
        content = await to_bytes(data)
        upload_options = self._normalize_upload_options(content_type, options)
        resolved_content_type = (
            upload_options.content_type
            if upload_options and upload_options.content_type
            else get_content_type(key)
        )

        try:
            from azure.storage.blob import (
                ContentSettings,
            )

            blob_client = self._container_client.get_blob_client(key)
            await blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=ContentSettings(content_type=resolved_content_type),
                metadata=upload_options.metadata if upload_options else None,
            )
            logger.info(
                "azure_upload_complete container=%s key=%s size=%d",
                self.container,
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
            logger.exception(
                "azure_upload_failed container=%s key=%s", self.container, key
            )
            raise StorageError(
                f"Azure upload failed for {key!r}: {exc}",
                details={
                    "container": self.container,
                    "key": key,
                    "account": self.account_name,
                },
                hint="Check Azure credentials, container write permissions, and network connectivity.",
            ) from exc

    async def download(self, path: str) -> bytes:
        """Download the blob at *path* into memory.

        Args:
            path: Blob name / key.

        Returns:
            Raw file bytes.

        Raises:
            FileNotFoundError: When the blob does not exist.
            StorageError: On any other Azure SDK error.
        """
        key = self._normalize_path(path)
        try:
            blob_client = self._container_client.get_blob_client(key)
            downloader = await blob_client.download_blob()
            data: bytes = await downloader.readall()
            return data
        except Exception as exc:
            raise reraise_blob_error(exc, self, "download", path)

    async def stream(
        self,
        path: str,
        chunk_size: int = 8192,
    ) -> AsyncGenerator[bytes, None]:
        """Yield successive chunks from the Azure blob at *path*.

        Args:
            path: Blob name / key.
            chunk_size: Bytes per chunk (default 8 KiB).

        Yields:
            Raw byte chunks.
        """
        key = self._normalize_path(path)
        try:
            blob_client = self._container_client.get_blob_client(key)
            downloader = await blob_client.download_blob(max_concurrency=1)
            async for chunk in downloader.chunks():
                # The SDK yields chunks of varying size; we re-chunk to
                # honour the caller's requested chunk_size.
                for i in range(0, len(chunk), chunk_size):
                    yield chunk[i : i + chunk_size]
        except Exception as exc:
            raise reraise_blob_error(exc, self, "stream", path)

    async def delete(self, path: str) -> None:
        """Delete the Azure blob at *path*.

        Args:
            path: Blob name / key.

        Raises:
            FileNotFoundError: When the blob does not exist.
            StorageError: On any other Azure SDK error.
        """
        key = self._normalize_path(path)
        try:
            blob_client = self._container_client.get_blob_client(key)
            await blob_client.delete_blob()
        except Exception as exc:
            raise reraise_blob_error(exc, self, "delete", path)

    async def exists(self, path: str) -> bool:
        """Return ``True`` if *path* exists in the Azure container.

        Args:
            path: Blob name / key.

        Returns:
            ``False`` when the blob does not exist.

        Raises:
            StorageError: On any other Azure SDK error — a failed
                connectivity/credentials check must not be reported as
                "does not exist" (the old narrow except tuple also missed
                Azure SDK error classes, which are not OSError subclasses).
        """
        key = self._normalize_path(path)
        try:
            blob_client = self._container_client.get_blob_client(key)
            return bool(await blob_client.exists())
        except Exception as exc:
            if is_blob_not_found(exc):
                return False
            raise StorageError(
                f"Azure exists check failed for {path!r}: {exc}",
                details={"container": self.container, "path": path},
                hint="Check Azure credentials and container read permissions.",
            ) from exc

    async def info(self, path: str) -> FileInfo:
        """Return metadata for the Azure blob at *path*.

        Args:
            path: Blob name / key.

        Returns:
            :class:`~quadkit.contracts.infra.storage.FileInfo`.

        Raises:
            FileNotFoundError: When the blob does not exist.
            StorageError: On any other Azure SDK error.
        """
        key = self._normalize_path(path)
        try:
            blob_client = self._container_client.get_blob_client(key)
            props = await blob_client.get_blob_properties()

            last_modified = coerce_last_modified(props.get("last_modified"))

            content_settings = props.get("content_settings", {})
            content_type = (
                (content_settings.get("content_type") or get_content_type(key))
                if content_settings
                else get_content_type(key)
            )

            return FileInfo(
                path=key,
                size=int(props.get("size", 0)),
                content_type=content_type,
                last_modified=last_modified,
                etag=props.get("etag", ""),
                metadata=dict(props.get("metadata", {})) or None,
            )
        except Exception as exc:
            raise reraise_blob_error(exc, self, "info", path)

    async def list(self, prefix: str = "") -> AsyncGenerator[FileInfo, None]:
        """Yield :class:`~quadkit.contracts.infra.storage.FileInfo` for blobs matching *prefix*.

        Args:
            prefix: Blob name prefix filter (empty string lists all blobs).

        Yields:
            :class:`~quadkit.contracts.infra.storage.FileInfo` entries.

        Raises:
            StorageError: On any Azure SDK error.
        """
        normalized_prefix = self._normalize_path(prefix) if prefix else None
        try:
            async for item in self._container_client.list_blobs(
                name_starts_with=normalized_prefix
            ):
                last_modified = coerce_last_modified(item.get("last_modified"))

                yield FileInfo(
                    path=item["name"],
                    size=int(item.get("size", 0)),
                    content_type=get_content_type(item["name"]),
                    last_modified=last_modified,
                    etag=item.get("etag", ""),
                )
        except Exception as exc:
            raise StorageError(
                f"Azure list failed for container={self.container} prefix={prefix!r}: {exc}"
            ) from exc

    async def get_url(self, path: str) -> str:
        """Return a public URL for the Azure blob at *path*.

        The URL is only accessible when the container has public access
        enabled.  For private containers, use :meth:`get_presigned_url`.

        Args:
            path: Blob name / key.
        """
        key = self._normalize_path(path)
        return (
            f"https://{self.account_name}.blob.core.windows.net/{self.container}/{key}"
        )

    async def get_presigned_url(
        self,
        path: str,
        expires_in: timedelta = timedelta(hours=1),
        method: str = "GET",
    ) -> str:
        """Return a SAS (Shared Access Signature) URL for the blob at *path*.

        Args:
            path: Blob name / key.
            expires_in: Validity window (default one hour).
            method: HTTP verb (``"GET"`` for read, ``"PUT"`` for write).

        Returns:
            A time-limited SAS URL string.

        Raises:
            StorageError: When SAS token generation fails.
        """
        key = self._normalize_path(path)
        try:
            from azure.storage.blob import (
                BlobSasPermissions,
                generate_blob_sas,
            )

            permission = (
                BlobSasPermissions(write=True, create=True)
                if method.upper() == "PUT"
                else BlobSasPermissions(read=True)
            )
            expiry = datetime.now(UTC) + expires_in
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container,
                blob_name=key,
                account_key=self._account_key.get_secret_value(),
                permission=permission,
                expiry=expiry,
            )
            base_url = (
                f"https://{self.account_name}.blob.core.windows.net"
                f"/{self.container}/{key}"
            )
            return f"{base_url}?{sas_token}"
        except Exception as exc:
            raise StorageError(
                f"Azure presigned URL failed for {path!r}: {exc}",
                details={
                    "container": self.container,
                    "path": path,
                    "account": self.account_name,
                },
                hint="Check Azure credentials and ensure the account key has sufficient permissions for SAS token generation.",
            ) from exc

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight connectivity check against Azure Blob Storage.

        Lists at most one blob from the container to verify credentials and
        container accessibility.

        Returns:
            :class:`~quadkit.contracts.types.HealthCheckResult`.
        """
        from quadkit.contracts.core import HealthCheckResult

        start_time = time.time()
        try:
            # Consume just the first item to verify connectivity.
            async for _ in self._container_client.list_blobs(results_per_page=1):
                break
            latency_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=self.container,
                status=HealthStatus.HEALTHY,
                details={
                    "account_name": self.account_name,
                    "container": self.container,
                },
                duration_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000
            logger.exception("azure_health_check_failed container=%s", self.container)
            return HealthCheckResult(
                component=self.container,
                status=HealthStatus.UNHEALTHY,
                error=str(exc),
                details={
                    "account_name": self.account_name,
                    "container": self.container,
                },
                duration_ms=latency_ms,
            )


__all__ = ["AzureDriver"]
