"""Tests for JWT audience claim enforcement (FAANG finding 06.C-01).

Verifies that:
 - A token carrying a wrong ``aud`` claim is rejected when ``required_audience``
   is configured on the manager.
 - A token carrying the correct ``aud`` claim is accepted.
 - ``allow_missing_audience=True`` bypasses the audience check, acting as an
   explicit escape hatch for internal trusted-service paths.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.validation import SecretStr

_SECRET = "test-secret-key-that-is-long-enough"
_ALGORITHM = "HS256"


def _make_token(
    sub: str,
    token_type: str = "access",
    audience: str | None = None,
) -> str:
    """Craft a raw JWT for testing without going through the creation mixin.

    Using ``jwt.encode`` directly lets us control the ``aud`` claim freely,
    including omitting it entirely when ``audience`` is ``None``.
    """
    now = datetime.now(UTC)
    payload: dict = {
        "sub": sub,
        "type": token_type,
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iat": int(now.timestamp()),
    }
    if audience is not None:
        payload["aud"] = audience

    return pyjwt.encode(
        payload,
        _SECRET,
        algorithm=_ALGORITHM,
        headers={"kid": "default"},
    )


class TestJWTAudienceEnforcement:
    """Suite covering audience enforcement in JWTTokenManager.verify_token."""

    @pytest.mark.asyncio
    async def test_wrong_audience_rejected(self) -> None:
        """Token with ``aud`` that doesn't match ``required_audience`` is rejected."""
        manager = JWTTokenManager(
            SecretStr(_SECRET),
            required_audience="my-service",
        )
        token = _make_token("user-1", audience="wrong-service")

        result = await manager.verify_token(token, token_type="access")

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_correct_audience_accepted(self) -> None:
        """Token carrying the expected ``aud`` claim is verified successfully."""
        manager = JWTTokenManager(
            SecretStr(_SECRET),
            required_audience="my-service",
        )
        token = _make_token("user-1", audience="my-service")

        result = await manager.verify_token(token, token_type="access")

        assert result.is_ok()
        verified = result.unwrap()
        assert verified.user_id == "user-1"

    @pytest.mark.asyncio
    async def test_allow_missing_audience_flag_bypasses_check(self) -> None:
        """``allow_missing_audience=True`` is the explicit opt-out escape hatch.

        Even when ``required_audience`` is set on the manager, passing the flag
        must allow a token that has no ``aud`` claim to verify successfully.
        """
        manager = JWTTokenManager(
            SecretStr(_SECRET),
            required_audience="my-service",
        )
        token = _make_token("user-1", audience=None)  # token has no aud claim

        result = await manager.verify_token(
            token,
            token_type="access",
            allow_missing_audience=True,
        )

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_no_required_audience_still_works(self) -> None:
        """Backward compatibility: manager without ``required_audience`` verifies normally."""
        manager = JWTTokenManager(SecretStr(_SECRET))
        token = _make_token("user-2")  # no aud claim

        result = await manager.verify_token(token, token_type="access")

        assert result.is_ok()
        assert result.unwrap().user_id == "user-2"

    @pytest.mark.asyncio
    async def test_expected_audience_param_still_honoured(self) -> None:
        """Passing ``expected_audience`` directly on the call site still works."""
        manager = JWTTokenManager(SecretStr(_SECRET))
        token = _make_token("user-3", audience="call-site-svc")

        result = await manager.verify_token(
            token,
            token_type="access",
            expected_audience="call-site-svc",
        )

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_expected_audience_param_overrides_required_audience(self) -> None:
        """Call-site ``expected_audience`` takes precedence over the manager config."""
        manager = JWTTokenManager(
            SecretStr(_SECRET),
            required_audience="default-svc",
        )
        # Token carries the call-site audience, not the manager-level one
        token = _make_token("user-4", audience="override-svc")

        result = await manager.verify_token(
            token,
            token_type="access",
            expected_audience="override-svc",
        )

        assert result.is_ok()
