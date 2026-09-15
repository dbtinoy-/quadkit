"""Tests for AuditEntry, AuditQuery, AuditEventSeverity."""

from __future__ import annotations

import pytest
from datetime import UTC, datetime

from quadkit.contracts.audit.types import (
    AuditEntry,
    AuditEventSeverity,
    AuditMismatch,
    AuditQuery,
    RetentionDecision,
    RetentionPolicy,
)


class TestAuditEventSeverity:
    def test_severity_values_are_strings(self) -> None:
        assert isinstance(AuditEventSeverity.LOW, str)
        assert isinstance(AuditEventSeverity.CRITICAL, str)

    def test_all_four_levels_exist(self) -> None:
        members = list(AuditEventSeverity)
        assert len(members) == 4

    def test_string_values(self) -> None:
        assert AuditEventSeverity.LOW == "low"
        assert AuditEventSeverity.MEDIUM == "medium"
        assert AuditEventSeverity.HIGH == "high"
        assert AuditEventSeverity.CRITICAL == "critical"


class TestAuditEntry:
    def test_audit_entry_is_frozen(self) -> None:
        entry = AuditEntry(action="auth.login", actor_id="u1")
        with pytest.raises((AttributeError, TypeError)):
            entry.actor_id = "hacked"  # type: ignore[misc]

    def test_audit_entry_has_utc_timestamp_by_default(self) -> None:
        entry = AuditEntry(action="auth.login", actor_id="u1")
        assert entry.occurred_at.tzinfo is not None

    def test_metadata_defaults_to_empty_dict(self) -> None:
        entry = AuditEntry(action="auth.login", actor_id="u1")
        assert entry.metadata == {}

    def test_severity_defaults_to_medium(self) -> None:
        entry = AuditEntry(action="auth.login", actor_id="u1")
        assert entry.severity == AuditEventSeverity.MEDIUM

    def test_source_defaults_to_empty(self) -> None:
        entry = AuditEntry(action="auth.login", actor_id="u1")
        assert entry.source == ""

    def test_tenant_id_defaults_to_none(self) -> None:
        entry = AuditEntry(action="auth.login", actor_id="u1")
        assert entry.tenant_id is None

    def test_no_resource_table_field(self) -> None:
        entry = AuditEntry(action="test", actor_id="actor")
        assert not hasattr(entry, "resource_table")

    def test_no_timestamp_field(self) -> None:
        entry = AuditEntry(action="test", actor_id="actor")
        assert not hasattr(entry, "timestamp")

    def test_metadata_independent_between_instances(self) -> None:
        e1 = AuditEntry(action="a", actor_id="1")
        e2 = AuditEntry(action="b", actor_id="2")
        assert e1.metadata is not e2.metadata


class TestAuditEntryNewFields:
    """LXF-003: New AuditEntry fields for audit enrichment."""

    def test_correlation_id_defaults_to_none(self) -> None:
        entry = AuditEntry(action="test", actor_id="u")
        assert entry.correlation_id is None

    def test_correlation_id_is_string_when_set(self) -> None:
        entry = AuditEntry(action="test", actor_id="u", correlation_id="corr-abc")
        assert isinstance(entry.correlation_id, str)
        assert entry.correlation_id == "corr-abc"

    def test_causation_id_defaults_to_none(self) -> None:
        entry = AuditEntry(action="test", actor_id="u")
        assert entry.causation_id is None

    def test_causation_id_is_string_when_set(self) -> None:
        entry = AuditEntry(action="test", actor_id="u", causation_id="cause-xyz")
        assert isinstance(entry.causation_id, str)
        assert entry.causation_id == "cause-xyz"

    def test_command_payload_hash_defaults_to_none(self) -> None:
        entry = AuditEntry(action="test", actor_id="u")
        assert entry.command_payload_hash is None

    def test_command_payload_hash_is_bytes_when_set(self) -> None:
        entry = AuditEntry(action="test", actor_id="u", command_payload_hash=b"1234")
        assert isinstance(entry.command_payload_hash, bytes)
        assert entry.command_payload_hash == b"1234"

    def test_payload_size_bytes_defaults_to_none(self) -> None:
        entry = AuditEntry(action="test", actor_id="u")
        assert entry.payload_size_bytes is None

    def test_payload_size_bytes_is_int_when_set(self) -> None:
        entry = AuditEntry(action="test", actor_id="u", payload_size_bytes=2048)
        assert isinstance(entry.payload_size_bytes, int)
        assert entry.payload_size_bytes == 2048


class TestAuditQuery:
    def test_defaults(self) -> None:
        q = AuditQuery()
        assert q.actor_id is None
        assert q.limit == 100
        assert q.offset == 0
        assert q.source is None
        assert q.tenant_id is None
        assert q.severity is None
        assert q.until is None

    def test_full_construction(self) -> None:
        now = datetime.now(UTC)
        q = AuditQuery(
            actor_id="u1",
            action="login",
            source="auth",
            severity=AuditEventSeverity.HIGH,
            since=now,
            limit=10,
        )
        assert q.actor_id == "u1"
        assert q.action == "login"
        assert q.source == "auth"
        assert q.severity == AuditEventSeverity.HIGH
        assert q.since == now
        assert q.limit == 10


class TestAuditQueryNewFields:
    """LXF-003: New AuditQuery correlation_id field."""

    def test_correlation_id_defaults_to_none(self) -> None:
        q = AuditQuery()
        assert q.correlation_id is None

    def test_correlation_id_is_string_when_set(self) -> None:
        q = AuditQuery(correlation_id="corr-abc")
        assert isinstance(q.correlation_id, str)
        assert q.correlation_id == "corr-abc"


class TestRetentionPolicy:
    def test_defaults(self) -> None:
        policy = RetentionPolicy(name="default")
        assert policy.default_retention_days == 365
        assert policy.severity_overrides == {}
        assert policy.source_overrides == {}

    def test_is_frozen(self) -> None:
        policy = RetentionPolicy(name="p")
        with pytest.raises((AttributeError, TypeError)):
            policy.name = "changed"  # type: ignore[misc]
