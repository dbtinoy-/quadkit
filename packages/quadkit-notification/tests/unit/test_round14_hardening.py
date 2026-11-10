"""Round-14 hardening pins for quadkit-notification.

Covers:
- placeholder dialect translation in the SQL stores (Postgres/MySQL/SQLite)
- the delivery attempts table being created before first record_attempt
- non-JSON API response bodies -> Err (not a raised exception)
- health checks never raising (any transport error -> UNHEALTHY)
- flush_retries isolating a raising backend from the rest of the batch
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.notification.types import SMSMessage
from quadkit.result import Ok

# ────────────────────────────────────────────────────────────
# Dialect translation
# ────────────────────────────────────────────────────────────


def _mock_db(name: str | None = None) -> MagicMock:
    from quadkit.contracts.data.sql.database import (
        DeleteResult,
        InsertResult,
        QueryResult,
        UpdateResult,
    )

    db = MagicMock()
    if name is not None:
        db.name = name
    db.execute = AsyncMock(return_value=None)
    db.execute_query = AsyncMock(
        return_value=QueryResult(
            rows=[], row_count=0, execution_time=0.001, success=True
        )
    )
    db.execute_insert = AsyncMock(
        return_value=InsertResult(
            inserted_id="1", affected_rows=1, execution_time=0.001, success=True
        )
    )
    db.execute_update = AsyncMock(
        return_value=UpdateResult(affected_rows=1, execution_time=0.001, success=True)
    )
    db.execute_delete = AsyncMock(
        return_value=DeleteResult(affected_rows=1, execution_time=0.001, success=True)
    )
    return db


class TestInboxStoreDialect:
    """DatabaseInboxStore must translate placeholders per provider."""

    @pytest.mark.asyncio
    async def test_postgres_get_uses_positional(self) -> None:
        from quadkit.notification.inbox.database import DatabaseInboxStore

        db = _mock_db("postgres")
        store = DatabaseInboxStore(db)
        await store.get("m-1")
        sql = db.execute_query.await_args.args[0]
        assert "$1" in sql
        assert "?" not in sql

    @pytest.mark.asyncio
    async def test_postgres_mark_read_translates_two_placeholders(self) -> None:
        from quadkit.notification.inbox.database import DatabaseInboxStore

        db = _mock_db("postgres")
        store = DatabaseInboxStore(db)
        await store.mark_read("m-1", "u-1")
        sql = db.execute_update.await_args.args[2]
        assert "$1" in sql
        assert "$2" in sql
        assert "?" not in sql

    @pytest.mark.asyncio
    async def test_mysql_uses_percent_style(self) -> None:
        from quadkit.notification.inbox.database import DatabaseInboxStore

        db = _mock_db("mysql")
        store = DatabaseInboxStore(db)
        await store.count_unread("u-1")
        sql = db.execute_query.await_args.args[0]
        assert "%s" in sql
        assert "?" not in sql

    @pytest.mark.asyncio
    async def test_sqlite_passes_through(self) -> None:
        from quadkit.notification.inbox.database import DatabaseInboxStore

        db = _mock_db("sqlite")
        store = DatabaseInboxStore(db)
        await store.get("m-1")
        sql = db.execute_query.await_args.args[0]
        assert "?" in sql
        assert "$" not in sql


class TestDeliveryStoreDialect:
    """SqlDeliveryStore must translate placeholders per provider."""

    @pytest.mark.asyncio
    async def test_postgres_get_delivery_translates_identifier_placeholder(self) -> None:
        from quadkit.notification.delivery.stores import SqlDeliveryStore

        db = _mock_db("postgres")
        store = SqlDeliveryStore(db)
        await store.get_delivery("d-1")
        queries = [call.args[0] for call in db.execute_query.await_args_list]
        select = next(q for q in queries if "WHERE delivery_id" in q)
        assert "$1" in select
        assert "?" not in select

    @pytest.mark.asyncio
    async def test_postgres_mark_failed_where_translated(self) -> None:
        from quadkit.notification.delivery.stores import SqlDeliveryStore

        db = _mock_db("postgres")
        store = SqlDeliveryStore(db)
        await store.mark_failed("d-1", reason="boom")
        sql = db.execute_update.await_args.args[2]
        assert "$1" in sql
        assert "?" not in sql


# ────────────────────────────────────────────────────────────
# Attempts table DDL
# ────────────────────────────────────────────────────────────


class TestDeliveryAttemptsTable:
    @pytest.mark.asyncio
    async def test_record_attempt_uses_provisioned_attempts_table(self) -> None:
        """Fresh outbox provisioning creates the attempt-history table."""
        from quadkit.contracts.notification.types import DeliveryMessage
        from quadkit.notification.delivery.stores import SqlDeliveryStore
        from quadkit.sql.providers.sqlite_provider import SQLiteProvider

        provider = SQLiteProvider(database_path=":memory:")
        await provider.connect()
        try:
            store = SqlDeliveryStore(provider)
            delivery_id = await store.create_pending(
                DeliveryMessage(
                    channel="email",
                    recipient="a@b.com",
                    subject="Subj",
                    body="Body",
                )
            )
            await store.record_attempt(delivery_id, "a@b.com", "Subj", 1)
            rows = await provider.execute_query(
                "SELECT attempt_number FROM notification_delivery_state_attempts "
                "WHERE delivery_id = ?",
                [delivery_id],
            )
            assert rows.rows[0]["attempt_number"] == 1
        finally:
            await provider.connection_manager.disconnect()


# ────────────────────────────────────────────────────────────
# Non-JSON response bodies
# ────────────────────────────────────────────────────────────


def _mock_aiohttp_session(resp: MagicMock) -> MagicMock:
    cm = MagicMock(
        __aenter__=AsyncMock(return_value=resp),
        __aexit__=AsyncMock(return_value=False),
    )
    return MagicMock(
        __aenter__=AsyncMock(
            return_value=MagicMock(post=MagicMock(return_value=cm))
        ),
        __aexit__=AsyncMock(return_value=False),
    )


class TestNonJsonResponses:
    @pytest.mark.asyncio
    async def test_twilio_non_json_body_is_err_not_raise(self) -> None:
        """A proxy HTML page / truncated body must yield Err, not raise."""
        from quadkit.notification.backends.sms.twilio import TwilioSMS
        from quadkit.notification.exceptions import TwilioNotificationError

        backend = TwilioSMS(
            account_sid="ACtest", auth_token="secret", from_number="+15550000000"
        )
        resp = MagicMock()
        resp.status = 502
        resp.json = AsyncMock(side_effect=ValueError("bad content-type"))
        message = SMSMessage(to=["+15551234567"], body="hi")

        with patch("aiohttp.ClientSession", return_value=_mock_aiohttp_session(resp)):
            result = await backend.send(message)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), TwilioNotificationError)
        assert "Non-JSON" in str(result.unwrap_err())

    @pytest.mark.asyncio
    async def test_fcm_non_json_body_is_err_not_raise(self) -> None:
        from quadkit.contracts.notification.types import PushMessage
        from quadkit.notification.backends.push.fcm import FCMPush
        from quadkit.notification.exceptions import FCMNotificationError

        backend = FCMPush(server_key="key")
        resp = MagicMock()
        resp.status = 502
        resp.json = AsyncMock(side_effect=KeyError("nope"))
        message = PushMessage(to=["token-1"], title="T", body="B")

        with patch("aiohttp.ClientSession", return_value=_mock_aiohttp_session(resp)):
            result = await backend.send(message)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), FCMNotificationError)
        assert "Non-JSON" in str(result.unwrap_err())

    @pytest.mark.asyncio
    async def test_whatsapp_twilio_non_json_body_is_err(self) -> None:
        from quadkit.notification.backends.sms.whatsapp import (
            WhatsAppBackend,
            WhatsAppNotificationError,
        )

        backend = WhatsAppBackend(
            provider="twilio",
            account_sid="ACtest",
            auth_token="secret",
            from_number="whatsapp:+15550000000",
        )
        resp = MagicMock()
        resp.status = 502
        resp.json = AsyncMock(side_effect=ValueError("bad content-type"))
        message = SMSMessage(to=["+15551234567"], body="hi")

        with patch("aiohttp.ClientSession", return_value=_mock_aiohttp_session(resp)):
            result = await backend.send(message)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), WhatsAppNotificationError)


# ────────────────────────────────────────────────────────────
# Health checks must never raise
# ────────────────────────────────────────────────────────────


class TestHealthNeverRaises:
    @pytest.mark.asyncio
    async def test_twilio_health_survives_http_client_error(self) -> None:
        """aiohttp.ClientResponseError is NOT an OSError — health used to
        raise instead of returning UNHEALTHY."""
        from quadkit.notification.backends.sms.twilio import TwilioSMS

        backend = TwilioSMS(
            account_sid="ACtest", auth_token="secret", from_number="+15550000000"
        )

        class _ClientResponseError(Exception):
            pass

        session = MagicMock(
            __aenter__=AsyncMock(
                side_effect=_ClientResponseError("599 Internal")
            ),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("aiohttp.ClientSession", return_value=session):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_whatsapp_meta_health_survives_httpx_error(self) -> None:
        from quadkit.notification.backends.sms.whatsapp import WhatsAppBackend

        backend = WhatsAppBackend(provider="meta", access_token="tok")

        class _HttpxError(Exception):
            pass

        with patch("httpx.AsyncClient") as client_cls:
            client = MagicMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            client.get = AsyncMock(side_effect=_HttpxError("connect refused"))
            client_cls.return_value = client
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY


# ────────────────────────────────────────────────────────────
# Worker isolation
# ────────────────────────────────────────────────────────────


class _RaisingFirstDispatcher:
    """Raises on the first channel dispatch, delivers the rest."""

    def __init__(self) -> None:
        self.calls = 0

    async def send(self, _message: object):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("smtp socket blown up")
        return Ok("receipt")


@pytest.mark.asyncio
async def test_flush_isolates_raising_delivery_from_batch() -> None:
    """One channel exception must not abort the remaining due deliveries."""
    from quadkit.contracts.notification.types import DeliveryMessage
    from quadkit.notification.delivery.stores import MemoryDeliveryStore
    from quadkit.notification.delivery.worker import flush_retries

    store = MemoryDeliveryStore()
    dispatcher = _RaisingFirstDispatcher()

    # Two due deliveries; the first dispatch raises.
    for i in range(2):
        await store.create_pending(
            DeliveryMessage(
                channel="email",
                recipient=f"u{i}@example.com",
                subject=f"s{i}",
                body="b",
            )
        )

    delivered = await flush_retries(store, dispatcher)

    # Both deliveries were processed; the healthy one was delivered.
    assert dispatcher.calls == 2
    assert delivered == 1
    statuses = sorted(entry["status"] for entry in store._state.values())
    assert "delivered" in statuses
    # The raising one was rescheduled (retrying), not lost.
    assert "retrying" in statuses
