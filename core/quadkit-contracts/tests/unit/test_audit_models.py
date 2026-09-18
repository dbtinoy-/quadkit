"""Tests for canonical AuditEntry, AuditQuery, and related types."""

from __future__ import annotations

import pytest
from datetime import UTC, datetime

from quadkit.contracts.audit import (
    AuditEntry,
    AuditEventSeverity,
    AuditMismatch,
    AuditMismatchReason,
    AuditQuery,
    RetentionDecision,
    RetentionPolicy,
)


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""

    def test_minimal_creation(self) -> None:
        """Verify minimal AuditEntry creation with defaults."""
        entry = AuditEntry(action="user.login", actor_id="user-1")
        assert entry.action == "user.login"
        assert entry.actor_id == "user-1"
        assert entry.resource_type == ""
        assert entry.resource_id == ""
        assert entry.outcome == "success"
        assert entry.severity == AuditEventSeverity.MEDIUM
        assert entry.occurred_at is not None
        assert entry.source == ""
        assert entry.tenant_id is None

    def test_full_creation(self) -> None:
        """Verify AuditEntry with all fields."""
        now = datetime.now(UTC)
        entry = AuditEntry(
            action="order.delete",
            actor_id="admin-1",
            resource_type="Order",
            resource_id="order-99",
            outcome="success",
            severity=AuditEventSeverity.HIGH,
            occurred_at=now,
            metadata={"ip": "1.2.3.4"},
            old_values={"status": "active"},
            new_values=None,
            source="admin",
            tenant_id="tenant-1",
        )
        assert entry.severity == AuditEventSeverity.HIGH
        assert entry.occurred_at == now
        assert entry.source == "admin"
        assert entry.tenant_id == "tenant-1"

    def test_is_frozen(self) -> None:
        """Verify AuditEntry is immutable."""
        entry = AuditEntry(action="test", actor_id="actor")
        with pytest.raises((AttributeError, TypeError)):
            entry.action = "modified"  # type: ignore[misc]

    def test_occurred_at_defaults_to_now(self) -> None:
        """Verify occurred_at auto-populates."""
        before = datetime.now(UTC)
        entry = AuditEntry(action="test", actor_id="actor")
        after = datetime.now(UTC)
        assert before <= entry.occurred_at <= after

    def test_no_resource_table_field(self) -> None:
        """Verify legacy resource_table field does not exist."""
        entry = AuditEntry(action="test", actor_id="actor")
        assert not hasattr(entry, "resource_table")

    def test_no_timestamp_field(self) -> None:
        """Verify legacy timestamp field does not exist (use occurred_at)."""
        entry = AuditEntry(action="test", actor_id="actor")
        assert not hasattr(entry, "timestamp")

    def test_default_metadata_is_empty_dict(self) -> None:
        """Verify default metadata is empty dict."""
        entry = AuditEntry(action="test", actor_id="actor")
        assert entry.metadata == {}

    def test_old_values_defaults_to_none(self) -> None:
        """Verify old_values defaults to None."""
        entry = AuditEntry(action="test", actor_id="actor")
        assert entry.old_values is None

    def test_checksum_defaults_to_none(self) -> None:
        entry = AuditEntry(action="test", actor_id="actor")
        assert entry.checksum is None

    def test_checksum_is_settable(self) -> None:
        entry = AuditEntry(action="test", actor_id="actor", checksum="abc123")
        assert entry.checksum == "abc123"


class TestAuditQuery:
    """Tests for AuditQuery dataclass."""

    def test_all_defaults(self) -> None:
        """Verify AuditQuery defaults."""
        q = AuditQuery()
        assert q.actor_id is None
        assert q.limit == 100
        assert q.offset == 0
        assert q.source is None
        assert q.tenant_id is None
        assert q.severity is None
        assert q.outcome is None
        assert q.until is None

    def test_partial_filter(self) -> None:
        """Verify partial AuditQuery construction."""
        q = AuditQuery(actor_id="user-1", action="user.login", limit=10)
        assert q.actor_id == "user-1"
        assert q.action == "user.login"
        assert q.limit == 10

    def test_severity_filter(self) -> None:
        """Verify severity filter on AuditQuery."""
        q = AuditQuery(severity=AuditEventSeverity.HIGH)
        assert q.severity == AuditEventSeverity.HIGH

    def test_tenant_filter(self) -> None:
        """Verify tenant_id filter on AuditQuery."""
        q = AuditQuery(tenant_id="tenant-1")
        assert q.tenant_id == "tenant-1"


class TestAuditMismatch:
    """Tests for AuditMismatch dataclass."""

    def test_creation(self) -> None:
        mismatch = AuditMismatch(
            entry_id="entry-1",
            expected_checksum="abc123",
            actual_checksum="def456",
        )
        assert mismatch.entry_id == "entry-1"
        assert mismatch.expected_checksum != mismatch.actual_checksum

    def test_reason_defaults_to_checksum_mismatch(self) -> None:
        mismatch = AuditMismatch(
            entry_id="entry-1",
            expected_checksum="abc123",
            actual_checksum="def456",
        )
        assert mismatch.reason == AuditMismatchReason.CHECKSUM_MISMATCH


class TestAuditMismatchReason:
    """Tests for AuditMismatchReason enum."""

    def test_values(self) -> None:
        assert AuditMismatchReason.CHECKSUM_MISMATCH == "checksum_mismatch"
        assert AuditMismatchReason.NO_CHECKSUM_PRESENT == "no_checksum_present"


class TestRetentionPolicy:
    """Tests for RetentionPolicy dataclass."""

    def test_defaults(self) -> None:
        policy = RetentionPolicy(name="default")
        assert policy.default_retention_days == 365
        assert policy.severity_overrides == {}
        assert policy.source_overrides == {}

    def test_with_overrides(self) -> None:
        policy = RetentionPolicy(
            name="strict",
            severity_overrides={"critical": 2555},
            source_overrides={"ai": 730},
        )
        assert policy.severity_overrides["critical"] == 2555


class TestRetentionDecision:
    """Tests for RetentionDecision enum."""

    def test_values(self) -> None:
        assert RetentionDecision.RETAIN == "retain"
        assert RetentionDecision.PURGE == "purge"
        assert RetentionDecision.ARCHIVE == "archive"
        assert RetentionDecision.RETAIN_UNTIL == "retain_until"


class TestAuditEventSeverity:
    """Tests for AuditEventSeverity enum."""

    def test_severity_values(self) -> None:
        assert AuditEventSeverity.LOW == "low"
        assert AuditEventSeverity.MEDIUM == "medium"
        assert AuditEventSeverity.HIGH == "high"
        assert AuditEventSeverity.CRITICAL == "critical"
