"""Convention followed: **Controller pattern** — stateless HTTP adapters; services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

JSON API for the API-keys console — management + machine endpoint.

Handlers return ``Result`` values; the web pipeline renders ``Ok`` payloads
and maps ``Err`` errors to ProblemDetail responses automatically.
"""
# Controller pattern — each handler returns Result[T, E].
# The web pipeline renders Ok payloads as JSON and maps Err to
# ProblemDetail responses. Error types determine HTTP status codes.

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from quadkit.auth import (
    AuthenticationService,
    SessionCookieBackend,
)
from quadkit.auth.authn.apikeys import APIKeyManager
from quadkit.auth.exceptions import AccountLockedError, InvalidCredentialsError
from quadkit.contracts.exceptions import (
    AuthenticationError,
    NotFoundError,
)
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result
from quadkit.serialization import loads as json_loads
from quadkit.web import Controller, JSONResponse, get, post

logger = get_logger(__name__)


class KeysApiController(Controller):
    """Session-guarded key management + X-API-Key machine endpoint."""

    def __init__(
        self,
        authentication: AuthenticationService,
        cookies: SessionCookieBackend,
        manager: APIKeyManager,
    ) -> None:
        # Constructor injection — all dependencies are
        # explicit typed parameters. The provider wires these in boot().
        self._authentication = authentication
        self._cookies = cookies
        self._manager = manager

    async def _require_session(self, request: Request) -> Any | None:
        return await self._cookies.authenticate(request)

    @post("/api/login")
    async def login(
        self,
        request: Request,
    ) -> Result[JSONResponse, InvalidCredentialsError | AccountLockedError]:
        # Result return type — error variants are unioned
        # so the web pipeline can map each to the right HTTP status.
        data = json_loads(await request.body())
        user = await self._authentication.authenticate_user(
            email=str(data.get("email", "")),
            password=str(data.get("password", "")),
        )
        if user.is_err():
            return Err(user.unwrap_err())
        authenticated = user.unwrap()
        response = JSONResponse({"ok": True, "user": {"email": authenticated.email}})
        await self._cookies.login(response, authenticated.user_id)
        return Ok(response)

    @post("/api/logout")
    async def logout(self, request: Request) -> JSONResponse:
        response = JSONResponse({"ok": True})
        await self._cookies.logout(request, response)
        return response

    @get("/api/keys")
    async def list_keys(
        self,
        request: Request,
    ) -> Result[dict, AuthenticationError]:
        user = await self._require_session(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))
        keys = await self._manager.list_keys(user.user_id)
        return Ok(
            {
                "keys": [
                    {
                        "key_id": k.key_id,
                        "name": k.name,
                        "prefix": k.prefix,
                        "scopes": list(k.scopes),
                        "expires_at": k.expires_at.isoformat()
                        if k.expires_at
                        else None,
                    }
                    for k in keys
                ]
            }
        )

    @post("/api/keys/create", status_code=201)
    async def create_key(
        self,
        request: Request,
    ) -> Result[dict, AuthenticationError]:
        """Issue a key; the raw secret appears exactly once in this response."""
        user = await self._require_session(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))
        data = json_loads(await request.body())
        raw_key, api_key = await self._manager.create_key(
            user_id=user.user_id,
            name=str(data.get("name", "unnamed")),
            scopes=list(data.get("scopes") or ["read"]),
            expires_days=None,
        )
        logger.info("api_key_created", key_id=api_key.key_id, prefix=api_key.prefix)
        return Ok(
            {"raw_key": raw_key, "key_id": api_key.key_id, "prefix": api_key.prefix}
        )

    @post("/api/keys/{key_id}/revoke")
    async def revoke_key(
        self,
        request: Request,
        key_id: str,
    ) -> Result[dict, NotFoundError]:
        revoked = await self._manager.revoke_key(key_id)
        if not revoked:
            return Err(NotFoundError(f"unknown key {key_id!r}"))
        return Ok({"ok": True})

    @get("/api/me")
    async def me(self, request: Request) -> Result[dict, AuthenticationError]:
        """Machine authentication via ``X-API-Key`` header."""
        # Machine auth via X-API-Key header — validates
        # the raw key against the repository. No session cookies needed.
        raw_key = request.headers.get("X-API-Key", "")
        if not raw_key:
            return Err(AuthenticationError("missing X-API-Key header"))
        api_key = await self._manager.validate_key(raw_key)
        if api_key is None:
            return Err(AuthenticationError("invalid api key"))
        return Ok(
            {
                "user_id": api_key.user_id,
                "name": api_key.name,
                "scopes": list(api_key.scopes),
            }
        )


__all__ = ["KeysApiController"]
