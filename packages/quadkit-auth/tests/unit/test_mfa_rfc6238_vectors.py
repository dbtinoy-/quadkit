"""RFC 6238 Appendix B TOTP test vectors.

These tests validate the HOTP/TOTP implementation in
:mod:`quadkit.auth.authn.mfa` against the official test vectors
specified in RFC 6238 Appendix B.

The test key is the 20-byte ASCII string ``12345678901234567890``
(base32-encoded: ``GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ``), which is the
standard vector key used throughout RFC 6238 and RFC 4226.

All vectors use SHA-1 (the algorithm implemented by :func:`_hotp`) with
an 8-digit output and a 30-second time step.

References:
    * RFC 6238 – TOTP: Time-Based One-Time Password Algorithm
      https://tools.ietf.org/html/rfc6238
    * RFC 4226 – HOTP: An HMAC-Based One-Time Password Algorithm
      https://tools.ietf.org/html/rfc4226
"""

from __future__ import annotations

import pytest

from quadkit.auth.authn.mfa import _hotp, generate_totp_code

# Base32 encoding of the 20-byte RFC 6238 test key ``12345678901234567890``.
_RFC6238_SHA1_KEY = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"

# ---------------------------------------------------------------------------
# Section 1: HOTP counter-based vectors (RFC 4226 §B, truncated to 8 digits)
# ---------------------------------------------------------------------------
# These vectors exercise _hotp() directly at the HMAC-otp level and can be
# verified independently of the clock.  The expected values are taken from
# RFC 4226 Appendix D extended to 8 digits via the same truncation algorithm.
#
# RFC 6238 uses the same underlying HOTP primitive, so these also implicitly
# validate the time-based path.

_HOTP_COUNTER_VECTORS: list[tuple[int, str]] = [
    (0, "755224"),
    (1, "287082"),
    (2, "359152"),
    (3, "969429"),
    (4, "338314"),
    (5, "254676"),
    (6, "287922"),
    (7, "162583"),
    (8, "399871"),
    (9, "520489"),
]


class TestHOTPCounterVectors:
    """Validate _hotp() against RFC 4226 Appendix D counter vectors."""

    @pytest.mark.parametrize(("counter", "expected"), _HOTP_COUNTER_VECTORS)
    def test_hotp_counter_vector(self, counter: int, expected: str) -> None:
        """_hotp() must produce the RFC 4226 expected OTP for each counter."""
        digits = len(expected)
        result = _hotp(_RFC6238_SHA1_KEY, counter, digits=digits)
        assert result == expected, (
            f"HOTP counter={counter}: expected {expected!r}, got {result!r}"
        )


# ---------------------------------------------------------------------------
# Section 2: TOTP time-based vectors (RFC 6238 Appendix B, SHA-1, 8 digits)
# ---------------------------------------------------------------------------
# Each tuple is (unix_timestamp, expected_8_digit_otp).
# The time-step is 30 seconds (T0 = 0), so counter = unix_timestamp // 30.

_RFC6238_TOTP_VECTORS: list[tuple[int, str]] = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


class TestTOTPRFC6238Vectors:
    """Validate generate_totp_code() against RFC 6238 Appendix B test vectors.

    All vectors use SHA-1 and 8-digit output with a 30-second time step.
    """

    @pytest.mark.parametrize(("timestamp", "expected"), _RFC6238_TOTP_VECTORS)
    def test_totp_rfc6238_vector(self, timestamp: int, expected: str) -> None:
        """generate_totp_code() must produce the expected OTP at the RFC timestamp."""
        result = generate_totp_code(_RFC6238_SHA1_KEY, for_time=timestamp, digits=8)
        assert result == expected, (
            f"TOTP t={timestamp}: expected {expected!r}, got {result!r}"
        )

    def test_totp_default_is_6_digits(self) -> None:
        """Default output length must remain 6 digits as per the constants module."""
        from quadkit.auth.authn.mfa import DEFAULT_TOTP_DIGITS

        assert DEFAULT_TOTP_DIGITS == 6

        code = generate_totp_code(_RFC6238_SHA1_KEY, for_time=59)
        assert len(code) == 6

    def test_totp_t0_counter_semantics(self) -> None:
        """Counter must equal unix_timestamp // time_step (T0 = 0, step = 30)."""
        # At T=59, counter = 59 // 30 = 1
        # Corresponds to HOTP(key, 1) with 8 digits → "94287082"
        counter_at_59 = 59 // 30
        assert counter_at_59 == 1

        direct = _hotp(_RFC6238_SHA1_KEY, counter_at_59, digits=8)
        via_totp = generate_totp_code(_RFC6238_SHA1_KEY, for_time=59, digits=8)
        assert direct == via_totp == "94287082"
