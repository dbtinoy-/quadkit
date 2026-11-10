"""Real-store recovery proofs for trusted, idempotent inbox effects."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.notification.inbox import INBOX_SENT_HOOK
from quadkit.hooks.ambient import use
from quadkit.hooks.registry import HookRegistry
from quadkit.notification.inbox.database import DatabaseInboxStore
from quadkit.notification.inbox.memory import InMemoryInboxStore
from quadkit.notification.inbox.service import InboxService
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "sqlite"])
async def test_recovery_conflict_hook_and_deletion(tmp_path, backend):
    provider = SQLiteProvider(str(tmp_path / "inbox.db"))
    if backend == "sqlite":
        await provider.connect()
    try:
        store = (
            DatabaseInboxStore(provider)
            if backend == "sqlite"
            else InMemoryInboxStore()
        )
        service = InboxService(store)
        calls = []
        registry = HookRegistry("send-once-test")

        async def broken_hook(**kw):
            calls.append(kw["message"].id)
            raise RuntimeError("best effort observer fails")

        registry.register_action(INBOX_SENT_HOOK, broken_hook)
        with use(registry):
            first = await service.send_once(
                "publish:post1", "owner", "Published", "Title", post_id="post1"
            )
            replay = await service.send_once(
                "publish:post1", "owner", "Published", "Title", post_id="post1"
            )
        assert replay == first
        assert calls == [first.message_id]
        assert len(await service.get_inbox("owner")) == 1
        for recipient, title in [("other", "Published"), ("owner", "Changed")]:
            with pytest.raises(ValueError, match="conflicts"):
                await service.send_once(
                    "publish:post1", recipient, title, "Title", post_id="post1"
                )
        assert await service.get_inbox("other") == []
        await service.mark_read(first.message_id, "other")
        await service.delete(first.message_id, "other")
        assert not (await service.get_message_for_user(first.message_id, "owner")).read
        await service.mark_read(first.message_id, "owner")
        assert (await service.get_message_for_user(first.message_id, "owner")).read
        await service.clear_all("owner")
        if backend == "sqlite":
            await provider.disconnect()
            await provider.connect()
            service = InboxService(DatabaseInboxStore(provider))
        replay = await service.send_once(
            "publish:post1", "owner", "Published", "Title", post_id="post1"
        )
        assert replay == first
        assert await service.get_inbox("owner") == []  # never resurrect deleted mail
    finally:
        if backend == "sqlite":
            await provider.disconnect()


@pytest.mark.asyncio
async def test_failed_insert_rolls_back_receipt_then_explicit_retry_succeeds(tmp_path):
    db = SQLiteProvider(str(tmp_path / "failure.db"))
    await db.connect()
    try:
        store = DatabaseInboxStore(db)
        await store.list_for_user("owner")
        await db.execute_query(
            "CREATE TRIGGER reject_inbox BEFORE INSERT ON notification_inbox_messages BEGIN SELECT RAISE(ABORT, 'inbox rejected'); END"
        )
        service = InboxService(store)
        with pytest.raises(Exception, match="inbox rejected"):
            await service.send_once("publish:post2", "owner", "Published", "Title")
        assert await service.get_inbox("owner") == []
        rows = await db.execute_query(
            "SELECT * FROM notification_inbox_messages_receipts"
        )
        assert rows.rows == []
        await db.execute_query("DROP TRIGGER reject_inbox")
        first = await service.send_once("publish:post2", "owner", "Published", "Title")
        assert (
            await service.send_once("publish:post2", "owner", "Published", "Title")
        ).message_id == first.message_id
        assert len(await service.get_inbox("owner")) == 1
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_concurrent_independent_sql_connections_deliver_once(tmp_path):
    providers = [SQLiteProvider(str(tmp_path / "concurrent.db")) for _ in range(2)]
    for db in providers:
        await db.connect()
    try:
        services = [InboxService(DatabaseInboxStore(db)) for db in providers]
        # Bootstrap before concurrency; the insert/key race still uses two connections.
        for service in services:
            await service.get_inbox("owner")
        messages = await asyncio.gather(
            *(
                s.send_once("publish:post3", "owner", "Published", "Title")
                for s in services
            )
        )
        assert messages[0] == messages[1]
        assert len(await services[0].get_inbox("owner")) == 1
    finally:
        for db in providers:
            await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["", " ", "x" * 513, "bad\x00key"])
async def test_invalid_key_refuses_without_mutation(key):
    service = InboxService()
    with pytest.raises(ValueError, match="delivery key"):
        await service.send_once(key, "owner", "Title", "Body")
    assert await service.get_inbox("owner") == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": object()},
        {"value": {1: "coerced"}},
    ],
)
async def test_non_json_metadata_refuses_without_mutation(metadata):
    service = InboxService()
    with pytest.raises((ValueError, TypeError)):
        await service.send_once("effect", "owner", "Title", "Body", **metadata)
    assert await service.get_inbox("owner") == []


@pytest.mark.asyncio
async def test_legacy_store_does_not_silently_fall_back_to_duplicate_send():
    class Legacy:
        save = AsyncMock()

    store = Legacy()
    service = InboxService(store)
    with pytest.raises(TypeError, match="atomic send_once"):
        await service.send_once("effect", "owner", "Title", "Body")
    store.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_outer_business_transaction_is_refused_before_receipt_or_hook(tmp_path):
    db = SQLiteProvider(str(tmp_path / "outer.db"))
    await db.connect()
    try:
        service = InboxService(DatabaseInboxStore(db))
        async with db.transaction():
            with pytest.raises(RuntimeError, match="committed-only"):
                await service.send_once("effect", "owner", "Title", "Body")
        assert await service.get_inbox("owner") == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_receipts_do_not_retain_deleted_private_content(tmp_path):
    db = SQLiteProvider(str(tmp_path / "retention.db"))
    await db.connect()
    try:
        service = InboxService(DatabaseInboxStore(db))
        receipt = await service.send_once(
            "effect",
            "owner",
            "Private subject",
            "Private body",
            secret="private metadata",
        )
        await service.clear_all("owner")
        rows = await db.execute_query(
            "SELECT * FROM notification_inbox_messages_receipts"
        )
        assert len(rows.rows) == 1
        assert set(rows.rows[0]) == {
            "delivery_key",
            "payload_digest",
            "message_id",
            "created_at",
        }
        assert rows.rows[0]["message_id"] == receipt.message_id
        assert len(rows.rows[0]["payload_digest"]) == 64
        assert await service.get_inbox("owner") == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_memory_key_cannot_overwrite_an_existing_message_id():
    from dataclasses import replace

    from quadkit.contracts.notification.inbox import InboxMessage

    store = InMemoryInboxStore()
    original = InboxMessage.create("owner", "Private", "Body")
    await store.save(original)
    with pytest.raises(ValueError, match="already exists"):
        await store.save_once("new-effect", replace(original, user_id="other"))
    assert await store.get(original.id) == original


def test_intent_digest_preserves_json_types_and_ignores_dict_order():
    from dataclasses import replace

    from quadkit.contracts.notification.inbox import InboxMessage
    from quadkit.notification.inbox.idempotency import fingerprint

    original = InboxMessage.create(
        "owner", "Title", "Body", metadata={"a": True, "b": 1.0}
    )
    assert fingerprint(original) == fingerprint(
        replace(original, metadata={"b": 1.0, "a": True})
    )
    assert fingerprint(original) != fingerprint(
        replace(original, metadata={"a": 1, "b": 1.0})
    )
    assert fingerprint(original) != fingerprint(
        replace(original, metadata={"a": True, "b": 1})
    )


@pytest.mark.asyncio
async def test_unrelated_save_once_method_is_not_implicitly_trusted():
    class Legacy:
        save_once = AsyncMock()
        save = AsyncMock()

    store = Legacy()
    with pytest.raises(TypeError, match="atomic send_once"):
        await InboxService(store).send_once("effect", "owner", "Title", "Body")
    store.save_once.assert_not_awaited()
    store.save.assert_not_awaited()
