"""Tests for FCMPush."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from quadkit.contracts.core import HealthStatus
from quadkit.notification.backends.push.fcm import FCMPush
from quadkit.notification.exceptions import FCMNotificationError
from quadkit.contracts.notification.types import PushMessage


class TestFCMPush:
    @pytest.fixture
    def backend(self) -> FCMPush:
        return FCMPush(server_key="test-server-key")

    @pytest.fixture
    def push_message(self) -> PushMessage:
        return PushMessage(
            to=["device-token-abc"],
            title="Test",
            body="Hello from FCM",
        )

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_200_success(
        self, backend: FCMPush, push_message: PushMessage
    ) -> None:
        """Test successful push send returns Ok with MessageDeliveryReceipt."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "results": [{"message_id": "fcm:abc123"}],
                "success": 1,
                "failure": 0,
            }
        )
        mock_cm = MagicMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        mock_session = MagicMock(
            __aenter__=AsyncMock(
                return_value=MagicMock(post=MagicMock(return_value=mock_cm))
            ),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.send(push_message)

        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.backend == "fcm"
        assert receipt.channel == "push"
        assert receipt.provider_reference == "fcm:abc123"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_fcm_failure(
        self, backend: FCMPush, push_message: PushMessage
    ) -> None:
        """Test FCM returns error in results → Err(FCMNotificationError)."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "results": [{"error": "InvalidRegistration"}],
                "success": 0,
                "failure": 1,
            }
        )
        mock_cm = MagicMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        mock_session = MagicMock(
            __aenter__=AsyncMock(
                return_value=MagicMock(post=MagicMock(return_value=mock_cm))
            ),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.send(push_message)

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, FCMNotificationError)
        assert err.fcm_error == "InvalidRegistration"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_http_error(
        self, backend: FCMPush, push_message: PushMessage
    ) -> None:
        """Test non-200 HTTP status returns Err(FCMNotificationError)."""
        mock_resp = MagicMock()
        mock_resp.status = 401
        mock_resp.json = AsyncMock(return_value={"error": "InvalidApiKey"})
        mock_cm = MagicMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        mock_session = MagicMock(
            __aenter__=AsyncMock(
                return_value=MagicMock(post=MagicMock(return_value=mock_cm))
            ),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.send(push_message)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), FCMNotificationError)

    @pytest.mark.asyncio
    async def test_send_batch_returns_list(self, backend: FCMPush) -> None:
        """Test send_batch sends multiple messages and returns list of Results."""
        messages = [
            PushMessage(to=["t1"], title="A", body="B"),
            PushMessage(to=["t2"], title="C", body="D"),
        ]
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "results": [{"message_id": "fcm:1"}],
                "success": 1,
                "failure": 0,
            }
        )
        mock_cm = MagicMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        mock_session = MagicMock(
            __aenter__=AsyncMock(
                return_value=MagicMock(post=MagicMock(return_value=mock_cm))
            ),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            results = await backend.send_batch(messages)

        assert len(results) == 2
        assert all(r.is_ok() for r in results)

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, backend: FCMPush) -> None:
        """Test health_check returns HEALTHY on HEAD success."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_cm = MagicMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        mock_session = MagicMock(
            __aenter__=AsyncMock(
                return_value=MagicMock(head=MagicMock(return_value=mock_cm))
            ),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.component == "fcm"

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_500(self, backend: FCMPush) -> None:
        """Test health_check returns UNHEALTHY on 5xx."""
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_cm = MagicMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        mock_session = MagicMock(
            __aenter__=AsyncMock(
                return_value=MagicMock(head=MagicMock(return_value=mock_cm))
            ),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_oserror(
        self, backend: FCMPush
    ) -> None:
        """Test health_check returns UNHEALTHY on OSError."""
        mock_session = MagicMock(
            __aenter__=AsyncMock(side_effect=OSError("Connection refused"))
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY


__all__ = ["TestFCMPush"]
