"""JWT key rotation helpers.

This module provides the :class:`JWTKeyStore` helper that manages the
lifecycle of JWT signing keys — adding new keys, retiring old ones after a
grace period, and exposing the correct key material for signing and
verification.

The :class:`~quadkit.auth.authn.jwt.JWTTokenManager` delegates all key
management to this class.

Example::

    from quadkit.auth.authn.key_rotation import JWTKeyStore
    from quadkit.validation import SecretStr

    store = JWTKeyStore(
        current_key_id="v1",
        keys={"v1": SecretStr("super-secret")},
        grace_period_seconds=3600,
    )
    await store.rotate("v2", "new-super-secret")
    signing_key = store.get_signing_key()
"""

from __future__ import annotations

from typing import Any, cast

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.validation import SecretStr

__all__ = ["JWTKeyStore"]

logger = get_logger(__name__)


class JWTKeyStore:
    """Manages JWT signing keys with support for seamless rotation.

    Keys are kept for a configurable grace period after rotation so that
    tokens signed with the old key remain verifiable during the overlap
    window.

    Args:
        current_key_id: The key ID that should be used for signing new tokens.
        keys: Mapping of key ID → key material.  Values may be
            :class:`~quadkit.validation.SecretStr` instances (symmetric) or
            dicts with ``"private"``/``"public"`` entries (asymmetric).
        grace_period_seconds: How long to retain retired keys before deletion.
            Defaults to 3600 s (1 hour).
    """

    def __init__(
        self,
        current_key_id: str,
        keys: dict[str, Any] | None = None,
        grace_period_seconds: float = 3600.0,
    ) -> None:
        self.current_key_id = current_key_id
        self.keys: dict[str, Any] = keys or {}
        self.grace_period_seconds = grace_period_seconds
        self._key_meta: dict[str, dict[str, Any]] = {
            kid: {"created_at": ambient_clock.now()} for kid in self.keys
        }

    # ── Rotation ──────────────────────────────────────────────────────────

    async def rotate(self, new_key_id: str, new_secret: str | dict) -> None:
        """Switch to a new signing key, retaining the old one for the grace period.

        Args:
            new_key_id: Identifier for the new key.
            new_secret: Key material — a plain string for HMAC algorithms or a
                dict with ``"private"`` / ``"public"`` entries for RSA/EC.
        """
        if isinstance(new_secret, dict):
            self.keys[new_key_id] = {
                sk: SecretStr(sv) if isinstance(sv, str) else sv
                for sk, sv in new_secret.items()
            }
        else:
            self.keys[new_key_id] = (
                SecretStr(new_secret) if isinstance(new_secret, str) else new_secret
            )
        self._key_meta[new_key_id] = {"created_at": ambient_clock.now()}
        self.current_key_id = new_key_id
        await self._cleanup_old_keys()

    async def _cleanup_old_keys(self) -> None:
        """Remove keys that have been retired beyond the grace period."""
        if not self._key_meta:
            return

        now = ambient_clock.now()
        remove: list[str] = []
        for kid, meta in list(self._key_meta.items()):
            created = meta.get("created_at")
            if not created:
                continue
            if (now - created).total_seconds() > self.grace_period_seconds:
                if kid != self.current_key_id:
                    remove.append(kid)

        for kid in remove:
            self.keys.pop(kid, None)
            self._key_meta.pop(kid, None)

    # ── Key access ────────────────────────────────────────────────────────

    def get_signing_key(self) -> str:
        """Return the raw signing key string for the current key ID."""
        val = self.keys[self.current_key_id]
        if isinstance(val, dict):
            return cast("str", val["private"].get_secret_value())
        return cast("str", val.get_secret_value())

    def get_verification_key(self, kid: str) -> str | None:
        """Return the raw verification key string for *kid*, or ``None``."""
        val = self.keys.get(kid)
        if val is None:
            return None
        if isinstance(val, dict):
            key_entry = val.get("public") or val.get("private")
            return cast(
                "str | None", key_entry.get_secret_value() if key_entry else None
            )
        return cast("str", val.get_secret_value())

    def list_keys(self) -> dict[str, dict[str, Any]]:
        """Return a copy of the key metadata dict (for inspection/auditing)."""
        return {k: v.copy() for k, v in self._key_meta.items()}
