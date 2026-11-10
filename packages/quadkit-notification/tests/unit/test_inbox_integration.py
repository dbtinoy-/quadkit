"""Local framework composition and pagination regressions for the inbox."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from quadkit.app.base import Application
from quadkit.notification.config import InboxConfig
from quadkit.notification.inbox.memory import InMemoryInboxStore
from quadkit.notification.inbox.module import InboxModule
from quadkit.notification.inbox.service import InboxService


@pytest.mark.asyncio
async def test_application_resolves_persistent_inbox_through_module_graph(
    tmp_path: Path,
) -> None:
    DatabaseModule = pytest.importorskip("quadkit.sql.module").DatabaseModule
    path = tmp_path / "di.sqlite"

    async def application() -> Application:
        db = DatabaseModule.configure(f"sqlite+aiosqlite:///{path}")
        inbox = replace(InboxModule.configure(), imports=[db])
        app = Application()
        app.add_modules([db, inbox])
        await app.start()
        return app

    app = await application()
    try:
        service = await app.container.resolve(InboxService)
        message = await service.send("alice", "Private", "Hello")
        assert await service.get_message_for_user(message.id, "bob") is None
    finally:
        await app.stop()

    app = await application()
    try:
        service = await app.container.resolve(InboxService)
        assert await service.get_message_for_user(message.id, "alice") is not None
        assert await service.get_message_for_user(message.id, "bob") is None
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_mark_on_fetch_affects_only_the_requested_page() -> None:
    service = InboxService(
        InMemoryInboxStore(),
        config=InboxConfig(max_page_size=2, mark_read_on_fetch=True),
    )
    for i in range(5):
        await service.send("alice", f"{i}", "body")
    await service.send("bob", "their message", "body")
    page = await service.get_inbox("alice", limit=1, offset=2)
    assert len(page) == 1
    assert page[0].read is True
    assert await service.count_unread("alice") == 4
    assert await service.count_unread("bob") == 1


@pytest.mark.asyncio
async def test_sqlite_bounded_pages_are_owner_scoped_and_stably_ordered(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    from quadkit.contracts.notification.inbox import InboxMessage
    from quadkit.notification.inbox.database import DatabaseInboxStore

    SQLiteProvider = pytest.importorskip(
        "quadkit.sql.providers.sqlite_provider"
    ).SQLiteProvider
    provider = SQLiteProvider(str(tmp_path / "pages.sqlite"))
    await provider.connect()
    try:
        sql_store = DatabaseInboxStore(provider)
        memory_store = InMemoryInboxStore()
        timestamp = datetime(2026, 1, 1, tzinfo=UTC)
        for store in (sql_store, memory_store):
            for index in range(5):
                message = replace(
                    InboxMessage.create("alice", str(index), "body"),
                    id=f"id-{index}",
                    created_at=timestamp,
                    read=index == 3,
                )
                await store.save(message)
            await store.save(replace(
                InboxMessage.create("bob", "private", "body"),
                id="id-bob", created_at=timestamp,
            ))
            service = InboxService(store)
            assert [m.id for m in await service.get_inbox("alice", limit=2, offset=1)] == [
                "id-3", "id-2"
            ]
            assert [m.id for m in await service.get_inbox(
                "alice", unread_only=True, limit=2, offset=1
            )] == ["id-2", "id-1"]
            assert await service.get_inbox("alice", offset=5) == []
            assert await service.get_message_for_user("id-bob", "alice") is None
            auto_mark = InboxService(
                store, config=InboxConfig(max_page_size=2, mark_read_on_fetch=True)
            )
            page = await auto_mark.get_inbox("alice", unread_only=True, limit=1, offset=1)
            assert [m.id for m in page] == ["id-2"]
            assert page[0].read is True
            assert await service.count_unread("alice") == 3
            assert await service.count_unread("bob") == 1
    finally:
        await provider.disconnect()
