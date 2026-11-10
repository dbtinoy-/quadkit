"""Tests for RetryingMailer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.mailer.types import EmailMessage, MessageDeliveryReceipt
from quadkit.result import Err, Ok


def _make_receipt() -> MessageDeliveryReceipt:
    return MessageDeliveryReceipt(
        message_id="msg-001",
        backend="smtp",
        channel="email",
    )


def _make_message() -> EmailMessage:
    return EmailMessage(
        to=["a@b.com"],
        subject="Hi",
        body="Hello",
    )


class TestRetryingMailer:
    @pytest.fixture
    def mock_inner_mailer(self) -> MagicMock:
        mailer = MagicMock()
        mailer.send = AsyncMock(return_value=Ok(_make_receipt()))
        return mailer

    @pytest.fixture
    def mock_delivery_store(self) -> MagicMock:
        store = MagicMock()
        store.create_pending = AsyncMock(return_value="delivery-123")
        store.claim_delivery = AsyncMock(return_value=True)
        store.record_attempt = AsyncMock()
        store.complete_attempt = AsyncMock()
        store.mark_delivered = AsyncMock()
        store.mark_failed = AsyncMock()
        return store

    @pytest.mark.asyncio
    async def test_successful_send_marks_delivered(
        self,
        mock_inner_mailer: MagicMock,
        mock_delivery_store: MagicMock,
    ) -> None:
        from quadkit.notification.mailer.retrying_mailer import RetryingMailer

        mailer = RetryingMailer(
            inner=mock_inner_mailer,
            delivery_store=mock_delivery_store,
            max_attempts=3,
        )
        result = await mailer.send(_make_message())

        mock_inner_mailer.send.assert_awaited_once()
        mock_delivery_store.mark_delivered.assert_awaited_once()
        assert result.is_ok()

        # The delivery row is created up front — later mark_delivered /
        # mark_failed / record_attempt calls have a row to update.
        mock_delivery_store.create_pending.assert_awaited_once()
        mock_delivery_store.mark_delivered.assert_awaited_once_with("delivery-123")
        first_call = mock_delivery_store.record_attempt.await_args_list[0]
        assert first_call.kwargs["delivery_id"] == "delivery-123"

    @pytest.mark.asyncio
    async def test_failed_send_retries_up_to_max(
        self,
        mock_inner_mailer: MagicMock,
        mock_delivery_store: MagicMock,
    ) -> None:
        from quadkit.notification.mailer.retrying_mailer import RetryingMailer

        mock_inner_mailer.send = AsyncMock(side_effect=Exception("SMTP error"))
        mailer = RetryingMailer(
            inner=mock_inner_mailer,
            delivery_store=mock_delivery_store,
            max_attempts=3,
            base_delay=0.0,  # no delay in tests
        )
        result = await mailer.send(_make_message())

        assert mock_inner_mailer.send.await_count == 3
        mock_delivery_store.mark_failed.assert_awaited_once()
        assert result.is_err()

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(
        self,
        mock_inner_mailer: MagicMock,
        mock_delivery_store: MagicMock,
    ) -> None:
        from quadkit.notification.mailer.retrying_mailer import RetryingMailer

        receipt = _make_receipt()
        mock_inner_mailer.send = AsyncMock(
            side_effect=[Exception("timeout"), Ok(receipt)]
        )
        mailer = RetryingMailer(
            inner=mock_inner_mailer,
            delivery_store=mock_delivery_store,
            max_attempts=3,
            base_delay=0.0,
        )
        result = await mailer.send(_make_message())

        assert mock_inner_mailer.send.await_count == 2
        mock_delivery_store.mark_delivered.assert_awaited_once()
        assert result.is_ok()
        assert result.unwrap() is receipt

    @pytest.mark.asyncio
    async def test_inner_err_result_is_not_retried(
        self,
        mock_inner_mailer: MagicMock,
        mock_delivery_store: MagicMock,
    ) -> None:
        """An Err(MailerError) from the inner mailer is a terminal failure — no retry."""
        from quadkit.contracts.mailer.errors import MailerError
        from quadkit.notification.mailer.retrying_mailer import RetryingMailer

        terminal_err = MailerError("Bounced", backend="smtp")
        mock_inner_mailer.send = AsyncMock(return_value=Err(terminal_err))
        mailer = RetryingMailer(
            inner=mock_inner_mailer,
            delivery_store=mock_delivery_store,
            max_attempts=3,
            base_delay=0.0,
        )
        result = await mailer.send(_make_message())

        # Inner called exactly once — no retry for expected delivery failures.
        mock_inner_mailer.send.assert_awaited_once()
        mock_delivery_store.mark_failed.assert_awaited_once()
        assert result.is_err()
        assert isinstance(result.unwrap_err(), MailerError)

    @pytest.mark.asyncio
    async def test_record_attempt_called_for_each_retry(
        self,
        mock_inner_mailer: MagicMock,
        mock_delivery_store: MagicMock,
    ) -> None:
        from quadkit.notification.mailer.retrying_mailer import RetryingMailer

        mock_inner_mailer.send = AsyncMock(side_effect=Exception("timeout"))
        mailer = RetryingMailer(
            inner=mock_inner_mailer,
            delivery_store=mock_delivery_store,
            max_attempts=3,
            base_delay=0.0,
        )
        await mailer.send(_make_message())

        assert mock_delivery_store.record_attempt.await_count == 3

    @pytest.mark.asyncio
    async def test_delivery_id_is_consistent_across_attempts(
        self,
        mock_inner_mailer: MagicMock,
        mock_delivery_store: MagicMock,
    ) -> None:
        from quadkit.notification.mailer.retrying_mailer import RetryingMailer

        mock_inner_mailer.send = AsyncMock(
            side_effect=[Exception("e1"), Exception("e2"), Ok(_make_receipt())]
        )
        mailer = RetryingMailer(
            inner=mock_inner_mailer,
            delivery_store=mock_delivery_store,
            max_attempts=3,
            base_delay=0.0,
        )
        await mailer.send(_make_message())

        call_args = mock_delivery_store.record_attempt.call_args_list
        delivery_ids = {c.kwargs["delivery_id"] for c in call_args}
        # All attempts share the same delivery_id.
        assert len(delivery_ids) == 1

    @pytest.mark.asyncio
    async def test_mark_delivered_not_called_on_failure(
        self,
        mock_inner_mailer: MagicMock,
        mock_delivery_store: MagicMock,
    ) -> None:
        from quadkit.notification.mailer.retrying_mailer import RetryingMailer

        mock_inner_mailer.send = AsyncMock(side_effect=Exception("SMTP error"))
        mailer = RetryingMailer(
            inner=mock_inner_mailer,
            delivery_store=mock_delivery_store,
            max_attempts=2,
            base_delay=0.0,
        )
        await mailer.send(_make_message())

        mock_delivery_store.mark_delivered.assert_not_awaited()
        mock_delivery_store.mark_failed.assert_awaited_once()
