"""Tests for SendGridMailer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.mailer import EmailMessage
from quadkit.notification.mailer.sendgrid_mailer import SendGridMailer
from quadkit.notification.exceptions import SendGridMailerError


class TestSendGridMailer:
    @pytest.fixture
    def mailer(self) -> SendGridMailer:
        return SendGridMailer(api_key="SG.test_key", from_email="noreply@example.com")

    @pytest.fixture
    def message(self) -> EmailMessage:
        return EmailMessage(
            to=["recipient@example.com"],
            subject="Hello",
            body="Plain text",
            html_body="<p>HTML</p>",
        )

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_202(
        self, mailer: SendGridMailer, message: EmailMessage
    ) -> None:
        mock_response = MagicMock()
        mock_response.status = 202
        mock_response.headers = {"X-Message-Id": "sg_msg_123"}

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await mailer.send(message)

        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.backend == "sendgrid"
        assert receipt.channel == "email"
        assert receipt.provider_reference == "sg_msg_123"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_429(
        self, mailer: SendGridMailer, message: EmailMessage
    ) -> None:
        mock_response = MagicMock()
        mock_response.status = 429
        mock_response.json = AsyncMock(
            return_value={"errors": [{"message": "rate limited"}]}
        )

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await mailer.send(message)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), SendGridMailerError)

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, mailer: SendGridMailer) -> None:
        mock_response = MagicMock()
        mock_response.status = 200

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.head = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await mailer.health_check()

        assert result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
