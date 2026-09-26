"""RFC 6238 TOTP test vectors for testing without pyotp.

These test vectors are from the RFC 6238 specification for Time-based
One-Time Passwords (Appendix B). They can be used to verify TOTP
implementations without requiring the pyotp library.

Keys (per the RFC's reference implementation):

* SHA-1:   ASCII ``"12345678901234567890"`` (20 bytes)
* SHA-256: ``"12345678901234567890123456789012"`` (32 bytes)
* SHA-512: ``"123456789012345678901234567890" * 3 + "1234"`` (64 bytes)

Reference: https://datatracker.ietf.org/doc/html/rfc6238
Reference: https://datatracker.ietf.org/doc/html/rfc6238#appendix-b
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TOTPTestVector:
    """A TOTP test vector from RFC 6238."""

    secret: str
    time_step: int
    digits: int
    algorithm: str
    time: int
    expected_otp: str


class TOTPTestVectors:
    """RFC 6238 test vectors for TOTP verification.

    These vectors can be used to test TOTP implementations without
    relying on external libraries like pyotp.

    Example:
        >>> from quadkit.logging import get_logger
        >>> logger = get_logger(__name__)
        >>> vector = TOTPTestVectors.SHA1_8DIGITS_1
        >>> logger.info("totp_vector", expected_otp=vector.expected_otp)
        >>> # Output: expected_otp: 94287082
    """

    SHA1_8DIGITS_1 = TOTPTestVector(
        secret="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",  # 20-byte RFC key, base32
        time_step=30,
        digits=8,
        algorithm="SHA1",
        time=59,
        expected_otp="94287082",
    )

    SHA1_8DIGITS_2 = TOTPTestVector(
        secret="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",
        time_step=30,
        digits=8,
        algorithm="SHA1",
        time=1111111109,
        expected_otp="07081804",
    )

    SHA1_8DIGITS_3 = TOTPTestVector(
        secret="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",
        time_step=30,
        digits=8,
        algorithm="SHA1",
        time=1111111111,
        expected_otp="14050471",
    )

    SHA1_8DIGITS_4 = TOTPTestVector(
        secret="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",
        time_step=30,
        digits=8,
        algorithm="SHA1",
        time=1234567890,
        expected_otp="89005924",
    )

    SHA256_8DIGITS_1 = TOTPTestVector(
        secret="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZA====",  # 32-byte RFC key
        time_step=30,
        digits=8,
        algorithm="SHA256",
        time=59,
        expected_otp="46119246",
    )

    SHA512_8DIGITS_1 = TOTPTestVector(
        secret="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNA=",  # 64-byte RFC key, base32
        time_step=30,
        digits=8,
        algorithm="SHA512",
        time=59,
        expected_otp="90693936",
    )

    SHA1_7DIGITS_1 = TOTPTestVector(
        secret="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",  # 20-byte RFC key
        time_step=30,
        digits=7,
        algorithm="SHA1",
        time=59,
        expected_otp="4287082",
    )

    SHA1_6DIGITS_1 = TOTPTestVector(
        secret="GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",  # 20-byte RFC key
        time_step=30,
        digits=6,
        algorithm="SHA1",
        time=59,
        expected_otp="287082",
    )

    @classmethod
    def get_all(cls) -> list[TOTPTestVector]:
        """Get all test vectors."""
        return [
            cls.SHA1_8DIGITS_1,
            cls.SHA1_8DIGITS_2,
            cls.SHA1_8DIGITS_3,
            cls.SHA1_8DIGITS_4,
            cls.SHA256_8DIGITS_1,
            cls.SHA512_8DIGITS_1,
            cls.SHA1_7DIGITS_1,
            cls.SHA1_6DIGITS_1,
        ]

    @classmethod
    def get_by_algorithm(cls, algorithm: str) -> list[TOTPTestVector]:
        """Get test vectors by algorithm."""
        return [v for v in cls.get_all() if v.algorithm == algorithm.upper()]

    @classmethod
    def get_by_digits(cls, digits: int) -> list[TOTPTestVector]:
        """Get test vectors by digit count."""
        return [v for v in cls.get_all() if v.digits == digits]


def generate_test_vector(
    secret: str,
    time: int,
    time_step: int = 30,
    digits: int = 6,
    algorithm: str = "SHA1",
) -> str:
    """Generate a TOTP for testing purposes.

    This is a simple implementation that returns a placeholder.
    In production, use pyotp or a proper TOTP library.

    Args:
        secret: The Base32-encoded secret key.
        time: The Unix timestamp.
        time_step: The time step in seconds (default 30).
        digits: Number of digits in the OTP (default 6).
        algorithm: Hash algorithm (SHA1, SHA256, SHA512).

    Returns:
        A generated OTP (placeholder implementation).
    """
    return "000000"


__all__ = [
    "TOTPTestVector",
    "TOTPTestVectors",
    "generate_test_vector",
]
