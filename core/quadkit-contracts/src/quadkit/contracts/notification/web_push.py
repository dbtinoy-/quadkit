"""Web Push notification value types — RFC 8030 subscription format."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WebPushKeys:
    """Crypto keys for Web Push message encryption (RFC 8291).

    Mirrors the ``keys`` property of the browser
    ``PushSubscription.toJSON()`` output.

    Attributes:
        p256dh: Base64URL-encoded P-256 ECDH public key.
        auth: Base64URL-encoded authentication secret.
    """

    p256dh: str
    auth: str


@dataclass(frozen=True, slots=True)
class WebPushSubscription:
    """A browser Web Push subscription — RFC 8030 endpoint + keys.

    Mirrors the top-level shape of ``PushSubscription.toJSON()``.

    Attributes:
        endpoint: The push service URL that accepts encrypted messages.
        keys: The P-256 public key + auth secret for encryption.
        expiration_time: Unix timestamp (seconds) when the subscription
            expires, or ``None`` if it never expires.
    """

    endpoint: str
    keys: WebPushKeys
    expiration_time: int | None = None


__all__ = ["WebPushKeys", "WebPushSubscription"]
