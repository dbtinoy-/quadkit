"""Unit tests for ``quadkit.security.HmacSigner``."""

from __future__ import annotations

import pytest

from quadkit.security import HmacSigner, SecretValue, SecurityError


def test_hmac_signer_sign_and_verify_round_trip() -> None:
    signer = HmacSigner("test-secret-key-min-32-characters-long", digest_chars=32)
    sig = signer.sign("cursor:page=2")
    assert len(sig) == 32
    assert signer.verify("cursor:page=2", sig) is True
    assert signer.verify("cursor:page=3", sig) is False


def test_hmac_signer_accepts_secret_value() -> None:
    secret = SecretValue("secret-value-key-min-32-characters-long")
    signer = HmacSigner(secret)
    token = signer.pack({"seed": "abc-123", "page": 4})
    assert signer.unpack(token) == {"seed": "abc-123", "page": 4}


def test_hmac_signer_rejects_tampered_signature_or_payload() -> None:
    signer = HmacSigner("test-secret-key-min-32-characters-long")
    token = signer.pack({"page": 1})
    tampered = token[:-2] + ("00" if not token.endswith("00") else "ff")
    with pytest.raises(SecurityError, match="Signature mismatch"):
        signer.unpack(tampered)

    other = HmacSigner("different-secret-key-min-32-chars-long")
    with pytest.raises(SecurityError, match="Signature mismatch"):
        other.unpack(token)


def test_hmac_signer_validates_constructor_parameters() -> None:
    with pytest.raises(SecurityError, match="must not be empty"):
        HmacSigner("")
    with pytest.raises(ValueError, match="between 16 and 64"):
        HmacSigner("valid-secret", digest_chars=8)
