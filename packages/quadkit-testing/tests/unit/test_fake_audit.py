from __future__ import annotations

import pytest

from quadkit.contracts.audit import AuditEntry, AuditEventSeverity, AuditQuery
from quadkit.testing.fakes import FakeAuditLogger


@pytest.mark.asyncio
async def test_fake_audit_logger_log_and_query() -> None:
    audit = FakeAuditLogger()

    entry = AuditEntry(
        action="admin.resource.create",
        actor_id="admin-1",
        resource_type="resource",
        resource_id="r-1",
        outcome="success",
        severity=AuditEventSeverity.MEDIUM,
        source="unit-test",
    )
    await audit.log(entry)

    results = await audit.query(AuditQuery(actor_id="admin-1", action="admin.resource.create"))
    assert len(results) == 1
    assert results[0].source == "unit-test"


@pytest.mark.asyncio
async def test_fake_audit_logger_clear_resets_state() -> None:
    audit = FakeAuditLogger()
    entry = AuditEntry(
        action="admin.resource.delete",
        actor_id="admin-1",
        resource_type="resource",
        resource_id="r-2",
        outcome="success",
        severity=AuditEventSeverity.CRITICAL,
    )
    await audit.log(entry)
    audit.clear()

    results = await audit.query(AuditQuery())
    assert results == []
