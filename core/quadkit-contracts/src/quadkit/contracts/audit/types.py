"""Canonical audit-trail value types for security and compliance logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any

__all__ = [
    "AuditEntry",
    "AuditEventSeverity",
    "AuditMismatch",
    "AuditMismatchReason",
    "AuditQuery",
    "RetentionDecision",
    "RetentionPolicy",
]


class AuditEventSeverity(StrEnum):
    """Severity level for audit log entries."""

    LOW = auto()  # Informational — routine operations
    MEDIUM = auto()  # Notable — privilege changes, config updates
    HIGH = auto()  # Security-sensitive — auth failures, data access
    CRITICAL = auto()  # Compliance-critical — data deletion, impersonation


class AuditMismatchReason(StrEnum):
    """Why an audit entry failed checksum verification."""

    CHECKSUM_MISMATCH = auto()  # Stored checksum does not match recomputed checksum
    NO_CHECKSUM_PRESENT = auto()  # Entry has no stored checksum (pre-checksum row)


@dataclass(frozen=True)
class AuditEntry:
    """Immutable record of a security-relevant or compliance-relevant operation.

    Canonical audit type used by all packages. Supersedes the former
    ``AuditEvent`` (simpler, no old/new values) and the ``AuditEntry``
    from ``contracts/observability/audit``.

    Attributes:
        action: Dot-notation action identifier (e.g. ``"user.update"``).
        actor_id: ID of the user or service that performed the action.
        resource_type: Kind of affected resource (e.g. ``"User"``).
        resource_id: ID of the affected resource.
        outcome: ``"success"`` or ``"failure"``.
        severity: Severity level (defaults to MEDIUM).
        occurred_at: UTC datetime of the event (defaults to now).
        metadata: Arbitrary additional context.
        old_values: Field values before the action (optional).
        new_values: Field values after the action (optional).
        source: Originating subsystem (e.g. ``"sql"``, ``"admin"``, ``"ai"``).
        tenant_id: Multi-tenant scoping (optional).
        correlation_id: Request correlation ID for tracing (optional).
        causation_id: Causing event ID for event-driven traces (optional).
        command_payload_hash: SHA-256 hash of the command payload (optional).
        payload_size_bytes: Size of the payload in bytes (optional).
        checksum: HMAC-SHA256 checksum of the persisted row, populated
            by stores on read-back (None for pre-checksum entries).
    """

    action: str
    actor_id: str
    resource_type: str = ""
    resource_id: str = ""
    outcome: str = "success"
    severity: AuditEventSeverity = AuditEventSeverity.MEDIUM
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    source: str = ""
    tenant_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    command_payload_hash: bytes | None = None
    payload_size_bytes: int | None = None
    checksum: str | None = None


@dataclass(frozen=True)
class AuditQuery:
    """Composable filter criteria for querying the audit trail.

    All fields are optional; omitted fields are not applied as filters.

    Attributes:
        actor_id: Filter by actor identifier.
        action: Filter by action verb (exact match).
        resource_type: Filter by resource type.
        resource_id: Filter by resource identifier.
        source: Filter by originating subsystem.
        severity: Filter by severity level.
        outcome: Filter by outcome.
        tenant_id: Filter by tenant.
        correlation_id: Filter by request correlation ID.
        since: Only entries at or after this UTC datetime.
        until: Only entries at or before this UTC datetime.
        limit: Maximum number of entries (default 100).
        offset: Entries to skip for pagination.
    """

    actor_id: str | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    source: str | None = None
    severity: AuditEventSeverity | None = None
    outcome: str | None = None
    tenant_id: str | None = None
    correlation_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class AuditMismatch:
    """Record of a checksum verification failure.

    Attributes:
        entry_id: Identifier of the audit entry with a bad checksum.
        expected_checksum: Checksum stored in the database.
        actual_checksum: Checksum recomputed from current data.
        reason: Whether the entry is tampered or simply has no stored checksum.
    """

    entry_id: str
    expected_checksum: str
    actual_checksum: str
    reason: AuditMismatchReason = AuditMismatchReason.CHECKSUM_MISMATCH


class RetentionDecision(StrEnum):
    """Outcome of a retention policy evaluation."""

    RETAIN = auto()  # Keep indefinitely
    RETAIN_UNTIL = auto()  # Keep until expiry
    ARCHIVE = auto()  # Move to cold storage
    PURGE = auto()  # Eligible for deletion


@dataclass(frozen=True)
class RetentionPolicy:
    """Configuration for audit retention behavior.

    Attributes:
        name: Identifier for this policy.
        default_retention_days: Default days to retain entries (0 = indefinite).
        severity_overrides: Per-severity retention days (key = severity value).
        source_overrides: Per-source retention days (key = source string).
    """

    name: str
    default_retention_days: int = 365
    severity_overrides: dict[str, int] = field(default_factory=dict)
    source_overrides: dict[str, int] = field(default_factory=dict)
