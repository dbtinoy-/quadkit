"""Tests for RFC 6238 TOTP test vectors."""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct

from quadkit.auth.mfa.totp_vectors import (
    TOTPTestVector,
    TOTPTestVectors,
    generate_test_vector,
)

_ALGOS = {"SHA1": hashlib.sha1, "SHA256": hashlib.sha256, "SHA512": hashlib.sha512}


def _real_totp(vector: TOTPTestVector) -> str:
    """Compute the TOTP per RFC 6238 to validate the vector data."""
    key = base64.b32decode(vector.secret.upper())
    counter = int(vector.time // vector.time_step)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, _ALGOS[vector.algorithm]).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % 10**vector.digits).zfill(vector.digits)


class TestVectors:
    def test_all_vectors_are_rfc6238_valid(self) -> None:
        vectors = TOTPTestVectors.get_all()
        assert len(vectors) == 8
        for v in vectors:
            assert _real_totp(v) == v.expected_otp, f"vector {v.algorithm}/{v.digits} mismatch"

    def test_sha1_8digit_vectors(self) -> None:
        assert TOTPTestVectors.SHA1_8DIGITS_1.time == 59
        assert TOTPTestVectors.SHA1_8DIGITS_1.expected_otp == "94287082"
        assert TOTPTestVectors.SHA1_8DIGITS_2.expected_otp == "07081804"
        assert TOTPTestVectors.SHA1_8DIGITS_3.expected_otp == "14050471"
        assert TOTPTestVectors.SHA1_8DIGITS_4.time == 1234567890
        assert TOTPTestVectors.SHA1_8DIGITS_4.expected_otp == "89005924"

    def test_sha256_and_sha512(self) -> None:
        assert TOTPTestVectors.SHA256_8DIGITS_1.expected_otp == "46119246"
        assert TOTPTestVectors.SHA512_8DIGITS_1.expected_otp == "90693936"

    def test_digit_variants(self) -> None:
        assert len(TOTPTestVectors.SHA1_7DIGITS_1.expected_otp) == 7
        assert TOTPTestVectors.SHA1_7DIGITS_1.expected_otp == "4287082"
        assert TOTPTestVectors.SHA1_6DIGITS_1.expected_otp == "287082"

    def test_vector_frozen(self) -> None:
        import dataclasses

        v = TOTPTestVectors.SHA1_8DIGITS_1
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.time = 0  # type: ignore[misc]


import pytest  # noqa: E402


class TestSelection:
    def test_get_by_algorithm_case_insensitive(self) -> None:
        assert len(TOTPTestVectors.get_by_algorithm("sha1")) == 6
        assert len(TOTPTestVectors.get_by_algorithm("SHA256")) == 1
        assert TOTPTestVectors.get_by_algorithm("SHA512")[0].algorithm == "SHA512"

    def test_get_by_digits(self) -> None:
        assert len(TOTPTestVectors.get_by_digits(8)) == 6
        assert len(TOTPTestVectors.get_by_digits(7)) == 1
        assert len(TOTPTestVectors.get_by_digits(6)) == 1

    def test_unknown_algorithm_empty(self) -> None:
        assert TOTPTestVectors.get_by_algorithm("MD5") == []


class TestGenerateTestVector:
    def test_returns_six_zero_digits(self) -> None:
        assert generate_test_vector("SECRET", 59) == "000000"

    def test_defaults(self) -> None:
        assert (
            generate_test_vector("SECRET", 59, time_step=30, digits=6, algorithm="SHA1")
            == "000000"
        )

    def test_all_exports(self) -> None:
        from quadkit.auth.mfa import totp_vectors

        assert totp_vectors.__all__ == [
            "TOTPTestVector",
            "TOTPTestVectors",
            "generate_test_vector",
        ]
