"""Tests for WhatsAppBackend (Twilio and Meta providers)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.notification.types import SMSMessage
from quadkit.notification.backends.sms.whatsapp import (
    WhatsAppBackend,
    WhatsAppMetaNotificationError,
    WhatsAppNotificationError,
)


def _make_aiohttp_session(status: int, json_body: dict) -> MagicMock:
    """Build a mock aiohttp.ClientSession context manager for POST."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_body)

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
    return mock_session


def _make_aiohttp_get_session(status: int) -> MagicMock:
    """Build a mock aiohttp.ClientSession context manager for GET."""
    mock_resp = MagicMock()
    mock_resp.status = status

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
    return mock_session


def _make_httpx_client(status_code: int, json_body: dict) -> MagicMock:
    """Build a mock httpx.AsyncClient context manager."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json = MagicMock(return_value=json_body)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestWhatsAppBackendInit:
    def test_default_provider_is_twilio(self) -> None:
        backend = WhatsAppBackend(account_sid="AC123", auth_token="tok")
        assert backend._provider == "twilio"

    def test_meta_provider_accepted(self) -> None:
        backend = WhatsAppBackend(
            provider="meta", access_token="abc", phone_number_id="123"
        )
        assert backend._provider == "meta"

    def test_invalid_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            WhatsAppBackend(provider="telegram")


class TestWhatsAppTwilioSend:
    @pytest.fixture
    def backend(self) -> WhatsAppBackend:
        return WhatsAppBackend(
            provider="twilio",
            account_sid="ACtest",
            auth_token="secret",
            from_number="+15550000000",
        )

    @pytest.fixture
    def message(self) -> SMSMessage:
        return SMSMessage(to=["+15551234567"], body="Hello via WhatsApp!")

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_201(
        self, backend: WhatsAppBackend, message: SMSMessage
    ) -> None:
        """Twilio 201 → Ok(MessageDeliveryReceipt) with whatsapp_twilio backend."""
        mock_session = _make_aiohttp_session(201, {"sid": "SMabc123", "status": "queued"})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.send(message)

        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.backend == "whatsapp_twilio"
        assert receipt.channel == "whatsapp"
        assert receipt.provider_reference == "SMabc123"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_400(
        self, backend: WhatsAppBackend, message: SMSMessage
    ) -> None:
        """Twilio 4xx → Err(WhatsAppNotificationError)."""
        mock_session = _make_aiohttp_session(
            400, {"message": "Invalid To", "code": 21211}
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.send(message)

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, WhatsAppNotificationError)
        assert err.twilio_code == 21211

    @pytest.mark.asyncio
    async def test_send_returns_err_on_500(
        self, backend: WhatsAppBackend, message: SMSMessage
    ) -> None:
        """Twilio 5xx → Err(WhatsAppNotificationError)."""
        mock_session = _make_aiohttp_session(
            500, {"message": "Internal Server Error", "code": 20001}
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.send(message)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), WhatsAppNotificationError)

    @pytest.mark.asyncio
    async def test_whatsapp_prefix_added_to_to_number(
        self, backend: WhatsAppBackend
    ) -> None:
        """send() adds whatsapp: prefix to recipient number."""
        message = SMSMessage(to=["+15559999999"], body="Prefix test")
        mock_session = _make_aiohttp_session(201, {"sid": "SMpfx", "status": "queued"})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.send(message)

        assert result.is_ok()
        inner = mock_session.__aenter__.return_value
        call_kwargs = inner.post.call_args[1]
        assert call_kwargs["data"]["To"] == "whatsapp:+15559999999"

    @pytest.mark.asyncio
    async def test_existing_whatsapp_prefix_not_duplicated(
        self, backend: WhatsAppBackend
    ) -> None:
        """send() doesn't double-prefix a number already starting with whatsapp:."""
        message = SMSMessage(to=["whatsapp:+15551111111"], body="No double prefix")
        mock_session = _make_aiohttp_session(201, {"sid": "SMnodbl", "status": "queued"})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.send(message)

        assert result.is_ok()
        inner = mock_session.__aenter__.return_value
        call_kwargs = inner.post.call_args[1]
        assert call_kwargs["data"]["To"] == "whatsapp:+15551111111"


class TestWhatsAppTwilioHealthCheck:
    @pytest.fixture
    def backend(self) -> WhatsAppBackend:
        return WhatsAppBackend(
            provider="twilio",
            account_sid="ACtest",
            auth_token="secret",
        )

    @pytest.mark.asyncio
    async def test_health_check_healthy_on_200(self, backend: WhatsAppBackend) -> None:
        """Account API < 500 → HEALTHY."""
        mock_session = _make_aiohttp_get_session(200)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.component == "whatsapp_twilio"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_500(self, backend: WhatsAppBackend) -> None:
        """Account API >= 500 → UNHEALTHY."""
        mock_session = _make_aiohttp_get_session(500)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.component == "whatsapp_twilio"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_oserror(
        self, backend: WhatsAppBackend
    ) -> None:
        """OSError → UNHEALTHY."""
        mock_session = MagicMock(
            __aenter__=AsyncMock(side_effect=OSError("Connection refused"))
        )
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.component == "whatsapp_twilio"


class TestWhatsAppMetaSend:
    @pytest.fixture
    def backend(self) -> WhatsAppBackend:
        return WhatsAppBackend(
            provider="meta",
            access_token="meta-access-token",
            phone_number_id="12345678",
        )

    @pytest.fixture
    def message(self) -> SMSMessage:
        return SMSMessage(to=["+15551234567"], body="Hello via Meta!")

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_200(
        self, backend: WhatsAppBackend, message: SMSMessage
    ) -> None:
        """Meta 200 → Ok(MessageDeliveryReceipt) with whatsapp_meta backend."""
        mock_client = _make_httpx_client(
            200,
            {"messages": [{"id": "wamid.abc123"}], "messaging_product": "whatsapp"},
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send(message)

        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.backend == "whatsapp_meta"
        assert receipt.channel == "whatsapp"
        assert receipt.provider_reference == "wamid.abc123"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_400(
        self, backend: WhatsAppBackend, message: SMSMessage
    ) -> None:
        """Meta 4xx → Err(WhatsAppMetaNotificationError)."""
        mock_client = _make_httpx_client(
            400,
            {"error": {"message": "Invalid parameter", "code": 100}},
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send(message)

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, WhatsAppMetaNotificationError)
        assert err.meta_code == "100"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_500(
        self, backend: WhatsAppBackend, message: SMSMessage
    ) -> None:
        """Meta 5xx → Err(WhatsAppMetaNotificationError)."""
        mock_client = _make_httpx_client(
            500,
            {"error": {"message": "Internal error", "code": 1}},
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send(message)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), WhatsAppMetaNotificationError)

    @pytest.mark.asyncio
    async def test_send_empty_messages_array(
        self, backend: WhatsAppBackend, message: SMSMessage
    ) -> None:
        """Meta 200 with empty messages array → Ok with no provider_reference."""
        mock_client = _make_httpx_client(
            200, {"messages": [], "messaging_product": "whatsapp"}
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send(message)

        assert result.is_ok()
        assert result.unwrap().provider_reference is None


class TestWhatsAppMetaHealthCheck:
    @pytest.fixture
    def backend(self) -> WhatsAppBackend:
        return WhatsAppBackend(
            provider="meta",
            access_token="meta-token",
            phone_number_id="12345678",
        )

    @pytest.mark.asyncio
    async def test_health_check_healthy_on_200(self, backend: WhatsAppBackend) -> None:
        """debug_token < 500 → HEALTHY."""
        mock_client = _make_httpx_client(200, {"data": {"is_valid": True}})
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.component == "whatsapp_meta"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_500(self, backend: WhatsAppBackend) -> None:
        """debug_token >= 500 → UNHEALTHY."""
        mock_client = _make_httpx_client(500, {})
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.component == "whatsapp_meta"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_oserror(
        self, backend: WhatsAppBackend
    ) -> None:
        """OSError → UNHEALTHY."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(side_effect=OSError("Timeout"))
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.component == "whatsapp_meta"


__all__ = [
    "TestWhatsAppBackendInit",
    "TestWhatsAppMetaHealthCheck",
    "TestWhatsAppMetaSend",
    "TestWhatsAppTwilioHealthCheck",
    "TestWhatsAppTwilioSend",
]
