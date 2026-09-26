"""Tests for QK-002: verified-only JWT mode (no unverified decoding path).

Policy summary
--------------
- PRODUCTION / STAGING + missing secret → raises at boot (ConfigurationError)
- PRODUCTION / STAGING + default/weak secret → raises
- DEVELOPMENT + missing secret → boots with a generated ephemeral secret,
  signature verification stays enabled (tokens invalidated on restart)
- DEVELOPMENT + valid secret → verifies signatures
- Valid secret + valid signature → succeeds in all environments
- Valid secret + tampered/wrong-secret/unsigned token → Err (TokenInvalidError)
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from pydantic import SecretStr

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.config import JWTConfig
from quadkit.auth.di.sub_providers.token_provider import TokenProvider
from quadkit.contracts.exceptions import ConfigurationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_SECRET = "a" * 33  # 33-char secret, passes the HS256 ≥32-byte check
_GOOD_AUDIENCE = "my-service"


def _make_token(secret: str, payload: dict[str, Any] | None = None) -> str:
    """Create a signed HS256 JWT for testing."""
    claims: dict[str, Any] = {
        "sub": "user-123",
        "email": "test@example.com",
        "type": "access",
        "exp": 9999999999,
    }
    if payload:
        claims.update(payload)
    return jwt.encode(claims, secret, algorithm="HS256")


def _make_unsigned_token(payload: dict[str, Any] | None = None) -> str:
    """Create an *unsigned* (algorithm=none) JWT via raw construction."""
    import base64
    import json

    header = (
        base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    )
    claims: dict[str, Any] = {
        "sub": "user-123",
        "email": "test@example.com",
        "type": "access",
        "exp": 9999999999,
    }
    if payload:
        claims.update(payload)
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{body}."


def _make_manager(secret: str = _GOOD_SECRET, **kwargs: Any) -> JWTTokenManager:
    return JWTTokenManager(
        current_key_id=SecretStr(secret),
        **kwargs,
    )


def _mock_token_config(secret: str | None, /) -> Any:
    """Build a minimal mock config for TokenProvider boot tests."""
    from unittest.mock import MagicMock

    token_cfg = MagicMock()
    token_cfg.secret_key = SecretStr(secret) if secret is not None else None
    token_cfg.algorithm = "HS256"
    token_cfg.access_expiration_hours = 1
    token_cfg.refresh_expiration_days = 7
    token_cfg.key_rotation_grace_period_seconds = 3600
    cfg = MagicMock()
    cfg.token = token_cfg
    return cfg


# ---------------------------------------------------------------------------
# JWTConfig validator tests
# ---------------------------------------------------------------------------


class TestJWTConfigVerificationPolicy:
    def test_allows_valid_secret_in_development(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "development"}):
            cfg = JWTConfig(secret_key=_GOOD_SECRET)
            assert cfg.secret_key.get_secret_value() == _GOOD_SECRET

    def test_allows_valid_secret_in_production(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "production"}):
            cfg = JWTConfig(secret_key=_GOOD_SECRET, required_audience=_GOOD_AUDIENCE)
            assert cfg.secret_key.get_secret_value() == _GOOD_SECRET
            assert cfg.required_audience == _GOOD_AUDIENCE

    def test_allows_valid_secret_in_staging(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "staging"}):
            cfg = JWTConfig(secret_key=_GOOD_SECRET, required_audience=_GOOD_AUDIENCE)
            assert cfg.secret_key.get_secret_value() == _GOOD_SECRET

    def test_rejects_default_secret_in_production(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "production"}):
            with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR"):
                JWTConfig(secret_key="change-me")

    def test_rejects_default_secret_in_staging(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "staging"}):
            with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR"):
                JWTConfig(secret_key="change-me")

    def test_rejects_missing_audience_in_production(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "production"}):
            with pytest.raises(ValueError, match="required_audience"):
                JWTConfig(secret_key=_GOOD_SECRET)

    def test_rejects_missing_audience_in_staging(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "staging"}):
            with pytest.raises(ValueError, match="required_audience"):
                JWTConfig(secret_key=_GOOD_SECRET)

    def test_allows_missing_audience_in_development(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "development"}):
            cfg = JWTConfig(secret_key=_GOOD_SECRET)
            assert cfg.required_audience is None


# ---------------------------------------------------------------------------
# TokenProvider boot-time policy tests
# ---------------------------------------------------------------------------


class TestTokenProviderBootPolicy:
    """TokenProvider enforces the verified-only JWT policy at __init__ time."""

    def _provider_with_env(self, env: str, secret: str | None) -> TokenProvider:
        """Build a TokenProvider with a mock config in the given env."""
        with patch.dict(os.environ, {"QK_ENV": env}):
            return TokenProvider(config=_mock_token_config(secret))

    # ── PRODUCTION ──────────────────────────────────────────────────────────

    def test_production_missing_secret_raises(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "production"}):
            with pytest.raises(ConfigurationError, match="CRITICAL SECURITY"):
                TokenProvider(config=_mock_token_config(None))

    def test_production_valid_secret_boots_verified_only(self) -> None:
        provider = self._provider_with_env("production", _GOOD_SECRET)
        assert provider.secret_key == _GOOD_SECRET

    # ── STAGING ─────────────────────────────────────────────────────────────

    def test_staging_missing_secret_raises(self) -> None:
        with patch.dict(os.environ, {"QK_ENV": "staging"}):
            with pytest.raises(ConfigurationError, match="CRITICAL SECURITY"):
                TokenProvider(config=_mock_token_config(None))

    def test_staging_valid_secret_boots_verified_only(self) -> None:
        provider = self._provider_with_env("staging", _GOOD_SECRET)
        assert provider.secret_key == _GOOD_SECRET

    # ── DEVELOPMENT ─────────────────────────────────────────────────────────

    def test_development_missing_secret_boots_with_ephemeral_secret(self) -> None:
        """Missing dev secret falls back to an ephemeral secret — no unverified mode."""
        provider = self._provider_with_env("development", None)
        assert len(provider.secret_key) >= 32
        assert provider.secret_key != _GOOD_SECRET

    def test_development_missing_secret_logs_ephemeral_warning(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Boot with a missing dev secret logs the ephemeral-secret warning."""
        with patch.dict(os.environ, {"QK_ENV": "development"}):
            TokenProvider(config=_mock_token_config(None))

        captured = capsys.readouterr()
        combined = (captured.out + captured.err).lower()
        assert "ephemeral" in combined, (
            f"Expected an ephemeral-secret warning in stdout/stderr, got:\n{combined[:500]}"
        )

    def test_development_valid_secret_boots_verified_only(self) -> None:
        provider = self._provider_with_env("development", _GOOD_SECRET)
        assert provider.secret_key == _GOOD_SECRET


# ---------------------------------------------------------------------------
# JWTTokenManager verified-path tests (regression: no unverified decoding)
# ---------------------------------------------------------------------------


class TestJWTTokenManagerVerifiedPath:
    """Every decode verifies the signature; there is no unverified mode."""

    @pytest.fixture
    def manager(self) -> JWTTokenManager:
        return _make_manager()

    @pytest.mark.asyncio
    async def test_valid_token_succeeds(self, manager: JWTTokenManager) -> None:
        token = _make_token(_GOOD_SECRET)
        result = await manager.verify_token(token)
        assert result.is_ok(), f"Expected Ok, got: {result}"
        verified = result.unwrap()
        assert verified.user_id == "user-123"

    @pytest.mark.asyncio
    async def test_tampered_signature_fails(self, manager: JWTTokenManager) -> None:
        token = _make_token(_GOOD_SECRET)
        # Corrupt the signature portion (last segment).
        parts = token.split(".")
        parts[-1] = parts[-1][:-4] + "XXXX"
        tampered = ".".join(parts)
        result = await manager.verify_token(tampered)
        assert result.is_err(), "Expected Err for tampered token"

    @pytest.mark.asyncio
    async def test_wrong_secret_fails(self, manager: JWTTokenManager) -> None:
        token = _make_token("wrong-secret-key-that-is-at-least-32-chars")
        result = await manager.verify_token(token)
        assert result.is_err(), "Expected Err for token signed with wrong secret"

    @pytest.mark.asyncio
    async def test_unsigned_token_fails(self, manager: JWTTokenManager) -> None:
        """alg=none tokens are rejected — signature verification is always on."""
        token = _make_unsigned_token()
        result = await manager.verify_token(token)
        assert result.is_err(), "Expected Err for unsigned token"

    @pytest.mark.asyncio
    async def test_expired_token_fails(self, manager: JWTTokenManager) -> None:
        import time

        expired_token = _make_token(
            _GOOD_SECRET,
            payload={"exp": int(time.time()) - 3600},
        )
        result = await manager.verify_token(expired_token)
        assert result.is_err(), "Expected Err for expired token"

    @pytest.mark.asyncio
    async def test_dev_ephemeral_secret_rejects_foreign_signature(self) -> None:
        """A manager booted with an ephemeral secret still verifies signatures."""
        import secrets

        manager = _make_manager(secrets.token_urlsafe(32))
        token = _make_token("completely-different-secret-xyz")
        result = await manager.verify_token(token)
        assert result.is_err(), "Expected Err for token signed with another secret"
