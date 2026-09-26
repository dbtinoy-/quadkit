"""Tests for the in-memory session repository adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from auth_web.repository import InMemorySessionRepository


def payload(session_id: str, user_id: str = "u-1") -> dict:
    return {
        "session_id": session_id,
        "user_id": user_id,
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }


async def test_insert_then_find_active() -> None:
    repo = InMemorySessionRepository()

    await repo.insert(payload("s-1"))

    row = await repo.find_active("s-1")
    assert row is not None
    assert row["user_id"] == "u-1"
    assert row["active"] is True


async def test_expired_session_is_not_active() -> None:
    repo = InMemorySessionRepository()
    expired = payload("s-exp")
    expired["expires_at"] = datetime.now(UTC) - timedelta(minutes=1)

    await repo.insert(expired)

    assert await repo.find_active("s-exp") is None


async def test_revoke_and_find_active_by_user() -> None:
    repo = InMemorySessionRepository()
    await repo.insert(payload("s-a"))
    await repo.insert(payload("s-b", user_id="u-2"))

    rows = await repo.find_active_by_user("u-1", cutoff=datetime.now(UTC))
    assert [row["session_id"] for row in rows] == ["s-a"]

    await repo.revoke("s-a")
    assert await repo.find_active("s-a") is None


async def test_revoke_all_scopes_to_user() -> None:
    repo = InMemorySessionRepository()
    await repo.insert(payload("s-1"))
    await repo.insert(payload("s-2"))
    await repo.insert(payload("s-other", user_id="u-2"))

    await repo.revoke_all("u-1")

    assert await repo.find_active("s-1") is None
    assert await repo.find_active("s-2") is None
    assert await repo.find_active("s-other") is not None


async def test_update_activity_touches_timestamp() -> None:
    repo = InMemorySessionRepository()
    await repo.insert(payload("s-1"))
    later = datetime.now(UTC) + timedelta(minutes=5)

    await repo.update_activity("s-1", later)

    row = await repo.find_active("s-1")
    assert row is not None
    assert row["last_active_at"] == later
