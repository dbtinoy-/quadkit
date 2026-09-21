"""Convention followed: **Service pattern** — domain logic behind a service
class, returning ``Result[T, E]`` for expected failures; no HTTP knowledge
lives here.

Token issue/verify for the Auth Tokens demo. The scheme
(``base64url(payload).base64url(mac)``) is deliberately small so the whole
flow stays readable — swap ``TokenService.verify`` for your JWT/IdP
integration in production.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any

from starlette.requests import Request

from quadkit.contracts.exceptions import AuthenticationError
from quadkit.result import Err, Ok, Result
from quadkit.serialization import dumps_str, loads


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class TokenService:
    """Issues and verifies HMAC-signed bearer tokens."""

    def __init__(self, secret: str) -> None:
        self._key = secret.encode()

    def issue(self, subject: str, roles: list[str]) -> str:
        """Return a signed token for ``subject`` with ``roles``."""
        payload = _b64(dumps_str({"sub": subject, "roles": roles}).encode())
        mac = _b64(hmac.new(self._key, payload.encode(), hashlib.sha256).digest())
        return f"{payload}.{mac}"

    def verify(self, token: str) -> Result[dict[str, Any], AuthenticationError]:
        """Return ``Ok(claims)`` for a valid token, else ``Err``."""
        try:
            payload, mac = token.split(".", 1)
        except ValueError:
            return Err(AuthenticationError("malformed bearer token"))
        expected = _b64(hmac.new(self._key, payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(mac, expected):
            return Err(AuthenticationError("invalid bearer token signature"))
        padded = payload + "=" * (-len(payload) % 4)
        return Ok(loads(base64.urlsafe_b64decode(padded.encode())))

    def require(self, request: Request) -> Result[dict[str, Any], AuthenticationError]:
        """Return the claims of the request's valid bearer token, else ``Err``."""
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return Err(AuthenticationError("missing bearer token"))
        return self.verify(token)


# Demo credentials for the template — load from your user store in real apps.
USERS: dict[str, dict[str, Any]] = {
    "ada": {"password": "wonderland", "roles": ["admin"]},
    "grace": {"password": "compiler", "roles": ["reader"]},
}


__all__ = ["USERS", "TokenService"]
