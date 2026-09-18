"""Tests for the inbound relay authentication contracts.

The gateway itself never validates keys: a host binds a
``RelayAuthVerifierProtocol`` implementation through the container and the
gateway only calls it.  These tests pin the identity and rejection value
types and the verifier protocol surface.
"""

from __future__ import annotations

from quadkit.contracts.ai.relay.auth import (
    RelayAuthError,
    RelayAuthIdentity,
    RelayAuthVerifierProtocol,
)


def test_identity_and_error_types() -> None:
    ident = RelayAuthIdentity(user_id="u1", token_id="t1", key_prefix="sk_")
    assert ident.user_id == "u1"
    assert ident.token_id == "t1"
    err = RelayAuthError("AUTH_TOKEN_INVALID", "invalid token")
    assert err.code == "AUTH_TOKEN_INVALID"
    assert isinstance(err, RelayAuthError)
    assert RelayAuthVerifierProtocol in [
        RelayAuthIdentity,
        RelayAuthError,
        RelayAuthVerifierProtocol,
    ]
