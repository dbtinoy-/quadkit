from __future__ import annotations

"""Contract compliance suites for audit protocol implementations."""

import abc
from datetime import UTC, datetime
from typing import Any
import uuid

import pytest

__all__ = ["AuditLoggerCompliance", "AuditStoreCompliance"]


def _make_entry(**kwargs: Any) -> object:
    """Build a minimal AuditEntry for compliance tests.

    Args:
        **kwargs: Field overrides for AuditEntry.

    Returns:
        AuditEntry with sensible defaults.
    """
    from quadkit.contracts.audit.types import AuditEntry

    defaults: dict[str, Any] = {
        "action": "user.login",
        "actor_id": f"actor-{uuid.uuid4().hex[:8]}",
        "resource_type": "User",
        "resource_id": f"user-{uuid.uuid4().hex[:8]}",
        "outcome": "success",
        "occurred_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return AuditEntry(**defaults)


class AuditLoggerCompliance(abc.ABC):
    """Compliance suite for AuditLoggerProtocol implementations.

    Subclass and implement create_logger() to run all compliance tests.
    """

    @abc.abstractmethod
    async def create_logger(self) -> Any:
        """Create the AuditLoggerProtocol implementation under test.

        Returns:
            A fresh instance implementing AuditLoggerProtocol.
        """
        ...

    @pytest.mark.asyncio
    async def test_log_does_not_raise(self) -> None:
        """log() completes without raising for a valid entry."""
        logger = await self.create_logger()
        entry = _make_entry()
        await logger.log(entry)

    @pytest.mark.asyncio
    async def test_log_creates_queryable_entry(self) -> None:
        """log() creates an entry that is returned by query()."""
        from quadkit.contracts.audit.types import AuditQuery

        logger = await self.create_logger()
        actor_id = f"actor-{uuid.uuid4().hex[:8]}"
        entry = _make_entry(actor_id=actor_id)
        await logger.log(entry)
        results = await logger.query(AuditQuery(actor_id=actor_id))
        assert len(results) >= 1
        assert any(r.actor_id == actor_id for r in results)

    @pytest.mark.asyncio
    async def test_log_with_metadata(self) -> None:
        """log() stores extra metadata fields."""
        from quadkit.contracts.audit.types import AuditQuery

        logger = await self.create_logger()
        actor_id = f"actor-{uuid.uuid4().hex[:8]}"
        entry = _make_entry(
            actor_id=actor_id, metadata={"ip": "127.0.0.1", "agent": "test"}
        )
        await logger.log(entry)
        results = await logger.query(AuditQuery(actor_id=actor_id))
        assert len(results) >= 1
        found = next(r for r in results if r.actor_id == actor_id)
        assert found.metadata.get("ip") == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_query_by_actor(self) -> None:
        """query() filters by actor_id."""
        from quadkit.contracts.audit.types import AuditQuery

        logger = await self.create_logger()
        actor_a = f"actor-{uuid.uuid4().hex[:8]}"
        actor_b = f"actor-{uuid.uuid4().hex[:8]}"
        await logger.log(_make_entry(actor_id=actor_a))
        await logger.log(_make_entry(actor_id=actor_b))
        results = await logger.query(AuditQuery(actor_id=actor_a))
        assert all(r.actor_id == actor_a for r in results)

    @pytest.mark.asyncio
    async def test_query_by_action(self) -> None:
        """query() filters by action name."""
        from quadkit.contracts.audit.types import AuditQuery

        logger = await self.create_logger()
        actor_id = f"actor-{uuid.uuid4().hex[:8]}"
        await logger.log(_make_entry(actor_id=actor_id, action="user.create"))
        await logger.log(_make_entry(actor_id=actor_id, action="user.delete"))
        results = await logger.query(AuditQuery(action="user.create"))
        assert all(r.action == "user.create" for r in results)

    @pytest.mark.asyncio
    async def test_query_returns_list(self) -> None:
        """query() always returns a list, even when empty."""
        from quadkit.contracts.audit.types import AuditQuery

        logger = await self.create_logger()
        results = await logger.query(AuditQuery(actor_id="no-such-actor-xyz"))
        assert isinstance(results, list)


class AuditStoreCompliance(abc.ABC):
    """Compliance suite for AuditStoreProtocol implementations.

    Subclass and implement create_store() to run all compliance tests.
    """

    @abc.abstractmethod
    async def create_store(self) -> Any:
        """Create the AuditStoreProtocol implementation under test.

        Returns:
            A fresh instance implementing AuditStoreProtocol.
        """
        ...

    @pytest.mark.asyncio
    async def test_append_does_not_raise(self) -> None:
        """append() completes without raising for a valid entry."""
        store = await self.create_store()
        await store.append(_make_entry())

    @pytest.mark.asyncio
    async def test_append_and_query_round_trip(self) -> None:
        """append() and query() round-trip an audit entry."""
        from quadkit.contracts.audit.types import AuditQuery

        store = await self.create_store()
        actor_id = f"actor-{uuid.uuid4().hex[:8]}"
        entry = _make_entry(actor_id=actor_id)
        await store.append(entry)
        results = await store.query(AuditQuery(actor_id=actor_id))
        assert len(results) >= 1
        assert any(r.actor_id == actor_id for r in results)

    @pytest.mark.asyncio
    async def test_count_reflects_appended(self) -> None:
        """count() returns correct count after appends."""
        from quadkit.contracts.audit.types import AuditQuery

        store = await self.create_store()
        actor_id = f"actor-{uuid.uuid4().hex[:8]}"
        await store.append(_make_entry(actor_id=actor_id))
        await store.append(_make_entry(actor_id=actor_id))
        count = await store.count(AuditQuery(actor_id=actor_id))
        assert count >= 2

    @pytest.mark.asyncio
    async def test_query_by_actor(self) -> None:
        """query() filters by actor_id."""
        from quadkit.contracts.audit.types import AuditQuery

        store = await self.create_store()
        actor_a = f"actor-{uuid.uuid4().hex[:8]}"
        actor_b = f"actor-{uuid.uuid4().hex[:8]}"
        await store.append(_make_entry(actor_id=actor_a))
        await store.append(_make_entry(actor_id=actor_b))
        results = await store.query(AuditQuery(actor_id=actor_a))
        assert all(r.actor_id == actor_a for r in results)

    @pytest.mark.asyncio
    async def test_query_empty_returns_list(self) -> None:
        """query() returns an empty list for unknown actor."""
        from quadkit.contracts.audit.types import AuditQuery

        store = await self.create_store()
        results = await store.query(AuditQuery(actor_id="no-such-actor-xyz"))
        assert isinstance(results, list)
        assert len(results) == 0
