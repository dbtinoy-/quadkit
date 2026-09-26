"""Native WebAuthn registration attestation coverage."""

from __future__ import annotations

import base64
import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
import pytest

from quadkit import serialization as json
from quadkit.auth.authn.passkey_attestation import (
    AttestationError,
    _decode_cbor,  # type: ignore[attr-defined]
    parse_registration_attestation,
)
from quadkit.auth.authn.passkeys import PasskeyService


class _User:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.name = "Alice"
        self.email = "alice@example.com"
        self.profile: dict[str, object] = {}


class _Store:
    def __init__(self, user: _User) -> None:
        self.user = user

    async def get_user_by_id(self, user_id: str):
        return self.user if user_id == self.user.user_id else None

    async def update_user(self, user) -> None:
        self.user = user


def _uint(value: int) -> bytes:
    if value < 0:
        return _head(1, -1 - value)
    return _head(0, value)


def _head(major: int, value: int) -> bytes:
    prefix = major << 5
    if value < 24:
        return bytes([prefix | value])
    if value < 256:
        return bytes([prefix | 24, value])
    if value < 65536:
        return bytes([prefix | 25]) + value.to_bytes(2, "big")
    return bytes([prefix | 26]) + value.to_bytes(4, "big")


def _cbor(value: object) -> bytes:
    if isinstance(value, bool):
        return b"\xf5" if value else b"\xf4"
    if value is None:
        return b"\xf6"
    if isinstance(value, int):
        return _uint(value)
    if isinstance(value, bytes):
        return _head(2, len(value)) + value
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return _head(3, len(encoded)) + encoded
    if isinstance(value, list):
        return _head(4, len(value)) + b"".join(_cbor(item) for item in value)
    if isinstance(value, dict):
        return _head(5, len(value)) + b"".join(_cbor(key) + _cbor(item) for key, item in value.items())
    raise TypeError(value)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _native_credential(
    private_key: ec.EllipticCurvePrivateKey,
    challenge: str,
    *,
    rp_id: str = "example.com",
    origin: str = "https://example.com",
    uv: bool = True,
    fmt: str = "none",
    credential_bytes: bytes = b"credential-1",
    sign_count: int = 0,
) -> tuple[bytes, bytes, str]:
    client_data = json.dumps(
        {"type": "webauthn.create", "challenge": challenge.rstrip("="), "origin": origin},
        separators=(",", ":"),
    )
    public_numbers = private_key.public_key().public_numbers()
    flags = 0x41 | (0x04 if uv else 0)
    cose_key = {
        1: 2,
        3: -7,
        -1: 1,
        -2: public_numbers.x.to_bytes(32, "big"),
        -3: public_numbers.y.to_bytes(32, "big"),
    }
    auth_data = (
        hashlib.sha256(rp_id.encode("utf-8")).digest()
        + bytes([flags])
        + sign_count.to_bytes(4, "big")
        + bytes(16)
        + len(credential_bytes).to_bytes(2, "big")
        + credential_bytes
        + _cbor(cose_key)
    )
    att_stmt: dict[object, object] = {}
    if fmt == "packed":
        att_stmt = {
            "alg": -7,
            "sig": private_key.sign(
                auth_data + hashlib.sha256(client_data).digest(),
                ec.ECDSA(hashes.SHA256()),
            ),
        }
    attestation = _cbor({"fmt": fmt, "authData": auth_data, "attStmt": att_stmt})
    return attestation, client_data, _b64(credential_bytes)


@pytest.mark.asyncio
async def test_native_none_attestation_is_bound_and_persisted() -> None:
    user = _User("user-1")
    store = _Store(user)
    service = PasskeyService(store, rp_id="example.com", allowed_origins={"https://example.com"})
    registration_id, challenge = await service.start_registration(user.user_id, origin="https://example.com")
    private_key = ec.generate_private_key(ec.SECP256R1())
    attestation, client_data, credential_id = _native_credential(private_key, challenge)

    assert await service.finish_registration(
        registration_id,
        credential_id,
        actor_user_id=user.user_id,
        origin="https://example.com",
        attestation_object=attestation,
        client_data_json=client_data,
    )
    stored = store.user.profile["passkeys"][0]  # type: ignore[index]
    assert stored["credential_id"] == credential_id
    assert stored["attestation_format"] == "none"
    assert stored["user_verified"] is True
    assert stored["sign_count"] == 0


@pytest.mark.asyncio
async def test_packed_self_attestation_verifies_its_signature() -> None:
    user = _User("user-2")
    store = _Store(user)
    service = PasskeyService(store, rp_id="example.com", allowed_origins={"https://example.com"})
    registration_id, challenge = await service.start_registration(user.user_id, origin="https://example.com")
    private_key = ec.generate_private_key(ec.SECP256R1())
    attestation, client_data, credential_id = _native_credential(private_key, challenge, fmt="packed")

    assert await service.finish_registration(
        registration_id,
        credential_id,
        actor_user_id=user.user_id,
        attestation_object=attestation,
        client_data_json=client_data,
        origin="https://example.com",
    )
    assert store.user.profile["passkeys"][0]["attestation_format"] == "packed"  # type: ignore[index]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("challenge", "challenge"),
        ("origin", "origin"),
        ("rp", "RP ID"),
        ("uv", "verify the user"),
    ],
)
def test_native_attestation_rejects_binding_or_policy_changes(change: str, message: str) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    attestation, client_data, _credential_id = _native_credential(private_key, "expected")
    expected = "different" if change == "challenge" else "expected"
    if change == "origin":
        client_data = client_data.replace(b"https://example.com", b"https://evil.example")
    if change == "rp":
        attestation, client_data, _credential_id = _native_credential(private_key, "expected", rp_id="evil.example")
    if change == "uv":
        attestation, client_data, _credential_id = _native_credential(private_key, "expected", uv=False)
    with pytest.raises(AttestationError, match=message):
        parse_registration_attestation(
            attestation,
            client_data,
            expected_challenge=expected,
            expected_rp_id="example.com",
            origin="https://example.com",
            allowed_origins={"https://example.com"},
        )


def test_packed_certificate_attestation_fails_closed() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    attestation, client_data, _ = _native_credential(private_key, "expected")
    # Rebuild a valid registration object with an unsupported x5c statement.
    # The parser reaches the statement policy only after all signed bindings.
    # A minimal empty certificate is sufficient to exercise the fail-closed
    # branch; it is never parsed or trusted.
    decoded = _decode_cbor(attestation)
    decoded["fmt"] = "packed"
    decoded["attStmt"] = {"alg": -7, "sig": b"invalid", "x5c": [b"not-a-certificate"]}
    with pytest.raises(AttestationError, match="not configured"):
        parse_registration_attestation(
            _cbor(decoded),
            client_data,
            expected_challenge="expected",
            expected_rp_id="example.com",
            origin="https://example.com",
            allowed_origins={"https://example.com"},
        )
