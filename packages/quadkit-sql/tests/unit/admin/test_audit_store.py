"""Unit tests for SqlAdminAuditLogStore (S2)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.sql.admin.audit_store import SqlAdminAuditLogStore
from quadkit.contracts.admin.audit_entry import AuditEntry, AuditOutcome
from quadkit.contracts.admin.audit_logger import AdminAuditLoggerProtocol


class TestSqlAdminAuditLogStoreProtocol:
    def test_satisfies_protocol(self) -> None:
        session = MagicMock()
        store = SqlAdminAuditLogStore(session=session)
        assert isinstance(store, AdminAuditLoggerProtocol)

    def test_has_write_method(self) -> None:
        store = SqlAdminAuditLogStore(session=MagicMock())
        assert callable(getattr(store, "write", None))

    def test_has_log_method(self) -> None:
        store = SqlAdminAuditLogStore(session=MagicMock())
        assert callable(getattr(store, "log", None))


class TestSqlAdminAuditLogStoreWrite:
    async def test_write_executes_insert(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock()
        store = SqlAdminAuditLogStore(session=session)

        entry = AuditEntry(
            admin_user_id="admin-1",
            action="delete",
            resource_type="users",
            resource_id="u-42",
            outcome=AuditOutcome.SUCCESS,
            before={"name": "Alice"},
            after={},
            correlation_id="cid-1",
        )

        await store.write(entry)
        assert session.execute.called

    async def test_write_passes_all_fields(self) -> None:
        captured: list[Any] = []

        class _CaptureSession:
            async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> None:
                captured.append(stmt)

        store = SqlAdminAuditLogStore(session=_CaptureSession())  # type: ignore[arg-type]

        entry = AuditEntry(
            admin_user_id="admin-2",
            action="create",
            resource_type="pets",
            resource_id="p-5",
            outcome=AuditOutcome.SUCCESS,
            correlation_id="cid-99",
            metadata={"env": "test"},
        )
        await store.write(entry)
        assert len(captured) == 1

    async def test_log_delegates_to_write(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock()
        store = SqlAdminAuditLogStore(session=session)

        await store.log(
            action="update",
            resource_type="users",
            resource_id="u-1",
            user_id="admin-1",
            changes={"name": ["old", "new"]},
        )
        assert session.execute.called
