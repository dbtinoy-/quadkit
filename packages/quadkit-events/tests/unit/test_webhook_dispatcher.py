"""Tests for WebhookDispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from quadkit.contracts.domain.events import DomainEvent
from quadkit.contracts.web.http_models import HttpResponse
from quadkit.contracts.infra.resilience.models import RetryConfig
from quadkit.events.exceptions import WebhookDeliveryError
from quadkit.events.webhooks.dispatcher import WebhookDispatcher, WebhookEndpoint


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserCreatedEvent(DomainEvent):
    """Minimal domain event for tests."""

    user_id: str = "user-123"


def _mock_http_client(status: int = 200) -> MagicMock:
    client = MagicMock()
    client.post = AsyncMock(
        return_value=HttpResponse(status=status, body=b"", text="", url="", method="POST")
    )
    return client


def _mock_verifier(signature: str = "sha256=abc123") -> MagicMock:
    verifier = MagicMock()
    verifier.compute_signature = MagicMock(return_value=signature)
    verifier.verify = MagicMock(return_value=True)
    return verifier


# ---------------------------------------------------------------------------
# WebhookEndpoint.accepts()
# ---------------------------------------------------------------------------


class TestWebhookEndpointAccepts:
    def test_accepts_all_events_when_event_types_none(self) -> None:
        endpoint = WebhookEndpoint(url="https://example.com", secret="s")
        assert endpoint.accepts(UserCreatedEvent()) is True

    def test_accepts_matching_event_type(self) -> None:
        endpoint = WebhookEndpoint(
            url="https://example.com",
            secret="s",
            event_types={"UserCreatedEvent"},
        )
        assert endpoint.accepts(UserCreatedEvent()) is True

    def test_rejects_non_matching_event_type(self) -> None:
        endpoint = WebhookEndpoint(
            url="https://example.com",
            secret="s",
            event_types={"OrderPlacedEvent"},
        )
        assert endpoint.accepts(UserCreatedEvent()) is False


# ---------------------------------------------------------------------------
# WebhookDispatcher.dispatch()
# ---------------------------------------------------------------------------


class TestWebhookDispatcherDispatch:
    @pytest.mark.asyncio
    async def test_posts_event_to_single_endpoint(self) -> None:
        http_client = _mock_http_client(status=200)
        verifier = _mock_verifier(signature="sha256=sig")
        dispatcher = WebhookDispatcher(http_client=http_client, signature_verifier=verifier)
        endpoint = WebhookEndpoint(url="https://hooks.example.com/events", secret="secret")

        await dispatcher.dispatch(UserCreatedEvent(), [endpoint])

        http_client.post.assert_awaited_once()
        args, kwargs = http_client.post.call_args
        assert args[0] == "https://hooks.example.com/events"
        assert kwargs["headers"]["X-Webhook-Signature"] == "sha256=sig"
        assert kwargs["headers"]["X-Webhook-Event-Type"] == "UserCreatedEvent"
        assert kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_fan_out_to_multiple_endpoints(self) -> None:
        http_client = _mock_http_client(status=200)
        verifier = _mock_verifier()
        dispatcher = WebhookDispatcher(http_client=http_client, signature_verifier=verifier)
        endpoints = [
            WebhookEndpoint(url="https://a.example.com", secret="s1"),
            WebhookEndpoint(url="https://b.example.com", secret="s2"),
        ]

        await dispatcher.dispatch(UserCreatedEvent(), endpoints)

        assert http_client.post.await_count == 2
        urls = [c.args[0] for c in http_client.post.call_args_list]
        assert "https://a.example.com" in urls
        assert "https://b.example.com" in urls

    @pytest.mark.asyncio
    async def test_skips_endpoints_not_matching_event_type(self) -> None:
        http_client = _mock_http_client(status=200)
        verifier = _mock_verifier()
        dispatcher = WebhookDispatcher(http_client=http_client, signature_verifier=verifier)
        endpoints = [
            WebhookEndpoint(url="https://a.example.com", secret="s", event_types={"OrderPlaced"}),
            WebhookEndpoint(url="https://b.example.com", secret="s", event_types={"UserCreatedEvent"}),
        ]

        await dispatcher.dispatch(UserCreatedEvent(), endpoints)

        assert http_client.post.await_count == 1
        args, _ = http_client.post.call_args
        assert args[0] == "https://b.example.com"

    @pytest.mark.asyncio
    async def test_signs_payload_with_endpoint_secret(self) -> None:
        http_client = _mock_http_client(status=200)
        verifier = _mock_verifier()
        dispatcher = WebhookDispatcher(http_client=http_client, signature_verifier=verifier)
        endpoint = WebhookEndpoint(url="https://example.com", secret="my-secret")

        await dispatcher.dispatch(UserCreatedEvent(), [endpoint])

        verifier.compute_signature.assert_called_once()
        _, secret_arg = verifier.compute_signature.call_args.args
        assert secret_arg == "my-secret"

    @pytest.mark.asyncio
    async def test_no_post_for_empty_endpoints(self) -> None:
        http_client = _mock_http_client(status=200)
        verifier = _mock_verifier()
        dispatcher = WebhookDispatcher(http_client=http_client, signature_verifier=verifier)

        await dispatcher.dispatch(UserCreatedEvent(), [])

        http_client.post.assert_not_awaited()


# ---------------------------------------------------------------------------
# Retry behaviour on 5xx responses
# ---------------------------------------------------------------------------


class TestWebhookDispatcherRetry:
    @pytest.mark.asyncio
    async def test_5xx_response_is_retried(self) -> None:
        """WebhookDeliveryError from a 500 response triggers retry."""
        # Fail once with 500, succeed on second attempt
        http_client = MagicMock()
        ok_response = HttpResponse(status=200, body=b"", text="", url="", method="POST")
        fail_response = HttpResponse(status=503, body=b"", text="", url="", method="POST")
        http_client.post = AsyncMock(side_effect=[fail_response, ok_response])

        verifier = _mock_verifier()
        retry_policy = RetryConfig(max_attempts=3, base_delay=0.0, jitter=False)
        dispatcher = WebhookDispatcher(
            http_client=http_client,
            signature_verifier=verifier,
            retry_policy=retry_policy,
        )
        endpoint = WebhookEndpoint(url="https://example.com", secret="s")

        # Should not raise; second attempt succeeds
        await dispatcher.dispatch(UserCreatedEvent(), [endpoint])

        assert http_client.post.await_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_logs_error(self) -> None:
        """After all retry attempts fail, the error is logged and fan-out continues."""
        fail_response = HttpResponse(status=500, body=b"", text="", url="", method="POST")
        http_client = MagicMock()
        http_client.post = AsyncMock(return_value=fail_response)

        verifier = _mock_verifier()
        retry_policy = RetryConfig(max_attempts=2, base_delay=0.0, jitter=False)
        dispatcher = WebhookDispatcher(
            http_client=http_client,
            signature_verifier=verifier,
            retry_policy=retry_policy,
        )
        endpoint = WebhookEndpoint(url="https://example.com", secret="s")

        # Should not raise — error is logged
        with patch.object(type(dispatcher), "_deliver_to", wraps=dispatcher._deliver_to):
            await dispatcher.dispatch(UserCreatedEvent(), [endpoint])

        # dispatch reached the endpoint (retried max_attempts times)
        assert http_client.post.await_count == retry_policy.max_attempts

    @pytest.mark.asyncio
    async def test_failure_on_one_endpoint_does_not_abort_others(self) -> None:
        """Fan-out continues to remaining endpoints after one fails."""
        fail_response = HttpResponse(status=500, body=b"", text="", url="", method="POST")
        ok_response = HttpResponse(status=200, body=b"", text="", url="", method="POST")

        responses: list[HttpResponse] = [fail_response, ok_response]
        http_client = MagicMock()
        http_client.post = AsyncMock(side_effect=responses)

        verifier = _mock_verifier()
        # Single attempt so first endpoint fails immediately
        retry_policy = RetryConfig(max_attempts=1, base_delay=0.0, jitter=False)
        dispatcher = WebhookDispatcher(
            http_client=http_client,
            signature_verifier=verifier,
            retry_policy=retry_policy,
        )
        endpoints = [
            WebhookEndpoint(url="https://bad.example.com", secret="s"),
            WebhookEndpoint(url="https://good.example.com", secret="s"),
        ]

        await dispatcher.dispatch(UserCreatedEvent(), endpoints)

        assert http_client.post.await_count == 2
        posted_urls = [c.args[0] for c in http_client.post.call_args_list]
        assert "https://bad.example.com" in posted_urls
        assert "https://good.example.com" in posted_urls


# ---------------------------------------------------------------------------
# WebhookDeliveryError
# ---------------------------------------------------------------------------


class TestWebhookDeliveryError:
    def test_stores_url_and_status(self) -> None:
        err = WebhookDeliveryError(url="https://example.com", status=503)
        assert err.url == "https://example.com"
        assert err.status == 503

    def test_default_message(self) -> None:
        err = WebhookDeliveryError(url="https://x.com", status=500)
        assert "500" in str(err) or "Webhook delivery failed" in str(err)
