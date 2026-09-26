"""Blob-name/metadata helpers for the Azure Blob Storage driver.

Pure, SDK-free utilities extracted from
:mod:`quadkit.storage.backends.azure`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, NoReturn, Protocol

from quadkit.contracts.infra.storage import Uploadable
from quadkit.storage.exceptions import (
    StorageError,
    StorageFileNotFoundError,
)


async def to_bytes(data: Uploadable) -> bytes:
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


def is_blob_not_found(exc: BaseException) -> bool:
    """Return ``True`` when *exc* represents a missing Azure blob (404)."""
    exc_str = str(exc)
    return "BlobNotFound" in exc_str or "404" in exc_str


def coerce_last_modified(value: Any) -> datetime:
    """Return *value* when it is a datetime, otherwise the current UTC time."""
    if isinstance(value, datetime):
        return value
    return datetime.now(UTC)


class _BlobDriver(Protocol):
    """Structural view of the driver attributes the error helper needs."""

    container: str
    account_name: str


_NOT_FOUND_HINTS: dict[str, str] = {
    "delete": (
        "Verify the blob exists before deleting. Check container {container!r}."
    ),
    "info": "Verify the blob exists in container {container!r}.",
}


def reraise_blob_error(
    exc: BaseException,
    driver: _BlobDriver,
    operation: str,
    path: str,
) -> NoReturn:
    """Re-raise *exc* as the canonical Azure storage error.

    Not-found (404) failures map to
    :class:`~quadkit.storage.exceptions.StorageFileNotFoundError`;
    every other failure maps to
    :class:`~quadkit.storage.exceptions.StorageError` so a
    connectivity/credentials outage is never silently swallowed.

    Args:
        exc: The caught SDK exception.
        driver: The :class:`AzureDriver` instance (provides
            ``container`` and ``account_name`` for the error details).
        operation: Human-readable verb used in messages
            (``"download"``, ``"stream"``, ``"delete"``, ``"info"``).
        path: The original (pre-normalisation) storage path.
    """
    container = str(driver.container)
    details: dict[str, Any] = {"container": container, "path": path}
    if is_blob_not_found(exc):
        template = _NOT_FOUND_HINTS.get(
            operation,
            "Ensure the blob was uploaded before {operation}ing. "
            "Check container {container!r}.",
        )
        raise StorageFileNotFoundError(
            f"File not found: {path!r}",
            details={**details, "account": str(driver.account_name)},
            hint=template.format(container=container, operation=operation),
        ) from exc
    permission = "delete" if operation == "delete" else "read"
    raise StorageError(
        f"Azure {operation} failed for {path!r}: {exc}",
        details=details,
        hint=f"Check Azure credentials and container {permission} permissions.",
    ) from exc
