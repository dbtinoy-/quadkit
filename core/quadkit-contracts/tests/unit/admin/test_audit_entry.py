"""Tests for AuditEntry value object and AuditOutcome enum."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from quadkit.contracts.admin.audit_entry import AuditEntry, AuditOutcome


class TestAuditEntryShape:
    """AuditEntry is a frozen dataclass with the expected fields."""

    def test_is_frozen_dataclass(self) -> None:
        entry = AuditEntry(
            admin_user_id="u1",
            action="delete_user",
            resource_type="users",
            resource_id="42",
            outcome="success",
            before={},
            after={},
            correlation_id="c1",
            request_id="r1",
            request_ip="1.2.3.4",
        )
        assert is_dataclass(entry)
        with pytest.raises(FrozenInstanceError):
            entry.outcome = "denied"  # type: ignore[misc]

    def test_outcome_str_enum_values(self) -> None:
        values = {o.value for o in AuditOutcome}
        assert values == {"success", "denied", "errored"}

    def test_outcome_accepts_enum_member(self) -> None:
        entry = AuditEntry(
            admin_user_id="u1",
            action="delete_user",
            resource_type="users",
            resource_id="42",
            outcome=AuditOutcome.SUCCESS,
        )
        assert entry.outcome == AuditOutcome.SUCCESS

    def test_outcome_accepts_raw_string(self) -> None:
        entry = AuditEntry(
            admin_user_id="u1",
            action="delete_user",
            resource_type="users",
            resource_id="42",
            outcome="denied",
        )
        assert entry.outcome == "denied"

    def test_defaults_are_empty(self) -> None:
        entry = AuditEntry(
            admin_user_id="u1",
            action="read",
            resource_type="users",
            resource_id=None,
            outcome=AuditOutcome.SUCCESS,
        )
        assert entry.before == {}
        assert entry.after == {}
        assert entry.correlation_id is None
        assert entry.request_id is None
        assert entry.request_ip is None
        assert entry.metadata == {}
