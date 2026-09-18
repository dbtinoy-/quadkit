"""Tests for Web Push value types."""
from __future__ import annotations

from quadkit.contracts.notification import WebPushKeys, WebPushSubscription


class TestWebPushKeys:
    def test_construct(self) -> None:
        keys = WebPushKeys(p256dh="abc123", auth="def456")
        assert keys.p256dh == "abc123"
        assert keys.auth == "def456"

    def test_frozen(self) -> None:
        keys = WebPushKeys(p256dh="abc", auth="def")
        import pytest
        with pytest.raises(AttributeError):
            keys.p256dh = "xyz"  # type: ignore[misc]


class TestWebPushSubscription:
    def test_construct_without_expiry(self) -> None:
        sub = WebPushSubscription(
            endpoint="https://push.example.com/abc",
            keys=WebPushKeys(p256dh="x", auth="y"),
        )
        assert sub.endpoint == "https://push.example.com/abc"
        assert sub.keys.p256dh == "x"
        assert sub.expiration_time is None

    def test_construct_with_expiry(self) -> None:
        sub = WebPushSubscription(
            endpoint="https://push.example.com/abc",
            keys=WebPushKeys(p256dh="x", auth="y"),
            expiration_time=1712345678,
        )
        assert sub.expiration_time == 1712345678

    def test_frozen(self) -> None:
        sub = WebPushSubscription(
            endpoint="https://push.example.com/abc",
            keys=WebPushKeys(p256dh="x", auth="y"),
        )
        import pytest
        with pytest.raises(AttributeError):
            sub.endpoint = "changed"  # type: ignore[misc]

    def test_exported_from_package(self) -> None:
        from quadkit.contracts.notification import WebPushSubscription as WPS
        assert WPS is WebPushSubscription
