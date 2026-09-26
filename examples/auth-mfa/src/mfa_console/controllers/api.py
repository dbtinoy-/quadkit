"""Convention followed: **Controller pattern** — stateless HTTP adapters; services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

JSON API for the MFA console — no HTML lives here.

Handlers return ``Result`` values; the web pipeline renders ``Ok`` payloads
and maps ``Err`` errors to ProblemDetail responses automatically.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from starlette.requests import Request

from mfa_console.repository.session_repository import InMemorySessionRepository
from quadkit.auth.authn.services import AuthenticationService
from quadkit.auth.authn.user_service import UserService
from quadkit.auth.config import AuthConfig
from quadkit.auth.exceptions import AccountLockedError, InvalidCredentialsError
from quadkit.auth.mfa.manager import MFAManager
from quadkit.auth.session.cookie_backend import SessionCookieBackend
from quadkit.contracts.exceptions.domain import (
    AuthenticationError,
    ConflictError,
)
from quadkit.logging import get_logger
from quadkit.primitives import clock
from quadkit.result import Err, Ok, Result
from quadkit.serialization import loads as json_loads
from quadkit.web import Controller, JSONResponse, get, post

logger = get_logger(__name__)

PENDING_COOKIE = "mfa_pending"
PENDING_TTL_SECONDS = 300


def _mfa_enabled(user: Any) -> bool:
    profile_mfa = (getattr(user, "profile", {}) or {}).get("mfa") or {}
    return bool(profile_mfa.get("enabled"))


class MfaApiController(Controller):
    """Login + TOTP challenge/enroll/disable API for the demo UI."""

    def __init__(
        self,
        authentication: AuthenticationService,
        users: UserService,
        mfa: MFAManager,
        cookies: SessionCookieBackend,
        sessions: InMemorySessionRepository,
        config: AuthConfig,
    ) -> None:
        self._authentication = authentication
        self._users = users
        self._mfa = mfa
        self._cookies = cookies
        self._sessions = sessions
        self._max_attempts = config.mfa.max_challenge_attempts
        self._attempts: dict[str, int] = {}

    async def _user_from_pending(self, request: Request) -> Any | None:
        pending_id = request.cookies.get(PENDING_COOKIE)
        if not pending_id:
            return None
        row = await self._sessions.find_active(pending_id)
        if row is None:
            return None
        user = await self._users.get_user(row["user_id"])
        if user is None or not _mfa_enabled(user):
            return None
        return user, pending_id, row

    @post("/api/login")
    async def login(
        self,
        request: Request,
    ) -> Result[JSONResponse, InvalidCredentialsError | AccountLockedError]:
        """Password step; MFA-enabled users get a pending challenge cookie."""
        data = json_loads(await request.body())
        email = str(data.get("email", ""))
        password = str(data.get("password", ""))

        result = await self._authentication.authenticate_user(email, password)
        if result.is_err():
            logger.warning("login_failed", email=email)
            return Err(result.unwrap_err())

        user = result.unwrap()
        if not _mfa_enabled(user):
            response = JSONResponse({"ok": True, "mfa_required": False})
            await self._cookies.login(response, user.user_id)
            return Ok(response)

        pending_id = f"pending-{user.user_id}-{clock.now().timestamp()}"
        await self._sessions.insert(
            {
                "session_id": pending_id,
                "user_id": user.user_id,
                "device_id": "pre-auth",
                "expires_at": clock.now() + timedelta(seconds=PENDING_TTL_SECONDS),
            }
        )
        response = JSONResponse({"ok": True, "mfa_required": True})
        response.set_cookie(
            key=PENDING_COOKIE,
            value=pending_id,
            max_age=PENDING_TTL_SECONDS,
            httponly=True,
            samesite="lax",
        )
        logger.info("mfa_challenge_issued", user_id=user.user_id)
        return Ok(response)

    @post("/api/mfa/challenge")
    async def challenge(
        self,
        request: Request,
    ) -> Result[JSONResponse | dict, AuthenticationError]:
        """Verify a TOTP/backup code and upgrade to a full session."""
        resolved = await self._user_from_pending(request)
        if resolved is None:
            return Err(AuthenticationError("no pending challenge"))
        user, pending_id, _row = resolved

        data = json_loads(await request.body())
        code = str(data.get("code", ""))

        if not await self._mfa.verify_totp(user.user_id, code):
            attempts = self._attempts.get(pending_id, 0) + 1
            self._attempts[pending_id] = attempts
            if attempts >= self._max_attempts:
                await self._sessions.revoke(pending_id)
                response = JSONResponse(
                    {"detail": "too many attempts; log in again"}, status_code=401
                )
                response.delete_cookie(PENDING_COOKIE)
                return response
            return Err(AuthenticationError("invalid code"))

        self._attempts.pop(pending_id, None)
        await self._sessions.revoke(pending_id)
        response = JSONResponse({"ok": True})
        await self._cookies.login(response, user.user_id)
        logger.info("mfa_challenge_passed", user_id=user.user_id)
        return Ok(response)

    @get("/api/me")
    async def me(self, request: Request) -> Result[dict, AuthenticationError]:
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))
        return Ok(
            {
                "email": user.email,
                "name": user.name,
                "mfa_enabled": _mfa_enabled(user),
            }
        )

    @get("/api/mfa/status")
    async def mfa_status(self, request: Request) -> Result[dict, AuthenticationError]:
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))
        profile_mfa = (getattr(user, "profile", None) or {}).get("mfa") or {}
        remaining = len(profile_mfa.get("backup_codes") or [])
        return Ok({"enabled": _mfa_enabled(user), "backup_codes_left": remaining})

    @post("/api/mfa/enroll")
    async def enroll(
        self,
        request: Request,
    ) -> Result[dict, AuthenticationError | ConflictError]:
        """Enable TOTP; returns secret + provisioning URI + backup codes once."""
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))
        if _mfa_enabled(user):
            return Err(ConflictError("MFA already enabled"))

        secret, provisioning_uri, backup_codes = await self._mfa.enable_totp(
            user.user_id,
        )
        logger.info("mfa_enrolled", user_id=user.user_id)
        return Ok(
            {
                "secret": secret,
                "provisioning_uri": provisioning_uri,
                "backup_codes": backup_codes,
            }
        )

    @post("/api/mfa/disable")
    async def disable(
        self,
        request: Request,
    ) -> Result[
        dict, AuthenticationError | InvalidCredentialsError | AccountLockedError
    ]:
        """Disable TOTP after re-verifying the password."""
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))

        data = json_loads(await request.body())
        recheck = await self._authentication.authenticate_user(
            user.email, str(data.get("password", ""))
        )
        if recheck.is_err():
            return Err(recheck.unwrap_err())

        disabled = await self._mfa.disable_totp(user.user_id)
        return Ok({"ok": True, "disabled": disabled})


__all__ = ["MfaApiController"]
