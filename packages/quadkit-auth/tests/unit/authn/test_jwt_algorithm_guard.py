"""Tests for the JWT algorithm guard in JWTTokenManager.

The manager passes its configured ``algorithm`` straight into PyJWT's
``algorithms`` allow-list at verify time. Without a guard,
``algorithm="none"`` would accept unsigned tokens (signature bypass) and
typos would fail opaquely at decode time.
"""

from __future__ import annotations

import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.validation import SecretStr

_SECRET = "test-secret-key-that-is-long-enough"


class TestAlgorithmGuard:
    @pytest.mark.parametrize("bad", ["none", "None", "NONE"])
    def test_unsigned_algorithm_rejected(self, bad: str) -> None:
        with pytest.raises(ConfigurationError, match="unsigned"):
            JWTTokenManager(SecretStr(_SECRET), algorithm=bad)

    @pytest.mark.parametrize("bad", ["BOGUS123", "HS256 ", "hs256"])
    def test_unknown_algorithm_rejected(self, bad: str) -> None:
        with pytest.raises(ConfigurationError, match="Unsupported JWT algorithm"):
            JWTTokenManager(SecretStr(_SECRET), algorithm=bad)

    @pytest.mark.parametrize("good", ["HS256", "RS256", "ES256"])
    def test_supported_algorithms_accepted(self, good: str) -> None:
        manager = JWTTokenManager(SecretStr(_SECRET), algorithm=good)
        assert manager.algorithm == good
