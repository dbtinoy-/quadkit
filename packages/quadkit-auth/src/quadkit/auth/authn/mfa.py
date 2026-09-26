"""MFA utilities - TOTP (RFC 6238) and backup codes

This module implements a small TOTP engine so we don't add a dependency
on `pyotp`. It provides helper functions to generate secrets, provisioning
URIs, verify codes, and to manage one-time backup codes.

MFA data is stored on the `User.profile['mfa']` key to avoid immediate DB
schema changes. The helpers in AuthProvider operate on the `User` object and
use `AuthProvider.user_store.update_user()` to persist changes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from typing import TYPE_CHECKING

from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from collections.abc import Iterable

DEFAULT_TOTP_DIGITS = 6
DEFAULT_TOTP_ALGORITHM = "SHA1"
DEFAULT_TOTP_PERIOD = 30


def _int_to_bytes(i: int) -> bytes:
    return struct.pack(
        ">Q",
        i,
    )


def generate_totp_secret(length: int = 20) -> str:
    """Generate a base32-encoded secret for TOTP.

    Args:
        length: number of random bytes to use before base32-encoding
    Returns:
        Base32 string without padding, upper-case (common otpauth format)
    """
    b = secrets.token_bytes(length)
    s = base64.b32encode(b).decode("ascii")
    return s.strip("=")


def _hotp(secret: str, counter: int, digits: int = DEFAULT_TOTP_DIGITS) -> str:
    key = base64.b32decode(_normalize_base32(secret), casefold=True)
    msg = _int_to_bytes(counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(
        ">I",
        h[offset : offset + 4],
    )[0]
    code = code & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def _normalize_base32(secret: str) -> str:
    """Normalize base32 secret by adding padding if necessary"""
    s = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - (len(s) % 8)) % 8)
    return s + padding


def generate_totp_code(
    secret: str,
    for_time: int | None = None,
    period: int = DEFAULT_TOTP_PERIOD,
    digits: int = DEFAULT_TOTP_DIGITS,
) -> str:
    """Generate TOTP code for given secret and time (unix seconds).

    Args:
        secret: base32 secret
        for_time: unix timestamp; defaults to now
        period: time-step period in seconds
        digits: number of OTP digits (default: DEFAULT_TOTP_DIGITS = 6)

    Returns:
        zero-padded numeric code string
    """
    if for_time is None:
        for_time = int(ambient_clock.timestamp())
    counter = int(for_time // period)
    return _hotp(secret, counter, digits=digits)


def verify_totp(
    secret: str,
    code: str,
    window: int = 1,
    period: int = DEFAULT_TOTP_PERIOD,
) -> bool:
    """Verify a TOTP code allowing a +/- window of time steps."""
    try:
        code = str(code).zfill(DEFAULT_TOTP_DIGITS)
    except (TypeError, ValueError):
        return False

    now = int(ambient_clock.timestamp())
    for w in range(-window, window + 1):
        c = int((now // period) + w)
        if _hotp(secret, c) == code:
            return True
    return False


def get_provisioning_uri(secret: str, username: str, issuer: str) -> str:
    """Return an `otpauth://` provisioning URI suitable for authenticator apps."""
    # Keep it simple; apps expect base32 secret without padding
    label = f"{issuer}:{username}"
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits={DEFAULT_TOTP_DIGITS}&period={DEFAULT_TOTP_PERIOD}"


def generate_backup_codes(count: int = 10, length: int = 8) -> list[str]:
    """Generate a list of human-friendly backup codes (plain strings).

    These are returned to the caller once and should be hashed before storage.
    """
    codes = []
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # exclude confusing chars
    for _ in range(count):
        codes.append("".join(secrets.choice(alphabet) for _ in range(length)))
    return codes


def hash_backup_codes(codes: Iterable[str]) -> list[str]:
    """Return digest hashes for backup codes (store these, compare with digest)."""
    out = []
    for c in codes:
        h = hashlib.sha256(c.encode("utf-8")).hexdigest()
        out.append(h)
    return out


__all__ = [
    "generate_backup_codes",
    "generate_totp_code",
    "generate_totp_secret",
    "get_provisioning_uri",
    "hash_backup_codes",
    "verify_totp",
]
