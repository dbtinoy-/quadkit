"""Strict WebAuthn registration attestation parsing for QuadKit Auth.

The passkey service keeps application-specific persistence out of this module.
This module owns the browser ceremony boundary: client-data binding, RP ID
hash validation, authenticator flags/counter extraction, COSE EC public-key
conversion, and the attestation formats that QuadKit can verify without a
platform trust store.

The parser intentionally supports the formats that can be verified locally and
fails closed for formats requiring a configured attestation trust policy:
``none`` and packed self-attestation are accepted; packed certificate,
Android, TPM, and FIDO U2F statements are rejected rather than being recorded
as if they were trusted.  A later trust-store provider can extend this contract
without weakening the existing boundary.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import hmac
from typing import Any
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from quadkit import serialization as json


class AttestationError(ValueError):
    """Raised when a browser registration response is not safe to persist."""


@dataclass(frozen=True)
class ParsedAttestation:
    """Validated data extracted from a WebAuthn attestation object."""

    credential_id: str
    public_key_pem: str
    aaguid: str
    sign_count: int
    attestation_format: str
    user_present: bool
    user_verified: bool
    backup_eligible: bool
    backup_state: bool


def _decode_base64url(value: Any, *, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise AttestationError(f"{field} is required")
    try:
        # urlsafe_b64decode accepts the standard alphabet too, but padding is
        # normalized so browser raw/base64url encodings share one path.
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError, binascii.Error) as exc:
        raise AttestationError(f"{field} is not valid base64url") from exc


def _canonical_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _normalize_challenge(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise AttestationError("clientDataJSON challenge is missing")
    return value.replace("+", "-").replace("/", "_").rstrip("=")


class _CBORDecoder:
    """Small, bounded CBOR decoder for WebAuthn's fixed registration maps.

    WebAuthn uses CBOR for the attestation object and COSE key.  Keeping the
    decoder bounded and local avoids making a full general-purpose serializer a
    security dependency of the authentication boundary.
    """

    _MAX_DEPTH = 16
    _MAX_ITEMS = 256
    _MAX_BYTES = 2 * 1024 * 1024

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    def _read(self, count: int) -> bytes:
        if (
            count < 0
            or count > self._MAX_BYTES
            or self._offset + count > len(self._data)
        ):
            raise AttestationError("truncated CBOR value")
        value = self._data[self._offset : self._offset + count]
        self._offset += count
        return value

    def _head(self) -> tuple[int, int]:
        first = self._read(1)[0]
        major = first >> 5
        additional = first & 0x1F
        if additional < 24:
            return major, additional
        if additional == 24:
            return major, int.from_bytes(self._read(1), "big")
        if additional == 25:
            return major, int.from_bytes(self._read(2), "big")
        if additional == 26:
            return major, int.from_bytes(self._read(4), "big")
        if additional == 27:
            return major, int.from_bytes(self._read(8), "big")
        # 31 is an indefinite-length item; 28-30 are reserved.  Neither is
        # needed for WebAuthn and accepting them makes bounds/duplicate checks
        # needlessly ambiguous.
        raise AttestationError("indefinite or reserved CBOR item")

    def _value(self, depth: int) -> Any:
        if depth > self._MAX_DEPTH:
            raise AttestationError("CBOR nesting is too deep")
        major, length = self._head()
        if major == 0:
            return length
        if major == 1:
            return -1 - length
        if major == 2:
            if length > self._MAX_BYTES:
                raise AttestationError("CBOR byte string is too large")
            return self._read(length)
        if major == 3:
            if length > self._MAX_BYTES:
                raise AttestationError("CBOR text string is too large")
            try:
                return self._read(length).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise AttestationError("CBOR text string is not UTF-8") from exc
        if major == 4:
            if length > self._MAX_ITEMS:
                raise AttestationError("CBOR array is too large")
            return [self._value(depth + 1) for _ in range(length)]
        if major == 5:
            if length > self._MAX_ITEMS:
                raise AttestationError("CBOR map is too large")
            result: dict[Any, Any] = {}
            for _ in range(length):
                key = self._value(depth + 1)
                try:
                    if key in result:
                        raise AttestationError("CBOR map contains duplicate keys")
                except TypeError as exc:
                    raise AttestationError("CBOR map key is not hashable") from exc
                result[key] = self._value(depth + 1)
            return result
        if major == 6:
            raise AttestationError("CBOR tags are not accepted in WebAuthn data")
        if major == 7:
            if length == 20:
                return False
            if length == 21:
                return True
            if length == 22:
                return None
        raise AttestationError("unsupported CBOR value")

    def one(self) -> Any:
        return self._value(0)

    @property
    def remaining(self) -> bytes:
        return self._data[self._offset :]


def _decode_cbor(data: bytes, *, allow_trailing: bool = False) -> Any:
    decoder = _CBORDecoder(data)
    value = decoder.one()
    if decoder.remaining and not allow_trailing:
        raise AttestationError("trailing CBOR data")
    return value


def _verify_attestation_statement(
    fmt: Any,
    att_stmt: Any,
    *,
    auth_data: bytes,
    client_data_json: bytes,
    public_key_pem: str,
) -> str:
    if not isinstance(fmt, str) or not isinstance(att_stmt, dict):
        raise AttestationError("attestation format is invalid")
    if fmt == "none":
        if att_stmt:
            raise AttestationError("none attestation must not contain a statement")
        return "none"
    if fmt != "packed":
        raise AttestationError(f"unsupported attestation format: {fmt}")

    # A packed certificate chain needs an operator-configured trust store. Do
    # not accept a certificate merely because its signature verifies.
    if att_stmt.get("x5c") is not None or att_stmt.get("ecdaaKeyId") is not None:
        raise AttestationError("packed certificate attestation is not configured")
    if att_stmt.get("alg") != -7 or not isinstance(att_stmt.get("sig"), bytes):
        raise AttestationError("only packed ES256 self-attestation is supported")
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        # ``alg == -7`` says ES256, but say it in the type system too: a
        # non-EC key handed to ``verify`` with an ECDSA algorithm is a
        # mismatch, and the isinstance check is what makes it fail closed
        # here instead of inside the verification call.
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise AttestationError("packed ES256 attestation requires an EC public key")
        public_key.verify(
            att_stmt["sig"],
            auth_data + hashlib.sha256(client_data_json).digest(),
            ec.ECDSA(hashes.SHA256()),
        )
    except (ValueError, TypeError) as exc:
        raise AttestationError("packed attestation signature is invalid") from exc
    return "packed"


def parse_registration_attestation(
    attestation_object: bytes,
    client_data_json: bytes,
    *,
    expected_challenge: str,
    expected_rp_id: str | None = None,
    origin: str | None = None,
    allowed_origins: set[str] | frozenset[str] | None = None,
    require_user_verification: bool = True,
    allow_insecure_origins: bool = False,
    supplied_credential_id: str | None = None,
) -> ParsedAttestation:
    """Validate a browser registration response and extract its credential.

    ``origin`` is an optional server-observed value.  When supplied it must
    match the signed client data; when ``allowed_origins`` is configured the
    signed origin is always required to be an exact member of that set.
    """
    if not isinstance(attestation_object, bytes) or not attestation_object:
        raise AttestationError("attestationObject is required")
    if not isinstance(client_data_json, bytes) or not client_data_json:
        raise AttestationError("clientDataJSON is required")
    try:
        client_data = json.loads(client_data_json)
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise AttestationError("clientDataJSON is invalid") from exc
    if (
        not isinstance(client_data, dict)
        or client_data.get("type") != "webauthn.create"
    ):
        raise AttestationError("clientDataJSON type is invalid")
    client_origin = client_data.get("origin")
    if not isinstance(client_origin, str) or not client_origin:
        raise AttestationError("clientDataJSON origin is missing")
    if origin is not None and client_origin != origin:
        raise AttestationError("clientDataJSON origin does not match request origin")
    if allowed_origins and client_origin not in allowed_origins:
        raise AttestationError("clientDataJSON origin is not allowed")
    if not hmac.compare_digest(
        _normalize_challenge(client_data.get("challenge")),
        _normalize_challenge(expected_challenge),
    ):
        raise AttestationError("clientDataJSON challenge does not match")

    parsed_origin = urlparse(client_origin)
    if (
        parsed_origin.username
        or parsed_origin.password
        or parsed_origin.path not in {"", "/"}
        or parsed_origin.query
        or parsed_origin.fragment
    ):
        raise AttestationError("clientDataJSON origin is not a valid origin")
    local_http = parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed_origin.scheme != "https" and not (allow_insecure_origins or local_http):
        raise AttestationError("passkey registration requires HTTPS")
    derived_rp_id = (parsed_origin.hostname or "").lower().rstrip(".")
    rp_id = str(expected_rp_id or derived_rp_id).strip().lower().rstrip(".")
    if not rp_id or parsed_origin.scheme not in {"https", "http"}:
        raise AttestationError("a valid RP ID cannot be derived")
    if derived_rp_id != rp_id and not derived_rp_id.endswith(f".{rp_id}"):
        raise AttestationError("clientDataJSON origin is outside the RP ID")

    attestation = _decode_cbor(attestation_object)
    if not isinstance(attestation, dict):
        raise AttestationError("attestationObject is not a CBOR map")
    auth_data = attestation.get("authData")
    if not isinstance(auth_data, bytes) or len(auth_data) < 37:
        raise AttestationError("attestation authData is truncated")
    rp_hash = hashlib.sha256(rp_id.encode("utf-8")).digest()
    if not hmac.compare_digest(auth_data[:32], rp_hash):
        raise AttestationError("attestation RP ID hash does not match")

    flags = auth_data[32]
    user_present = bool(flags & 0x01)
    user_verified = bool(flags & 0x04)
    if not user_present:
        raise AttestationError("authenticator did not assert user presence")
    if require_user_verification and not user_verified:
        raise AttestationError("authenticator did not verify the user")
    if not flags & 0x40:
        raise AttestationError("attestation does not contain a credential")

    sign_count = int.from_bytes(auth_data[33:37], "big")
    offset = 37
    if len(auth_data) < offset + 18:
        raise AttestationError("attested credential data is truncated")
    aaguid = auth_data[offset : offset + 16]
    offset += 16
    credential_length = int.from_bytes(auth_data[offset : offset + 2], "big")
    offset += 2
    if (
        credential_length < 1
        or credential_length > 1024
        or len(auth_data) < offset + credential_length
    ):
        raise AttestationError("credential id is invalid")
    credential_bytes = auth_data[offset : offset + credential_length]
    offset += credential_length
    public_key_decoder = _CBORDecoder(auth_data[offset:])
    public_key_value = public_key_decoder.one()
    if flags & 0x80:
        # Extension data is allowed only as a complete CBOR value.  We do not
        # currently persist extension outputs, but parsing it prevents hidden
        # trailing bytes from being accepted as part of a credential key.
        _decode_cbor(public_key_decoder.remaining)
    elif public_key_decoder.remaining:
        raise AttestationError("unexpected trailing attestation data")
    if not isinstance(public_key_value, dict):
        raise AttestationError("credential public key is invalid")
    # Re-encode is intentionally avoided: parse the exact map from authData by
    # using the decoder's bounded value result and validate the same fields.
    cose_key = public_key_value
    if cose_key.get(1) != 2 or cose_key.get(3) != -7 or cose_key.get(-1) != 1:
        raise AttestationError("only P-256 ES256 passkeys are supported")
    x = cose_key.get(-2)
    y = cose_key.get(-3)
    if (
        not isinstance(x, bytes)
        or not isinstance(y, bytes)
        or len(x) != 32
        or len(y) != 32
    ):
        raise AttestationError("COSE P-256 coordinates are invalid")
    try:
        public_key = ec.EllipticCurvePublicNumbers(
            int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
        ).public_key()
        public_key_pem = public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
    except (ValueError, TypeError) as exc:
        raise AttestationError("COSE public key is not a valid P-256 point") from exc

    credential_id = _canonical_base64url(credential_bytes)
    if supplied_credential_id:
        supplied = _decode_base64url(supplied_credential_id, field="credential id")
        if not hmac.compare_digest(supplied, credential_bytes):
            raise AttestationError("credential id does not match attestation")
    attestation_format = _verify_attestation_statement(
        attestation.get("fmt"),
        attestation.get("attStmt"),
        auth_data=auth_data,
        client_data_json=client_data_json,
        public_key_pem=public_key_pem,
    )
    return ParsedAttestation(
        credential_id=credential_id,
        public_key_pem=public_key_pem,
        aaguid=_canonical_base64url(aaguid),
        sign_count=sign_count,
        attestation_format=attestation_format,
        user_present=user_present,
        user_verified=user_verified,
        backup_eligible=bool(flags & 0x08),
        backup_state=bool(flags & 0x10),
    )


__all__ = ["AttestationError", "ParsedAttestation", "parse_registration_attestation"]
