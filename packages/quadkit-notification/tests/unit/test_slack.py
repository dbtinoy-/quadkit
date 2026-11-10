"""Tests for SlackNotifier (webhook and bot modes)."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.notification.backends.slack.slack_notifier import (
    SlackMessage,
    SlackNotificationError,
    SlackNotifier,
)


def _patch_slack_sdk(mock_client: MagicMock):
    """Return a patch.dict context that injects a fake slack_sdk into sys.modules."""
    mock_async_client_module = MagicMock()
    mock_async_client_module.AsyncWebClient = MagicMock(return_value=mock_client)

    mock_web = MagicMock()
    mock_web.async_client = mock_async_client_module

    mock_sdk = MagicMock()
    mock_sdk.web = mock_web
    mock_sdk.web.async_client = mock_async_client_module

    return patch.dict(
        sys.modules,
        {
            "slack_sdk": mock_sdk,
            "slack_sdk.web": mock_web,
            "slack_sdk.web.async_client": mock_async_client_module,
        },
    )


def _make_httpx_client(
    status_code: int, text: str = "", json_body: dict | None = None
) -> MagicMock:
    """Build a mock httpx.AsyncClient context manager."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = text
    if json_body is not None:
        mock_resp.json = MagicMock(return_value=json_body)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestSlackNotifierInit:
    def test_requires_webhook_or_token(self) -> None:
        with pytest.raises(ValueError, match="webhook_url"):
            SlackNotifier()

    def test_webhook_mode_set(self) -> None:
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        assert notifier._mode == "webhook"

    def test_bot_mode_set(self) -> None:
        notifier = SlackNotifier(bot_token="xoxb-test")
        assert notifier._mode == "bot"


class TestSlackWebhookSend:
    @pytest.fixture
    def backend(self) -> SlackNotifier:
        return SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")

    @pytest.fixture
    def message(self) -> SlackMessage:
        return SlackMessage("Hello, Slack!")

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_200_ok(
        self, backend: SlackNotifier, message: SlackMessage
    ) -> None:
        """Webhook 200 + 'ok' body → Ok(MessageDeliveryReceipt)."""
        mock_client = _make_httpx_client(200, text="ok")
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send(message)

        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.backend == "slack_webhook"
        assert receipt.channel == "slack"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_non_ok_body(
        self, backend: SlackNotifier, message: SlackMessage
    ) -> None:
        """Webhook 200 but non-'ok' body → Err(SlackNotificationError)."""
        mock_client = _make_httpx_client(200, text="invalid_payload")
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send(message)

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, SlackNotificationError)
        assert err.slack_error == "invalid_payload"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_4xx(
        self, backend: SlackNotifier, message: SlackMessage
    ) -> None:
        """Webhook 400 → Err(SlackNotificationError)."""
        mock_client = _make_httpx_client(400, text="channel_not_found")
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send(message)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), SlackNotificationError)

    @pytest.mark.asyncio
    async def test_send_with_blocks(self, backend: SlackNotifier) -> None:
        """Blocks are included in the payload."""
        msg = SlackMessage(
            "Fallback",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "*Hi*"}}],
        )
        mock_client = _make_httpx_client(200, text="ok")
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send(msg)

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_send_text_convenience(self, backend: SlackNotifier) -> None:
        """send_text() wraps send() and returns Ok."""
        mock_client = _make_httpx_client(200, text="ok")
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send_text("Quick message")

        assert result.is_ok()


class TestSlackWebhookHealthCheck:
    @pytest.fixture
    def backend(self) -> SlackNotifier:
        return SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")

    @pytest.mark.asyncio
    async def test_health_check_healthy_on_2xx(self, backend: SlackNotifier) -> None:
        """GET slack.com < 500 → HEALTHY."""
        mock_client = _make_httpx_client(200)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.component == "slack_webhook"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_5xx(self, backend: SlackNotifier) -> None:
        """GET slack.com >= 500 → UNHEALTHY."""
        mock_client = _make_httpx_client(503)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.component == "slack_webhook"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_oserror(
        self, backend: SlackNotifier
    ) -> None:
        """OSError during HTTP → UNHEALTHY."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(side_effect=OSError("Network unreachable"))
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.component == "slack_webhook"


class TestSlackBotSend:
    @pytest.fixture
    def backend(self) -> SlackNotifier:
        return SlackNotifier(bot_token="xoxb-test", default_channel="#general")

    @pytest.fixture
    def message(self) -> SlackMessage:
        return SlackMessage("Hello, bot!")

    def _make_bot_client(
        self, ok: bool = True, ts: str = "12345.000", error: str = "unknown"
    ) -> MagicMock:
        mock_resp = {"ok": ok, "ts": ts} if ok else {"ok": ok, "error": error}
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(return_value=mock_resp)
        mock_client.auth_test = AsyncMock(
            return_value={"ok": ok, "team": "TestTeam", "bot_id": "B123"}
        )
        return mock_client

    @pytest.mark.asyncio
    async def test_send_returns_ok_on_success(
        self, backend: SlackNotifier, message: SlackMessage
    ) -> None:
        """Bot API ok=true → Ok(MessageDeliveryReceipt)."""
        mock_client = self._make_bot_client(ok=True, ts="12345.000")
        with _patch_slack_sdk(mock_client):
            result = await backend.send(message)

        assert result.is_ok()
        receipt = result.unwrap()
        assert receipt.backend == "slack_bot"
        assert receipt.channel == "slack"
        assert receipt.provider_reference == "12345.000"

    @pytest.mark.asyncio
    async def test_send_returns_err_on_api_error(
        self, backend: SlackNotifier, message: SlackMessage
    ) -> None:
        """Bot API ok=false → Err(SlackNotificationError)."""
        mock_client = self._make_bot_client(ok=False, error="channel_not_found")
        with _patch_slack_sdk(mock_client):
            result = await backend.send(message)

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, SlackNotificationError)
        assert err.slack_error == "channel_not_found"

    @pytest.mark.asyncio
    async def test_send_returns_err_without_channel(self) -> None:
        """Bot mode with no default_channel and no message.channel → Err."""
        backend = SlackNotifier(bot_token="xoxb-test")
        msg = SlackMessage("No channel set")
        mock_client = MagicMock()
        mock_client.auth_test = AsyncMock(return_value={"ok": True})
        with _patch_slack_sdk(mock_client):
            result = await backend.send(msg)

        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, SlackNotificationError)
        assert err.slack_error == "missing_channel"

    @pytest.mark.asyncio
    async def test_send_message_channel_overrides_default(self) -> None:
        """message.channel takes precedence over default_channel."""
        backend = SlackNotifier(bot_token="xoxb-test", default_channel="#default")
        msg = SlackMessage("Override!", channel="#override")
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(
            return_value={"ok": True, "ts": "999.000"}
        )
        with _patch_slack_sdk(mock_client):
            result = await backend.send(msg)

        assert result.is_ok()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "#override"

    @pytest.mark.asyncio
    async def test_send_with_blocks_and_thread_ts(self, backend: SlackNotifier) -> None:
        """blocks and thread_ts forwarded to chat_postMessage."""
        msg = SlackMessage(
            "Rich message",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "*Hi*"}}],
            thread_ts="98765.000",
        )
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(
            return_value={"ok": True, "ts": "98766.000"}
        )
        with _patch_slack_sdk(mock_client):
            result = await backend.send(msg)

        assert result.is_ok()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert "blocks" in call_kwargs
        assert call_kwargs["thread_ts"] == "98765.000"


class TestSlackBotHealthCheck:
    @pytest.fixture
    def backend(self) -> SlackNotifier:
        return SlackNotifier(bot_token="xoxb-test")

    @pytest.mark.asyncio
    async def test_health_check_healthy_on_auth_test_ok(
        self, backend: SlackNotifier
    ) -> None:
        """auth.test ok=true → HEALTHY."""
        mock_client = MagicMock()
        mock_client.auth_test = AsyncMock(
            return_value={"ok": True, "team": "TestTeam", "bot_id": "B123"}
        )
        with _patch_slack_sdk(mock_client):
            result = await backend.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.component == "slack_bot"
        assert result.details is not None
        assert result.details["team"] == "TestTeam"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_auth_test_fail(
        self, backend: SlackNotifier
    ) -> None:
        """auth.test ok=false → UNHEALTHY."""
        mock_client = MagicMock()
        mock_client.auth_test = AsyncMock(
            return_value={"ok": False, "error": "invalid_auth"}
        )
        with _patch_slack_sdk(mock_client):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.component == "slack_bot"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_oserror(
        self, backend: SlackNotifier
    ) -> None:
        """OSError during auth.test → UNHEALTHY."""
        mock_client = MagicMock()
        mock_client.auth_test = AsyncMock(side_effect=OSError("Connection refused"))
        with _patch_slack_sdk(mock_client):
            result = await backend.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.component == "slack_bot"


class TestMrkdwnEscaping:
    def test_escape_mrkdwn_escapes_link_markup(self) -> None:
        from quadkit.notification.backends.slack.slack_notifier import (
            _escape_mrkdwn,
        )

        assert _escape_mrkdwn("<https://evil.example|click me>") == (
            "&lt;https://evil.example|click me&gt;"
        )

    def test_escape_mrkdwn_escapes_entities(self) -> None:
        from quadkit.notification.backends.slack.slack_notifier import (
            _escape_mrkdwn,
        )

        assert _escape_mrkdwn("a & b") == "a &amp; b"

    def test_plain_text_unchanged(self) -> None:
        from quadkit.notification.backends.slack.slack_notifier import (
            _escape_mrkdwn,
        )

        assert _escape_mrkdwn("hello world") == "hello world"

    @pytest.mark.asyncio
    async def test_webhook_payload_escapes_text(self) -> None:
        backend = SlackNotifier(webhook_url="https://hooks.slack.com/services/T/B/X")
        msg = SlackMessage("<https://evil.example|click me>")
        mock_client = _make_httpx_client(200, text="ok")
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.send(msg)

        assert result.is_ok()
        call_args = mock_client.post.call_args
        assert (
            call_args.kwargs["json"]["text"] == "&lt;https://evil.example|click me&gt;"
        )

    @pytest.mark.asyncio
    async def test_bot_payload_escapes_text(self) -> None:
        backend = SlackNotifier(bot_token="xoxb-test", default_channel="#general")
        msg = SlackMessage("<https://evil.example|click me>")
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(
            return_value={"ok": True, "ts": "999.000"}
        )
        with _patch_slack_sdk(mock_client):
            result = await backend.send(msg)

        assert result.is_ok()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["text"] == "&lt;https://evil.example|click me&gt;"


__all__ = [
    "TestMrkdwnEscaping",
    "TestSlackBotHealthCheck",
    "TestSlackBotSend",
    "TestSlackNotifierInit",
    "TestSlackWebhookHealthCheck",
    "TestSlackWebhookSend",
]
