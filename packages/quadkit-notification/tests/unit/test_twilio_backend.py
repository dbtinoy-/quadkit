"""Tests for TwilioSMS."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from quadkit.contracts.core import HealthStatus
from quadkit.notification.backends.sms.twilio import TwilioSMS
from quadkit.notification.exceptions import TwilioNotificationError
from quadkit.contracts.notification.types import SMSMessage


class TestTwilioSMS:
    @pytest.fixture
    def backend(self) -> TwilioSMS:
        return TwilioSMS(
            account_sid="ACtest",
            auth_token="secret",
            from_number="+15550000000",
        )

    @pytest.fixture
    def sms_message(self) -> SMSMessage:
        return SMSMessage(to=["+15551234567"], body="Hello!")

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_201(self, backend: TwilioSMS, sms_message: SMSMessage) -> None:
        """Test successful SMS send returns Ok with MessageDeliveryReceipt."""
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_resp.json = AsyncMock(return_value={"sid": "SM123", "status": "queued"})
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
            result = await backend.send(sms_message)

        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.backend == "twilio"
        assert receipt.channel == "sms"
        assert receipt.provider_reference == "SM123"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_400(self, backend: TwilioSMS, sms_message: SMSMessage) -> None:
        """Test 4xx error returns Err(TwilioNotificationError)."""
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_resp.json = AsyncMock(
            return_value={"message": "Invalid to", "code": 21211}
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
            result = await backend.send(sms_message)

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, TwilioNotificationError)
        assert err.twilio_code == 21211

    @pytest.mark.asyncio
    async def test_send_returns_err_on_500(self, backend: TwilioSMS, sms_message: SMSMessage) -> None:
        """Test 5xx error returns Err(TwilioNotificationError)."""
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.json = AsyncMock(
            return_value={"message": "Internal Server Error", "code": 20001}
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
            result = await backend.send(sms_message)

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, TwilioNotificationError)

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, backend: TwilioSMS) -> None:
        """Test health_check returns HEALTHY on 200."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_cm = MagicMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        mock_session = MagicMock(
            __aenter__=AsyncMock(
                return_value=MagicMock(get=MagicMock(return_value=mock_cm))
            ),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.component == "twilio"

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_500(self, backend: TwilioSMS) -> None:
        """Test health_check returns UNHEALTHY on 5xx."""
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_cm = MagicMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        )
        mock_session = MagicMock(
            __aenter__=AsyncMock(
                return_value=MagicMock(get=MagicMock(return_value=mock_cm))
            ),
            __aexit__=AsyncMock(return_value=False),
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_oserror(self, backend: TwilioSMS) -> None:
        """Test health_check returns UNHEALTHY on OSError."""
        mock_session = MagicMock(
            __aenter__=AsyncMock(side_effect=OSError("Connection refused"))
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY


__all__ = ["TestTwilioSMS"]
