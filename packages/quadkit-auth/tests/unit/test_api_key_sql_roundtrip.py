"""API key lifecycle regression tests against a real SQLite-backed repository.

Covers two previously-broken paths end to end:

- ``APIKeySqlRepository.insert`` crashed because ``scopes`` (a list) was
  passed raw to the driver — fixed by JSON-encoding in the CRUD layer.
- Expiry timestamps were naive local time and validation compared raw
  driver values (ISO text on SQLite) against ``datetime.now()`` — fixed
  by UTC timestamps plus aware normalization in ``APIKeyManager``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from quadkit.auth.authn.apikeys import APIKeyManager
from quadkit.auth.storage.apikey_sql import APIKeySqlRepository
from quadkit.sql.providers.sqlite_provider import SQLiteProvider

_CREATE_TABLE_SQL = """
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    name TEXT,
    key_hash TEXT,
    prefix TEXT,
    user_id TEXT,
    scopes TEXT,
    expires_at TEXT,
    revoked_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    last_used_at TEXT,
    last_used_ip TEXT
)
"""


@pytest.fixture
async def manager():
    """APIKeyManager backed by the SQL repository over in-memory SQLite."""
    provider = SQLiteProvider(database_path=":memory:")
    await provider.connect()
    await provider.execute(_CREATE_TABLE_SQL)
    try:
        yield APIKeyManager(APIKeySqlRepository(provider))
    finally:
        await provider.connection_manager.disconnect()


@pytest.mark.asyncio
async def test_create_and_validate_key_round_trip(manager) -> None:
    """Creating a key with scopes persists and validates via the SQL repo."""
    raw_key, created = await manager.create_key(
        user_id="user-1",
        name="ci key",
        scopes=["orders:read", "orders:write"],
        expires_days=30,
    )
    assert created.scopes == ["orders:read", "orders:write"]
    assert created.expires_at is not None
    assert created.expires_at.tzinfo is not None  # aware UTC

    validated = await manager.validate_key(raw_key)
    assert validated is not None
    assert validated.key_id == created.key_id
    assert validated.scopes == ["orders:read", "orders:write"]
    assert validated.expires_at == created.expires_at


@pytest.mark.asyncio
async def test_validate_key_rejects_expired_key(manager) -> None:
    """An expired key stored as ISO text (SQLite) is rejected, not crashed on."""
    raw_key, created = await manager.create_key("user-2", "short-lived", expires_days=1)
    assert created.expires_at is not None

    # Backdate the stored expiry by 2 days, as text — the SQLite driver shape.
    expired = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    await manager._repo.update_last_used(created.key_id, None)  # noqa: SLF001 — test-only
    rows = await manager._repo.find_by_prefix(raw_key[:8])
    await manager._repo._db.execute(  # noqa: SLF001 — test-only
        "UPDATE api_keys SET expires_at = ? WHERE id = ?", [expired, created.key_id]
    )
    assert rows  # sanity: key exists

    assert await manager.validate_key(raw_key) is None


@pytest.mark.asyncio
async def test_validate_key_rejects_unknown_key(manager) -> None:
    """Unknown keys return None without error."""
    await manager.create_key("user-3", "key", expires_days=30)
    assert await manager.validate_key("sk_live_doesnotexist") is None
