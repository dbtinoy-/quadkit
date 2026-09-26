"""Convention followed: **Controller pattern** — stateless HTTP adapters; services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

JSON API for the auth web demo — no HTML lives here.

Handlers return ``Result`` values; the web pipeline renders ``Ok`` payloads
and maps ``Err`` errors to ProblemDetail responses automatically.
"""

from __future__ import annotations

from typing import cast

from starlette.requests import Request

from auth_web.config import AuthWebConfig
from auth_web.services.account_verification import DemoAccountVerificationService
from auth_web.services.password_change import PasswordChangeService
from auth_web.services.password_reset import DemoPasswordResetService
from quadkit.auth import (
    AuthenticationService,
    SessionCookieBackend,
    TokenError,
    User,
)
from quadkit.auth.authn import RegisterRequest
from quadkit.auth.authz import AuthorizationService
from quadkit.auth.exceptions import (
    AccountLockedError,
    AuthenticationError,
    EmailExistsError,
    InvalidCredentialsError,
    PasswordPolicyError,
)
from quadkit.contracts.auth import SessionRepositoryProtocol
from quadkit.logging import get_logger
from quadkit.primitives import clock
from quadkit.result import Err, Ok, Result
from quadkit.serialization import loads as json_loads
from quadkit.web import Controller, JSONResponse, NotFoundError, get, post

logger = get_logger(__name__)


class AuthApiController(Controller):
    """Account lifecycle API consumed by the UI's vanilla-JS client."""

    def __init__(
        self,
        authentication: AuthenticationService,
        cookies: SessionCookieBackend,
        sessions: SessionRepositoryProtocol,
        authz: AuthorizationService,
        password_changes: PasswordChangeService,
        password_resets: DemoPasswordResetService,
        verification: DemoAccountVerificationService,
        config: AuthWebConfig | None = None,
    ) -> None:
        self._authentication = authentication
        self._cookies = cookies
        self._sessions = sessions
        self._authz = authz
        self._password_changes = password_changes
        self._password_resets = password_resets
        self._verification = verification
        self._config = config or AuthWebConfig()

    @post("/api/register")
    async def register(
        self,
        request: Request,
    ) -> Result[JSONResponse, EmailExistsError | PasswordPolicyError]:
        """Create an account and start a session for it.

        If ``auto_send_verification`` is enabled in config, a verification
        token is returned in the response (simulated email delivery).
        """
        data = json_loads(await request.body())
        try:
            req = RegisterRequest(
                name=str(data.get("name", "")),
                email=str(data.get("email", "")),
                password=str(data.get("password", "")),
                confirm_password=str(data.get("confirm_password", "")),
            )
        except ValueError as e:
            return Err(PasswordPolicyError(str(e)))

        result = await self._authentication.register_user(req)
        if result.is_err():
            return Err(result.unwrap_err())

        user = result.unwrap()
        body: dict = {"ok": True, "user": {"email": user.email}}

        if self._config.registration.auto_send_verification:
            token_result = await self._verification.send_verification(user.user_id)
            if token_result.is_ok():
                body["verification_token"] = token_result.unwrap()
                logger.info(
                    "auto_verification_sent",
                    user_id=user.user_id,
                )

        response = JSONResponse(body, status_code=201)
        await self._cookies.login(response, user.user_id)
        return Ok(response)

    @post("/api/login")
    async def login(
        self,
        request: Request,
    ) -> Result[JSONResponse, InvalidCredentialsError | AccountLockedError]:
        """Verify credentials and set the session cookie."""
        data = json_loads(await request.body())
        email = str(data.get("email", ""))
        password = str(data.get("password", ""))

        user = await self._authentication.authenticate_user(email, password)
        if user.is_err():
            logger.warning("login_failed", email=email)
            return Err(user.unwrap_err())

        authenticated = user.unwrap()
        response = JSONResponse(
            {
                "ok": True,
                "user": {
                    "user_id": authenticated.user_id,
                    "email": authenticated.email,
                    "name": authenticated.name,
                },
            }
        )
        await self._cookies.login(response, authenticated.user_id)
        return Ok(response)

    @post("/api/logout")
    async def logout(self, request: Request) -> JSONResponse:
        """Invalidate the session cookie."""
        response = JSONResponse({"ok": True})
        await self._cookies.logout(request, response)
        return response

    @get("/api/me")
    async def me(self, request: Request) -> Result[dict, AuthenticationError]:
        """Return the session's identity, or 401 when anonymous."""
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))
        return Ok({"user_id": user.user_id, "email": user.email, "name": user.name})

    @get("/api/profile")
    async def profile(
        self,
        request: Request,
    ) -> Result[dict, AuthenticationError | TokenError]:
        """Identity + fresh JWT claims + active sessions for this user."""
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))

        token = self._authentication.create_token(cast("User", user))
        verified = await self._authentication.verify_token(token.token)
        if verified.is_err():
            return Err(verified.unwrap_err())
        claims = verified.unwrap()

        sessions = await self._sessions.find_active_by_user(
            user.user_id, cutoff=clock.now()
        )

        # Effective permissions = explicit claims UNION role-derived patterns
        # (AuthorizationService expands inheritance for us).
        effective: set[str] = set(claims.permissions)
        for role in claims.roles:
            effective |= self._authz.get_role_permissions(role)

        return Ok(
            {
                "user": {
                    "user_id": user.user_id,
                    "email": user.email,
                    "name": user.name,
                },
                "token_preview": token.token[:24] + "…",
                "claims": {
                    "roles": claims.roles,
                    "permissions": sorted(effective),
                    "key_id": claims.key_id,
                    "expires_at": claims.expires_at.isoformat(),
                    "token_type": claims.token_type,
                },
                "sessions": [
                    {
                        "session_id": row["session_id"],
                        "expires_at": row["expires_at"].isoformat()
                        if row.get("expires_at")
                        else None,
                    }
                    for row in sessions
                ],
            }
        )

    @post("/api/profile/password")
    async def change_password(
        self,
        request: Request,
    ) -> Result[
        dict,
        AuthenticationError | InvalidCredentialsError | PasswordPolicyError,
    ]:
        """Change the session user's password (requires current password)."""
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))

        data = json_loads(await request.body())
        result = await self._password_changes.change(
            user_id=user.user_id,
            current_password=str(data.get("current_password", "")),
            new_password=str(data.get("new_password", "")),
        )
        if result.is_err():
            return Err(result.unwrap_err())
        return Ok({"ok": True})

    @post("/api/sessions/{session_id}/revoke")
    async def revoke_session(
        self,
        request: Request,
        session_id: str,
    ) -> Result[dict, AuthenticationError | NotFoundError]:
        """Revoke one of the session user's active sessions."""
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))

        rows = await self._sessions.find_active_by_user(
            user.user_id, cutoff=clock.now()
        )
        if session_id not in {row["session_id"] for row in rows}:
            return Err(NotFoundError(f"unknown session {session_id!r}"))

        await self._sessions.revoke(session_id)
        return Ok({"ok": True})

    @post("/api/forgot-password")
    async def forgot_password(
        self,
        request: Request,
    ) -> Result[JSONResponse, AuthenticationError]:
        """Request a password reset token for the given email.

        Returns the token directly (simulated email delivery for the demo).
        Always returns 200 to prevent email enumeration.
        """
        data = json_loads(await request.body())
        email = str(data.get("email", ""))

        result = await self._password_resets.request_reset(email)
        if result.is_err():
            # Return 200 even on error to prevent email enumeration.
            return Ok(JSONResponse({"ok": True}))

        return Ok(JSONResponse({"ok": True, "reset_token": result.unwrap()}))

    @post("/api/reset-password")
    async def reset_password(
        self,
        request: Request,
    ) -> Result[JSONResponse, PasswordPolicyError]:
        """Reset a password using a valid reset token."""
        data = json_loads(await request.body())
        token = str(data.get("token", ""))
        new_password = str(data.get("new_password", ""))

        result = await self._password_resets.confirm_reset(token, new_password)
        if result.is_err():
            return Err(PasswordPolicyError(str(result.unwrap_err())))
        return Ok(JSONResponse({"ok": True}))

    @post("/api/verify-email")
    async def verify_email(
        self,
        request: Request,
    ) -> Result[JSONResponse, AuthenticationError]:
        """Verify the session user's email with a verification token."""
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))

        data = json_loads(await request.body())
        token = str(data.get("token", ""))

        result = await self._verification.verify(token)
        if result.is_err():
            return Err(AuthenticationError(str(result.unwrap_err())))
        return Ok(JSONResponse({"ok": True}))

    @post("/api/send-verification")
    async def send_verification(
        self,
        request: Request,
    ) -> Result[JSONResponse, AuthenticationError]:
        """Send a verification email for the session user.

        Returns the token directly (simulated email delivery for the demo).
        """
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))

        result = await self._verification.send_verification(user.user_id)
        if result.is_err():
            return Err(AuthenticationError(str(result.unwrap_err())))
        return Ok(JSONResponse({"ok": True, "verification_token": result.unwrap()}))


__all__ = ["AuthApiController"]
