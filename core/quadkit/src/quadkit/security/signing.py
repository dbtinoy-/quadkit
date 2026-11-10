"""HMAC message signing and URL-safe signed token helpers.

Provides constant-time HMAC-SHA256 signing and verification for stateless
cursors, callback state tokens, and webhook signatures without forcing
application code to import ``hmac`` / ``hashlib`` directly.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
import hashlib
import hmac
from typing import Any

from quadkit.security.exceptions import SecurityError
from quadkit.security.secrets import SecretValue
from quadkit.serialization import JSONDecodeError, dumps_str, loads


def _unwrap_key(secret: str | bytes | Any) -> bytes:
    if isinstance(secret, bytes):
        raw = secret
    elif isinstance(secret, SecretValue):
        raw = str.__str__(secret).encode("utf-8")
    elif hasattr(secret, "get_secret_value"):
        raw = str(secret.get_secret_value()).encode("utf-8")
    else:
        raw = str(secret).encode("utf-8")
    if not raw:
        msg = "HMAC signing secret must not be empty"
        raise SecurityError(msg)
    return raw


class HmacSigner:
    """Stateless HMAC-SHA256 signer and URL-safe JSON token packer."""

    def __init__(
        self,
        secret: str | bytes | SecretValue,
        *,
        digest_chars: int = 32,
    ) -> None:
        if digest_chars < 16 or digest_chars > 64:
            msg = "digest_chars must be between 16 and 64 hex characters"
            raise ValueError(msg)
        self._key = _unwrap_key(secret)
        self._digest_chars = digest_chars

    def sign(self, data: str | bytes) -> str:
        """Compute hex HMAC-SHA256 signature over *data*."""
        payload = data.encode("utf-8") if isinstance(data, str) else data
        digest = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
        return digest[: self._digest_chars]

    def verify(self, data: str | bytes, signature: str) -> bool:
        """Verify *signature* against *data* in constant time."""
        expected = self.sign(data)
        return hmac.compare_digest(signature, expected)

    def pack(self, payload: Mapping[str, Any]) -> str:
        """Encode *payload* as ``<urlsafe_b64_json>.<hmac_hex>``."""
        encoded = (
            base64.urlsafe_b64encode(dumps_str(dict(payload)).encode("utf-8"))
            .decode("ascii")
            .rstrip("=")
        )
        sig = self.sign(encoded)
        return f"{encoded}.{sig}"

    def unpack(self, token: str) -> dict[str, Any]:
        """Verify signature and decode ``<urlsafe_b64_json>.<hmac_hex>``."""
        try:
            encoded, sig = token.split(".", 1)
        except ValueError as exc:
            msg = "Malformed signed token"
            raise SecurityError(msg) from exc

        if not self.verify(encoded, sig):
            msg = "Signature mismatch"
            raise SecurityError(msg)

        padding = "=" * (-len(encoded) % 4)
        try:
            decoded = loads(base64.urlsafe_b64decode(encoded + padding))
        except (ValueError, JSONDecodeError) as exc:
            msg = "Invalid signed token payload"
            raise SecurityError(msg) from exc

        if not isinstance(decoded, dict):
            msg = "Signed token payload must be a JSON object"
            raise SecurityError(msg)
        return decoded


__all__ = ["HmacSigner"]
