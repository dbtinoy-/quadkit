"""Token creation mixin for :class:`~quadkit.auth.authn.jwt.JWTTokenManager`.

This module is an internal implementation detail; import
:class:`~quadkit.auth.authn.jwt.JWTTokenManager` directly.
"""

from __future__ import annotations

from datetime import timedelta
import secrets
from typing import Any

import jwt

from quadkit.auth.authn._binding import TokenBindingConfig, compute_binding_hash
from quadkit.auth.models import AuthToken
from quadkit.auth.models.user import User
from quadkit.contracts.core.identity import IdGeneratorProtocol
from quadkit.primitives import clock as ambient_clock


class _JWTCreationMixin:
    """Mixin providing JWT token-creation methods for :class:`JWTTokenManager`.

    All public attributes referenced here are initialised by
    ``JWTTokenManager.__init__``; they are declared below as class-level
    annotations solely to satisfy static type checkers.
    """

    # ── Attributes set by JWTTokenManager.__init__ ───────────────────────────
    algorithm: str
    access_expiration_hours: int
    refresh_expiration_days: int
    _required_audience: str | None
    _binding_config: TokenBindingConfig | None

    def __init__(
        self,
        ids: IdGeneratorProtocol | None = None,
    ) -> None:
        """Initialize the JWT creation mixin.

        Args:
            ids: Optional ID generator for JTI claims.
        """
        self._ids = ids

    @property
    def current_key_id(self) -> str:  # pragma: no cover
        """Active signing key ID — provided by JWTTokenManager."""
        raise NotImplementedError

    def _get_signing_key(self) -> str:  # pragma: no cover
        """Return raw signing key — provided by JWTTokenManager."""
        raise NotImplementedError

    # ─────────────────────────────────────────────────────────────────────────

    def create_access_token(
        self,
        user: User,
        additional_claims: dict[str, Any] | None = None,
        binding_context: dict[str, str] | None = None,
    ) -> str:
        """Create a JWT access token for a user with current key."""
        now = ambient_clock.now()
        expires_at = now + timedelta(hours=self.access_expiration_hours)

        # Previously we included the user's username in the token.  The
        # field was deprecated in favour of ``name`` so callers can refer to a
        # human-readable label without using the deprecated word "username".
        # Authentication logic should still use ``sub`` (user_id) and email.
        payload = {
            "sub": user.user_id,
            "email": user.email,
            # include name for compatibility with tests and helpers
            "name": user.name,
            "roles": user.roles,
            "permissions": user.permissions,
            "type": "access",
            # Audience minted only when required_audience is configured,
            # keeping default deployments byte-compatible.
            **({"aud": self._required_audience} if self._required_audience else {}),
            "jti": self._ids.generate_for("Token")
            if self._ids
            else secrets.token_urlsafe(16),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }

        if additional_claims:
            payload.update(additional_claims)

        if self._binding_config and binding_context:
            bind_hash = compute_binding_hash(self._binding_config, binding_context)
            if bind_hash:
                payload["bind"] = bind_hash

        # Include key ID in header for verification
        headers = {"kid": self.current_key_id}

        signing_key = self._get_signing_key()
        return jwt.encode(
            payload,
            signing_key,
            algorithm=self.algorithm,
            headers=headers,
        )

    def create_refresh_token(
        self,
        user: User,
        binding_context: dict[str, str] | None = None,
    ) -> str:
        """Create a JWT refresh token for a user."""
        now = ambient_clock.now()
        expires_at = now + timedelta(days=self.refresh_expiration_days)

        payload = {
            "sub": user.user_id,
            "type": "refresh",
            # Audience minted only when required_audience is configured,
            # keeping default deployments byte-compatible.
            **({"aud": self._required_audience} if self._required_audience else {}),
            "jti": self._ids.generate_for("Token")
            if self._ids
            else secrets.token_urlsafe(16),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }

        if self._binding_config and binding_context:
            bind_hash = compute_binding_hash(self._binding_config, binding_context)
            if bind_hash:
                payload["bind"] = bind_hash

        # Include key ID in header for verification
        headers = {"kid": self.current_key_id}

        signing_key = self._get_signing_key()
        return jwt.encode(
            payload,
            signing_key,
            algorithm=self.algorithm,
            headers=headers,
        )

    def create_token_pair(
        self,
        user: User,
        additional_claims: dict[str, Any] | None = None,
        binding_context: dict[str, str] | None = None,
    ) -> AuthToken:
        """Create both access and refresh tokens."""
        access_token = self.create_access_token(
            user, additional_claims, binding_context
        )
        refresh_token = self.create_refresh_token(user, binding_context)

        now = ambient_clock.now()
        access_expires = now + timedelta(hours=self.access_expiration_hours)
        refresh_expires = now + timedelta(days=self.refresh_expiration_days)

        return AuthToken(
            token=access_token,
            expires_at=access_expires,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_expires,
        )

    def create_token(
        self,
        user: Any,
        additional_claims: dict[str, Any] | None = None,
        binding_context: dict[str, str] | None = None,
    ) -> AuthToken:
        """Create auth tokens for a user, satisfying the TokenManagerProtocol protocol.

        Delegates to :meth:`create_token_pair`.  This alias exists so that
        ``isinstance(manager, TokenManagerProtocol)`` passes the runtime-checkable
        protocol check from ``quadkit.contracts.auth.token``.

        Args:
            user: Authenticated user object.
            additional_claims: Optional extra JWT payload fields.
            binding_context: Optional request context dict for token binding.
                Recognised keys: ``ip``, ``fingerprint``.

        Returns:
            AuthToken containing the access and refresh tokens.
        """
        return self.create_token_pair(user, additional_claims, binding_context)
