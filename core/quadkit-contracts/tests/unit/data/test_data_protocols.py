"""Tests for data protocols."""

from __future__ import annotations

import pytest

from quadkit.contracts.data import OutboxStoreProtocol


class TestOutboxStoreProtocol:
    """Tests for OutboxStoreProtocol."""

    @pytest.mark.asyncio
    async def test_protocol_is_runtime_checkable(self) -> None:
        """Verify protocol is runtime checkable."""
        from quadkit.contracts.data.outbox import OutboxStoreProtocol

        class MockOutbox:
            async def append_batch(self, events):
                pass

            async def fetch_pending(self, limit=100):
                return []

            async def mark_delivered(self, event_id):
                pass

            async def mark_failed(self, event_id, error):
                pass

        mock = MockOutbox()
        assert isinstance(mock, OutboxStoreProtocol)


class TestDataProtocolsExports:
    """Tests for data module exports."""

    def test_outbox_protocol_exported(self) -> None:
        """Verify OutboxStoreProtocol is exported."""
        from quadkit.contracts.data import OutboxStoreProtocol
        assert OutboxStoreProtocol is not None

    def test_repository_protocol_exported(self) -> None:
        """Verify RepositoryProtocol is exported."""
        from quadkit.contracts.data import RepositoryProtocol
        assert RepositoryProtocol is not None

    def test_unit_of_work_protocol_exported(self) -> None:
        """Verify UnitOfWorkProtocol is exported."""
        from quadkit.contracts.data.sql import UnitOfWorkProtocol
        assert UnitOfWorkProtocol is not None


class TestDataIdentifiers:
    """Tests for data identifiers."""

    def test_identifier_types_exported(self) -> None:
        """Verify identifier types are exported."""
        from quadkit.contracts.data.identifiers import Table, Column, Schema

        t = Table("users")
        assert t.name == "users"

        c = Column("email")
        assert c.name == "email"

        s = Schema("public")
        assert s.name == "public"