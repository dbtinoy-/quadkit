"""Storage data models for Quadkit Framework."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, BinaryIO

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class FileInfo:
    """Information about a stored file."""

    path: str
    size: int
    content_type: str
    last_modified: datetime
    created_at: datetime | None = None
    etag: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class UploadOptions:
    """Options for file uploads."""

    content_type: str | None = None
    public: bool = False
    metadata: dict[str, str] | None = None
    cache_control: str | None = None

    def __post_init__(self) -> None:
        """Normalize metadata keys to lowercase for consistent lookups."""
        if self.metadata:
            object.__setattr__(
                self, "metadata", {k.lower(): v for k, v in self.metadata.items()}
            )


# Type alias for uploadable content
Uploadable = bytes | str | BinaryIO | AsyncIterator[Any]


__all__ = ["FileInfo", "UploadOptions", "Uploadable"]
