"""Tests for DeferredRetryMailer — one durable attempt, then worker backoff."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.mailer import EmailMessage
from quadkit.result import Err, Ok


class TestDeferredRetryMailer:
    @pytest.fixture
    def mock_backend(self) -> MagicMock:
        backend = MagicMock()
        backend.send = AsyncMock()
        return backend

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        store = MagicMock()
        store.create_pending = AsyncMock(return_value="delivery-id-1")
        store.claim_delivery = AsyncMock(return_value=True)
        store.record_attempt = AsyncMock()
        store.complete_attempt = AsyncMock()
        store.mark_delivered = AsyncMock()
        store.mark_failed = AsyncMock()
        store.schedule_retry = AsyncMock()
        return store

    @staticmethod
    def _message() -> EmailMessage:
        return EmailMessage(
            to=["ada@example.com"],
            subject="Reset",
            body="Click here",
        )

    @pytest.mark.asyncio
    async def test_successful_delivery_records_and_marks_attempt(
        self, mock_backend: MagicMock, mock_store: MagicMock
    ) -> None:
        from quadkit.notification.delivery.retry import DeferredRetryMailer

        mock_backend.send.return_value = Ok(MagicMock())
        mailer = DeferredRetryMailer(backend=mock_backend, store=mock_store)
        result = await mailer.send(self._message())

        assert result.is_ok()
        assert result.unwrap() == "delivery-id-1"
        mock_store.claim_delivery.assert_awaited_once_with("delivery-id-1")
        mock_store.record_attempt.assert_awaited_once_with(
            "delivery-id-1", "ada@example.com", "Reset", 1
        )
        mock_store.complete_attempt.assert_awaited_once_with(
            "delivery-id-1", 1, outcome="delivered"
        )
        mock_store.mark_delivered.assert_awaited_once_with("delivery-id-1")
        mock_store.schedule_retry.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_transient_failure_schedules_the_first_backoff(
        self, mock_backend: MagicMock, mock_store: MagicMock
    ) -> None:
        from quadkit.notification.delivery.retry import DeferredRetryMailer

        mock_backend.send.return_value = Err(RuntimeError("Connection reset"))
        mailer = DeferredRetryMailer(
            backend=mock_backend,
            store=mock_store,
            max_retries=3,
            base_delay=60.0,
        )
        result = await mailer.send(self._message())

        assert result.is_ok()
        assert result.unwrap() == "delivery-id-1"
        mock_store.complete_attempt.assert_awaited_once_with(
            "delivery-id-1", 1, outcome="failed", error="Connection reset"
        )
        mock_store.schedule_retry.assert_awaited_once_with("delivery-id-1", 60.0)
        mock_store.mark_delivered.assert_not_awaited()
        mock_store.mark_failed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_single_allowed_attempt_is_terminal(
        self, mock_backend: MagicMock, mock_store: MagicMock
    ) -> None:
        from quadkit.notification.delivery.exceptions import PermanentDeliveryFailure
        from quadkit.notification.delivery.retry import DeferredRetryMailer

        mock_backend.send.return_value = Err(RuntimeError("permanent"))
        mailer = DeferredRetryMailer(
            backend=mock_backend,
            store=mock_store,
            max_retries=1,
            base_delay=60.0,
        )
        result = await mailer.send(self._message())

        assert result.is_err()
        assert isinstance(result.unwrap_err(), PermanentDeliveryFailure)
        assert result.unwrap_err().delivery_id == "delivery-id-1"
        mock_store.mark_failed.assert_awaited_once_with(
            "delivery-id-1", reason="permanent"
        )
        mock_store.schedule_retry.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_transport_exception_is_persisted_and_scheduled(
        self, mock_backend: MagicMock, mock_store: MagicMock
    ) -> None:
        from quadkit.notification.delivery.retry import DeferredRetryMailer

        mock_backend.send.side_effect = OSError("socket closed")
        mailer = DeferredRetryMailer(backend=mock_backend, store=mock_store)
        result = await mailer.send(self._message())

        assert result.is_ok()
        mock_store.complete_attempt.assert_awaited_once_with(
            "delivery-id-1", 1, outcome="failed", error="OSError: socket closed"
        )
        mock_store.schedule_retry.assert_awaited_once_with("delivery-id-1", 60.0)
