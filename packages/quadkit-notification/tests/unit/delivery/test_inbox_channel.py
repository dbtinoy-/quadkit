"""Bound-account delivery and durable worker crash/restart recovery."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from quadkit.auth.storage._sql_store import SQLUserStore
from quadkit.contracts.notification.delivery import DeliveryStatus
from quadkit.contracts.notification.types import DeliveryMessage
from quadkit.notification.delivery import (
    InboxDeliveryChannel,
    NotificationDeliveryDispatcher,
    SqlDeliveryStore,
    flush_retries,
)
from quadkit.notification.inbox.database import DatabaseInboxStore
from quadkit.notification.inbox.service import InboxService
from quadkit.primitives import clock
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


class MutableClock:
    def __init__(self):
        self.value = datetime(2030, 1, 1, tzinfo=UTC)

    def now(self):
        return self.value

    def monotonic(self):
        return self.value.timestamp()

    def timestamp(self):
        return self.value.timestamp()

    def time(self):
        return self.value.timestamp()


@pytest.mark.asyncio
async def test_real_account_and_acknowledgement_crash_recover_without_duplicate(
    tmp_path,
):
    path = str(tmp_path / "delivery.db")
    db = SQLiteProvider(path)
    await db.connect()
    timer = MutableClock()
    try:
        users = SQLUserStore(db)
        owner = await users.create_user("editor", "editor@example.test", None)
        other = await users.create_user("other", "other@example.test", None)
        inbox = InboxService(DatabaseInboxStore(db))
        channel = InboxDeliveryChannel(
            inbox, users.get_user_by_email, recipient_email="editor@example.test"
        )
        dispatcher = NotificationDeliveryDispatcher([channel])
        queue = SqlDeliveryStore(db)
        message = DeliveryMessage(
            "inbox",
            "editor@example.test",
            "Post published",
            "Committed title",
            {
                "effect_key": "post-published:post1",
                "recipient_user_id": owner.user_id,
                "post_id": "post1",
                "status": "published",
            },
        )
        with clock.use(timer):
            delivery_id = await queue.create_pending(message)
            original = queue.mark_delivered
            queue.mark_delivered = AsyncMock(
                side_effect=RuntimeError("crash before acknowledgement")
            )
            with pytest.raises(RuntimeError, match="acknowledgement"):
                await flush_retries(queue, dispatcher, lease_seconds=10)
            queue.mark_delivered = original
            stored = await inbox.get_inbox(owner.user_id)
            assert len(stored) == 1
            message_id = stored[0].id
            assert await inbox.get_inbox(other.user_id) == []
            assert await inbox.get_message_for_user(message_id, other.user_id) is None
            # Cold connections/account lookup/store state; only SQLite carries data.
            await db.disconnect()
            db = SQLiteProvider(path)
            await db.connect()
            users = SQLUserStore(db)
            inbox = InboxService(DatabaseInboxStore(db))
            queue = SqlDeliveryStore(db)
            channel = InboxDeliveryChannel(
                inbox, users.get_user_by_email, recipient_email="editor@example.test"
            )
            timer.value += timedelta(seconds=11)
            assert (
                await flush_retries(queue, NotificationDeliveryDispatcher([channel]))
                == 1
            )
            assert (
                await queue.get_delivery(delivery_id)
            ).status == DeliveryStatus.DELIVERED
            assert [m.id for m in await inbox.get_inbox(owner.user_id)] == [message_id]
            assert (await channel.send(message)).unwrap().message_id == message_id
            assert len(await inbox.get_inbox(owner.user_id)) == 1
            assert await inbox.get_inbox(other.user_id) == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "unknown",
        "inactive",
        "wrong-account",
        "wrong-destination",
        "missing-key",
        "missing-pin",
        "wrong-pin",
        "recreated-account",
        "conflicting-key",
    ],
)
async def test_binding_refuses_missing_spoofed_or_changed_recipient(tmp_path, failure):
    db = SQLiteProvider(str(tmp_path / "recipient.db"))
    await db.connect()
    try:
        users = SQLUserStore(db)
        owner = await users.create_user("editor", "editor@example.test", None)
        inbox = InboxService(DatabaseInboxStore(db))
        channel = InboxDeliveryChannel(
            inbox, users.get_user_by_email, recipient_email="editor@example.test"
        )
        message = DeliveryMessage(
            "inbox",
            "editor@example.test",
            "Published",
            "Title",
            {"effect_key": "publish:p1", "recipient_user_id": owner.user_id},
        )
        if failure == "unknown":
            channel = InboxDeliveryChannel(
                inbox, users.get_user_by_email, recipient_email="missing@example.test"
            )
            message = replace(message, recipient="missing@example.test")
        elif failure == "inactive":
            await users.update_user(owner.model_copy(update={"is_active": False}))
        elif failure == "wrong-account":
            wrong = await users.create_user("other", "other@example.test", None)
            users.get_user_by_email = AsyncMock(return_value=wrong)
            channel = InboxDeliveryChannel(
                inbox, users.get_user_by_email, recipient_email="editor@example.test"
            )
        elif failure == "wrong-destination":
            message = replace(message, recipient="other@example.test")
        elif failure == "missing-key":
            message = replace(message, metadata={})
        elif failure == "missing-pin":
            message = replace(message, metadata={"effect_key": "publish:p1"})
        elif failure == "wrong-pin":
            message = replace(
                message,
                metadata={
                    "effect_key": "publish:p1",
                    "recipient_user_id": "not-the-account",
                },
            )
        elif failure == "recreated-account":
            await users.delete_user(owner.user_id)
            replacement = await users.create_user("editor", "editor@example.test", None)
            assert replacement.user_id != owner.user_id
        else:
            assert (await channel.send(message)).is_ok()
            message = replace(message, body="changed intent")
        assert (await channel.send(message)).is_err()
        assert len(await inbox.get_inbox(owner.user_id)) == (
            1 if failure == "conflicting-key" else 0
        )
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_atomic_publication_enqueue_then_failed_inbox_recovers_after_restart(
    tmp_path,
):
    """Native shared-provider bridge, not a generated HTTP/effect admission."""
    path = str(tmp_path / "publication.db")
    db = SQLiteProvider(path)
    await db.connect()
    timer = MutableClock()
    try:
        users = SQLUserStore(db)
        owner = await users.create_user("editor", "editor@example.test", None)
        await db.execute_query(
            "CREATE TABLE posts (id TEXT PRIMARY KEY, status TEXT NOT NULL)"
        )
        await db.execute_insert("posts", {"id": "p1", "status": "draft"})
        inbox = InboxService(DatabaseInboxStore(db))
        await inbox.get_inbox(owner.user_id)
        await db.execute_query(
            "CREATE TRIGGER reject_inbox BEFORE INSERT ON notification_inbox_messages BEGIN SELECT RAISE(ABORT, 'inbox unavailable'); END"
        )
        queue = SqlDeliveryStore(db)
        channel = InboxDeliveryChannel(
            inbox, users.get_user_by_email, recipient_email="editor@example.test"
        )
        message = (
            await channel.prepare(
                "publish:p1",
                "Post published",
                "Post p1 was published",
                post_id="p1",
                status="published",
            )
        ).unwrap()
        with clock.use(timer):
            # The existing native SQL queue participates in the same provider UOW.
            async with db.transaction():
                await db.execute_update(
                    "posts", {"status": "published"}, "id = ?", ["p1"]
                )
                delivery_id = await queue.create_pending(message)
            dispatcher = NotificationDeliveryDispatcher(
                [
                    InboxDeliveryChannel(
                        inbox,
                        users.get_user_by_email,
                        recipient_email="editor@example.test",
                    )
                ]
            )
            assert await flush_retries(queue, dispatcher, base_delay=1) == 0
            assert (
                await db.execute_query("SELECT status FROM posts WHERE id = 'p1'")
            ).rows[0]["status"] == "published"
            assert (
                await queue.get_delivery(delivery_id)
            ).status == DeliveryStatus.RETRYING
            assert await inbox.get_inbox(owner.user_id) == []
            await db.execute_query("DROP TRIGGER reject_inbox")
            await db.disconnect()
            db = SQLiteProvider(path)
            await db.connect()
            users = SQLUserStore(db)
            inbox = InboxService(DatabaseInboxStore(db))
            queue = SqlDeliveryStore(db)
            dispatcher = NotificationDeliveryDispatcher(
                [
                    InboxDeliveryChannel(
                        inbox,
                        users.get_user_by_email,
                        recipient_email="editor@example.test",
                    )
                ]
            )
            timer.value += timedelta(seconds=2)
            assert await flush_retries(queue, dispatcher) == 1
            assert await flush_retries(queue, dispatcher) == 0
            stored = await inbox.get_inbox(owner.user_id)
            assert len(stored) == 1
            # A duplicate producer envelope is harmless at the inbox side too.
            await queue.create_pending(message)
            assert await flush_retries(queue, dispatcher) == 1
            assert [m.id for m in await inbox.get_inbox(owner.user_id)] == [
                stored[0].id
            ]

            # Rolling business work back also rolls its queued notification back.
            async def abort_publication():
                async with db.transaction():
                    await db.execute_update(
                        "posts", {"status": "draft"}, "id = ?", ["p1"]
                    )
                    await queue.create_pending(
                        replace(message, metadata={"effect_key": "must-not-exist"})
                    )
                    raise RuntimeError("abort publication")

            with pytest.raises(RuntimeError, match="abort publication"):
                await abort_publication()
            assert await queue.due_deliveries() == []
            assert (
                await db.execute_query("SELECT status FROM posts WHERE id = 'p1'")
            ).rows[0]["status"] == "published"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_prepare_resolves_real_account_and_rejects_routing_overrides(tmp_path):
    db = SQLiteProvider(str(tmp_path / "prepare.db"))
    await db.connect()
    try:
        users = SQLUserStore(db)
        owner = await users.create_user("editor", "editor@example.test", None)
        inbox = InboxService(DatabaseInboxStore(db))
        channel = InboxDeliveryChannel(
            inbox, users.get_user_by_email, recipient_email="editor@example.test"
        )
        data = {"post_id": "p1", "status": "published"}
        prepared = await channel.prepare(
            "publish:p1", "Post published", "Post p1", **data
        )
        assert prepared.is_ok()
        envelope = prepared.unwrap()
        assert envelope.recipient == owner.email
        assert envelope.metadata == {
            **data,
            "effect_key": "publish:p1",
            "recipient_user_id": owner.user_id,
        }
        assert await inbox.get_inbox(owner.user_id) == []  # preparation never sends
        assert (
            await channel.prepare(
                "publish:p1", "Title", "Body", recipient_user_id="spoofed"
            )
        ).is_err()
        assert (
            await channel.prepare("publish:p1", "Title", "Body", effect_key="spoofed")
        ).is_err()
        receipt = (await channel.send(envelope)).unwrap()
        assert (await channel.send(envelope)).unwrap() == receipt
        assert len(await inbox.get_inbox(owner.user_id)) == 1
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_binding_does_not_rewrite_the_account_lookup_identity(tmp_path):
    db = SQLiteProvider(str(tmp_path / "exact-identity.db"))
    await db.connect()
    try:
        users = SQLUserStore(db)
        owner = await users.create_user("editor", "straße@example.test", None)
        other = await users.create_user("other", "strasse@example.test", None)
        inbox = InboxService(DatabaseInboxStore(db))
        channel = InboxDeliveryChannel(
            inbox, users.get_user_by_email, recipient_email=owner.email
        )
        envelope = (await channel.prepare("publish:identity", "Title", "Body")).unwrap()
        assert envelope.recipient == owner.email
        assert envelope.metadata["recipient_user_id"] == owner.user_id
        assert (await channel.send(envelope)).is_ok()
        assert len(await inbox.get_inbox(owner.user_id)) == 1
        assert await inbox.get_inbox(other.user_id) == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_initial_queue_schema_rollback_does_not_poison_recovery(tmp_path):
    db = SQLiteProvider(str(tmp_path / "schema-rollback.db"))
    await db.connect()
    try:
        queue = SqlDeliveryStore(db, table="isolated_inbox_queue")
        message = DeliveryMessage("inbox", "editor@example.test", "Title", "Body")

        async def aborted_first_enqueue():
            async with db.transaction():
                await queue.create_pending(message)
                raise RuntimeError("rollback first queue schema")

        with pytest.raises(RuntimeError, match="rollback first queue schema"):
            await aborted_first_enqueue()
        # Same object must not assume rolled-back tables still exist.
        assert await queue.due_deliveries() == []
        await queue.initialize()
        delivery_id = await queue.create_pending(message)
        assert (await queue.get_delivery(delivery_id)).message == message
    finally:
        await db.disconnect()
