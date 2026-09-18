"""Tests for audit protocol definitions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from quadkit.contracts.audit import (
    AuditEntry,
    AuditLoggerProtocol,
    AuditQuery,
    AuditStoreProtocol,
)


class TestAuditStoreProtocol:
    """Tests for AuditStoreProtocol."""

    @pytest.mark.asyncio
    async def test_has_append_method(self) -> None:
        class Store:
            async def append(self, entry: AuditEntry) -> None: pass
            async def query(self, query: AuditQuery) -> list[AuditEntry]: return []
            async def count(self, query: AuditQuery) -> int: return 0
            async def delete_expired(self, cutoff: datetime) -> int: return 0

        store = Store()
        entry = AuditEntry(action="test", actor_id="actor")
        await store.append(entry)

    @pytest.mark.asyncio
    async def test_has_query_method(self) -> None:
        class Store:
            async def append(self, entry: AuditEntry) -> None: pass
            async def query(self, query: AuditQuery) -> list[AuditEntry]: return []
            async def count(self, query: AuditQuery) -> int: return 0
            async def delete_expired(self, cutoff: datetime) -> int: return 0

        store = Store()
        result = await store.query(AuditQuery())
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_has_delete_expired_method(self) -> None:
        class Store:
            async def append(self, entry: AuditEntry) -> None: pass
            async def query(self, query: AuditQuery) -> list[AuditEntry]: return []
            async def count(self, query: AuditQuery) -> int: return 0
            async def delete_expired(self, cutoff: datetime) -> int: return 0

        store = Store()
        assert await store.delete_expired(datetime.now(UTC)) == 0

    def test_is_runtime_checkable(self) -> None:
        class Store:
            async def append(self, entry: AuditEntry) -> None: pass
            async def query(self, query: AuditQuery) -> list[AuditEntry]: return []
            async def count(self, query: AuditQuery) -> int: return 0
            async def delete_expired(self, cutoff: datetime) -> int: return 0

        assert isinstance(Store(), AuditStoreProtocol)


class TestAuditLoggerProtocol:
    """Tests for AuditLoggerProtocol."""

    @pytest.mark.asyncio
    async def test_has_log_method(self) -> None:
        class Logger:
            async def log(self, entry: AuditEntry) -> None: pass
            async def query(self, query: AuditQuery) -> list[AuditEntry]: return []

        logger = Logger()
        entry = AuditEntry(action="test", actor_id="actor")
        await logger.log(entry)

    def test_is_runtime_checkable(self) -> None:
        class Logger:
            async def log(self, entry: AuditEntry) -> None: pass
            async def query(self, query: AuditQuery) -> list[AuditEntry]: return []

        assert isinstance(Logger(), AuditLoggerProtocol)
