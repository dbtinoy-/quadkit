"""Cooldown-window semantics for quota backends.

A 429 marks a cascade entry exhausted for a short cooldown (``until``);
a 402 (or a legacy call without ``until``) lasts the rest of the UTC day.
Stale rows whose ``exhausted_until`` is ``None`` are NOT exhausted, so
pre-cooldown production rows self-heal after deploy.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from quadkit.ai.llm.routing.backends.database import DatabaseQuotaBackend
from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend

KEY = "openrouter:google/gemma-4-31b-it:free"


# ── Memory backend ───────────────────────────────────────────────────────────


async def test_mark_exhausted_with_future_until_blocks():
    backend = InMemoryQuotaBackend()
    await backend.mark_exhausted(KEY, until=datetime.now(UTC) + timedelta(seconds=300))
    assert await backend.is_exhausted(KEY) is True


async def test_mark_exhausted_with_past_until_expires():
    backend = InMemoryQuotaBackend()
    await backend.mark_exhausted(KEY, until=datetime.now(UTC) - timedelta(seconds=1))
    assert await backend.is_exhausted(KEY) is False


async def test_mark_exhausted_default_lasts_rest_of_day():
    backend = InMemoryQuotaBackend()
    await backend.mark_exhausted(KEY)  # legacy: until=None
    assert await backend.is_exhausted(KEY) is True


async def test_unmarked_provider_not_exhausted():
    backend = InMemoryQuotaBackend()
    assert await backend.is_exhausted(KEY) is False


# ── Database backend (fake connection) ───────────────────────────────────────


class _FakeConn:
    """Minimal stand-in for an asyncpg connection over one table."""

    def __init__(self, store: dict) -> None:
        self.store = store

    async def execute(self, sql: str, *params) -> None:
        if "exhausted_until" in sql and "DO UPDATE" in sql:
            self.store[(params[0], params[1])] = {"exhausted_until": params[2]}

    async def fetchrow(self, sql: str, *params):
        row = self.store.get((params[0], params[1]))
        if row is None:
            return None
        return {
            "provider": params[0],
            "usage_date": params[1],
            "success_count": 0,
            "error_count": 0,
            "is_exhausted": True,
            "exhausted_until": row["exhausted_until"],
        }


class _FakeDb:
    """Fake DatabaseProviderProtocol wrapping a shared row store."""

    def __init__(self) -> None:
        self.store: dict = {}

    @asynccontextmanager
    async def scoped_context(self):
        yield self

    async def get_scoped_connection(self) -> _FakeConn:
        return _FakeConn(self.store)


async def test_db_backend_future_until_blocks():
    backend = DatabaseQuotaBackend(db=_FakeDb())
    await backend.mark_exhausted(KEY, until=datetime.now(UTC) + timedelta(seconds=300))
    assert await backend.is_exhausted(KEY) is True


async def test_db_backend_past_until_expires():
    backend = DatabaseQuotaBackend(db=_FakeDb())
    await backend.mark_exhausted(KEY, until=datetime.now(UTC) - timedelta(seconds=1))
    assert await backend.is_exhausted(KEY) is False


async def test_db_backend_null_until_not_exhausted():
    """Stale pre-cooldown rows (exhausted_until NULL) self-heal."""
    db = _FakeDb()
    backend = DatabaseQuotaBackend(db=db)
    db.store[(KEY, backend._today())] = {"exhausted_until": None}
    assert await backend.is_exhausted(KEY) is False
