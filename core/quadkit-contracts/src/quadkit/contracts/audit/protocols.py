"""Framework-wide audit logging protocols for security and compliance."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from quadkit.contracts.audit.types import (
    AuditEntry,
    AuditMismatch,
    AuditQuery,
    RetentionDecision,
)

__all__ = [
    "AuditLoggerProtocol",
    "AuditStoreProtocol",
    "AuditVerifierProtocol",
    "RetentionPolicyProtocol",
]


@runtime_checkable
class AuditLoggerProtocol(Protocol):
    """Framework-wide protocol for recording and querying the audit trail.

    All packages that perform security-sensitive or compliance-relevant
    operations accept this via constructor injection and call ``log()``
    at key operation boundaries.

    Implementations must not raise from ``log()`` — audit failure must
    never block the operation that triggered it.
    """

    async def log(self, entry: AuditEntry) -> None:
        """Persist an audit entry. Never raises.

        Args:
            entry: The audit event to record.
        """
        ...

    async def query(self, query: AuditQuery) -> list[AuditEntry]:
        """Retrieve audit entries matching the given filters.

        Args:
            query: Filter criteria encapsulated in an AuditQuery object.

        Returns:
            List of matching entries, newest-first.
        """
        ...


@runtime_checkable
class AuditStoreProtocol(Protocol):
    """Low-level persistence protocol for audit storage backends.

    The ``AuditLogger`` delegates to this protocol for actual persistence.
    This protocol is append-only — purge operations happen at a higher
    level via ``AuditPurger``.
    """

    async def append(self, entry: AuditEntry) -> None:
        """Persist a single audit entry.

        Args:
            entry: The audit event to store.
        """
        ...

    async def query(self, query: AuditQuery) -> list[AuditEntry]:
        """Retrieve entries matching filters, newest-first.

        Args:
            query: Filter criteria.

        Returns:
            List of matching entries.
        """
        ...

    async def count(self, query: AuditQuery) -> int:
        """Return count of entries matching filters.

        Args:
            query: Filter criteria.

        Returns:
            Number of matching entries.
        """
        ...

    async def delete_expired(self, cutoff: datetime) -> int:
        """Delete entries whose stored expiry precedes or equals the cutoff.

        Entries are identified by the ``__expires_at`` metadata stamp
        written by ``AuditLogger.log()`` when a retention policy is
        configured. Entries without the stamp are never deleted.

        Args:
            cutoff: UTC datetime; entries expiring at or before this
                instant are deleted.

        Returns:
            Number of entries deleted.
        """
        ...


@runtime_checkable
class AuditVerifierProtocol(Protocol):
    """Protocol for audit trail tamper detection via HMAC checksums."""

    async def verify_recent(self, *, limit: int = 100) -> list[AuditMismatch]:
        """Verify checksums for the most recent entries.

        Args:
            limit: Number of recent entries to verify.

        Returns:
            List of mismatches (empty list = all verified).
        """
        ...

    async def verify_entry(self, entry: AuditEntry) -> AuditMismatch | None:
        """Verify checksum for a single entry.

        Args:
            entry: The audit entry to verify.

        Returns:
            None when the entry verifies clean; an AuditMismatch whose
            reason is ``checksum_mismatch`` when tampered or
            ``no_checksum_present`` when the entry carries no stored
            checksum (a pre-checksum row) and cannot be verified.
        """
        ...


@runtime_checkable
class RetentionPolicyProtocol(Protocol):
    """Protocol for audit retention policy evaluation."""

    async def evaluate(self, entry: AuditEntry) -> RetentionDecision:
        """Determine the retention decision for an entry.

        Args:
            entry: The audit entry to evaluate.

        Returns:
            A RetentionDecision value.
        """
        ...

    async def get_expiry(self, entry: AuditEntry) -> datetime | None:
        """Return the expiry datetime for an entry, or None for indefinite retention.

        Args:
            entry: The audit entry to evaluate.

        Returns:
            UTC datetime when the entry expires, or None.
        """
        ...
