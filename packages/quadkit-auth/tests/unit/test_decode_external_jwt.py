"""Unit tests for decode_external_jwt in quadkit.auth.authn.jwt."""

from __future__ import annotations

from datetime import UTC, datetime

import jwt as pyjwt

from quadkit.auth.authn.jwt import decode_external_jwt
from quadkit.primitives import clock
from quadkit.validation import SecretStr

_SECRET = "nextauth-shared-secret-at-least-32-bytes!!"


class _FixedClock:
    def __init__(self, instant: datetime) -> None:
        self._instant = instant

    def now(self) -> datetime:
        return self._instant

    def monotonic(self) -> float:
        return 0.0

    def timestamp(self) -> float:
        return self._instant.timestamp()

    def time(self) -> float:
        return self._instant.timestamp()


def test_decode_external_jwt_verifies_hs256_and_ambient_clock_expiry() -> None:
    issued = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
    exp = int(issued.timestamp()) + 60
    token = pyjwt.encode(
        {"sub": "user-123", "email": "pet@example.com", "exp": exp},
        _SECRET,
        algorithm="HS256",
    )

    with clock.use(_FixedClock(issued)):
        ok_res = decode_external_jwt(token, secret=SecretStr(_SECRET))
        assert ok_res.is_ok()
        assert ok_res.unwrap()["sub"] == "user-123"

    expired = datetime.fromtimestamp(exp + 1, tz=UTC)
    with clock.use(_FixedClock(expired)):
        err_res = decode_external_jwt(token, secret=_SECRET)
        assert err_res.is_err()
        assert "expired" in str(err_res.unwrap_err()).lower()


def test_decode_external_jwt_rejects_wrong_secret_and_supports_unverified() -> None:
    token = pyjwt.encode({"sub": "dev-user"}, _SECRET, algorithm="HS256")

    bad = decode_external_jwt(token, secret="wrong-secret-at-least-32-bytes-long!!")
    assert bad.is_err()

    unverified = decode_external_jwt(token, verify_signature=False, verify_exp=False)
    assert unverified.is_ok()
    assert unverified.unwrap()["sub"] == "dev-user"
