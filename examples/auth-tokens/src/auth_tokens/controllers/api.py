"""Convention followed: **Controller pattern** — stateless HTTP adapters;
expected failures are ``Err(domain error)`` values rendered as RFC-9457
``ProblemDetail`` by the Result bridge (``AuthenticationError`` maps to
401 by the framework's built-in table — no custom registration needed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.requests import Request

from auth_tokens.services.tokens import USERS
from quadkit.contracts.exceptions import AuthenticationError
from quadkit.result import Err, Ok, Result
from quadkit.web import Controller, body, get, post

if TYPE_CHECKING:
    from auth_tokens.services.tokens import TokenService


class SessionController(Controller):
    """Token login and a protected ``/me`` route."""

    prefix = "/"

    def __init__(self, tokens: TokenService | None = None) -> None:
        self._tokens = tokens

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe this demo's surface (the hub mounts it at ``/examples/<slug>/``)."""
        return {
            "demo": "auth-tokens",
            "summary": "Opaque bearer tokens: issue, verify, and read /me.",
            "endpoints": ["POST /session", "GET /me"],
        }

    @post("/session", status_code=201)
    async def login(
        self, credentials: dict = body()
    ) -> Result[dict[str, Any], AuthenticationError]:
        """Issue a signed bearer token for valid demo credentials."""
        username = str(credentials.get("username", ""))
        user = USERS.get(username)
        if user is None or user["password"] != credentials.get("password"):
            return Err(AuthenticationError("invalid credentials"))
        token = self._tokens.issue(username, user["roles"])
        return Ok({"token": token, "type": "bearer"})

    @get("/me")
    async def me(self, request: Request) -> Result[dict[str, Any], AuthenticationError]:
        """Return the claims of the authenticated caller."""
        claims = self._tokens.require(request)
        if claims.is_err():
            return claims  # Err(AuthenticationError) → 401 ProblemDetail
        value = claims.unwrap()
        return Ok({"sub": value["sub"], "roles": value["roles"]})


__all__ = ["SessionController"]
