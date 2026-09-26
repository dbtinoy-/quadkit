"""Round 41 hardening pins — quadkit-auth: verify_token returns Err.

_JWTVerificationMixin.verify_token — a verification failure with a
non-infra error type (e.g. a JWKS client failure, not a PyJWT token
error and not RuntimeError/OSError/ConnectionError) returns
Err(TokenError) instead of raising raw. Documented infra errors
(RuntimeError/OSError/ConnectionError) still propagate.

Run with: pytest tests/unit/test_round41_hardening.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quadkit.auth.authn import _jwt_verification as module
from quadkit.contracts.auth.exceptions import TokenError

pytestmark = pytest.mark.unit


class _DriverError(Exception):
    """Stand-in for a JWKS/driver failure (not a PyJWT token error)."""


class TestVerifyTokenDriverFailure:
    @pytest.mark.asyncio
    async def test_driver_error_becomes_err(self) -> None:
        verifier = module._JWTVerificationMixin()

        with patch.object(
            module.jwt, "get_unverified_header", side_effect=_DriverError("jwks wedged")
        ):
            result = await verifier.verify_token("header.payload.sig")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), TokenError)

    @pytest.mark.asyncio
    async def test_infra_errors_still_raise(self) -> None:
        verifier = module._JWTVerificationMixin()

        with patch.object(module.jwt, "get_unverified_header", side_effect=OSError("cache down")):
            with pytest.raises(OSError):
                await verifier.verify_token("header.payload.sig")
