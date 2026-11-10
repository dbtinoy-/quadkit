"""Tests for WebPushChannel."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import pytest
from pywebpush import WebPushException

from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.types import PushMessage
from quadkit.notification.backends.push.web_push import WebPushChannel
from quadkit.notification.exceptions import WebPushNotificationError
from quadkit.result import Err, Ok


@pytest.fixture
def channel() -> WebPushChannel:
    key = ec.generate_private_key(ec.SECP256R1())
    return WebPushChannel(
        vapid_private_key=key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        vapid_public_key=base64.urlsafe_b64encode(
            key.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        )
        .rstrip(b"=")
        .decode(),
        vapid_claims_subject="mailto:test@example.com",
    )


class TestWebPushChannel:
    @pytest.mark.asyncio
    async def test_send_requires_to(self, channel: WebPushChannel) -> None:
        """send() raises ValueError if to is empty."""
        msg = PushMessage(to=[], title="Test", body="Hello")
        with pytest.raises(ValueError, match="at least one endpoint"):
            await channel.send(msg)

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_success(self, channel: WebPushChannel) -> None:
        """send() returns Ok(MessageDeliveryReceipt) on success."""
        msg = PushMessage(
            to=["https://push.example.com/abc"],
            title="Test",
            body="Hello",
            data={"keys": {"p256dh": "x", "auth": "y"}},
        )

        with patch(
            "quadkit.notification.backends.push.web_push.webpush",
            return_value=MagicMock(status_code=201),
        ) as mock:
            result = await channel.send(msg)
            assert isinstance(result, Ok)
            assert isinstance(result.unwrap(), MessageDeliveryReceipt)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_returns_err_on_410(self, channel: WebPushChannel) -> None:
        """send() returns Err(WebPushNotificationError) on 410 Gone."""
        msg = PushMessage(
            to=["https://push.example.com/abc"],
            title="Test",
            body="Hello",
        )

        exc = WebPushException(
            "410 Gone", response=SimpleNamespace(status_code=410, text="gone")
        )
        with patch(
            "quadkit.notification.backends.push.web_push.webpush",
            side_effect=exc,
        ) as mock:
            result = await channel.send(msg)
            assert isinstance(result, Err)
            err = result.unwrap_err()
            assert isinstance(err, WebPushNotificationError)
            assert err.status_code == 410
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_returns_err_on_404(self, channel: WebPushChannel) -> None:
        """send() returns Err(WebPushNotificationError) on 404 Not Found."""
        msg = PushMessage(
            to=["https://push.example.com/abc"],
            title="Test",
            body="Hello",
        )

        exc = WebPushException(
            "404 Not Found", response=SimpleNamespace(status_code=404, text="not_found")
        )
        with patch(
            "quadkit.notification.backends.push.web_push.webpush",
            side_effect=exc,
        ) as mock:
            result = await channel.send(msg)
            assert isinstance(result, Err)
            err = result.unwrap_err()
            assert err.status_code == 404
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_returns_result(self, channel: WebPushChannel) -> None:
        """health_check() returns HealthCheckResult across fixture, PEM, and empty keys."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        from quadkit.contracts.core import HealthCheckResult, HealthStatus

        result = await channel.health_check()
        assert isinstance(result, HealthCheckResult)
        assert result.status in (HealthStatus.HEALTHY, HealthStatus.UNHEALTHY)

        pem = (
            ec.generate_private_key(ec.SECP256R1())
            .private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
            .decode()
        )
        valid_channel = WebPushChannel(
            vapid_private_key=pem,
            vapid_public_key="x",
            vapid_claims_subject="mailto:test@example.com",
        )
        assert (await valid_channel.health_check()).status == HealthStatus.HEALTHY

        empty_channel = WebPushChannel(
            vapid_private_key="",
            vapid_public_key="",
            vapid_claims_subject="mailto:test@example.com",
        )
        assert (await empty_channel.health_check()).status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_send_batch_preserves_order(self, channel: WebPushChannel) -> None:
        """send_batch returns results in same order as messages."""
        messages = [
            PushMessage(to=[f"https://push.example.com/{i}"], title="T", body="B")
            for i in range(3)
        ]
        with patch(
            "quadkit.notification.backends.push.web_push.webpush",
            return_value=MagicMock(status_code=201),
        ):
            results = await channel.send_batch(messages)
            assert len(results) == 3
            for r in results:
                assert isinstance(r, Ok)
