"""Domain events for storage operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from quadkit.contracts.domain.events import DomainEvent
from quadkit.primitives import clock as ambient_clock


@dataclass(frozen=True, init=False)
class FileUploadedEvent(DomainEvent):
    """File was successfully uploaded to storage.

    Consumed by: file tracking, audit logging, quota management.
    """

    file_key: str
    bucket: str
    size_bytes: int
    occurred_at: datetime = field(default_factory=ambient_clock.now, kw_only=True)


@dataclass(frozen=True, init=False)
class FileDeletedEvent(DomainEvent):
    """File was successfully deleted from storage.

    Consumed by: file cleanup tracking, audit logging, quota reclamation.
    """

    file_key: str
    bucket: str
    occurred_at: datetime = field(default_factory=ambient_clock.now, kw_only=True)


@dataclass(frozen=True, init=False)
class FileDownloadedEvent(DomainEvent):
    """File was successfully downloaded from storage.

    Consumed by: download tracking, audit logging, usage analytics.
    """

    file_key: str
    bucket: str
    occurred_at: datetime = field(default_factory=ambient_clock.now, kw_only=True)
