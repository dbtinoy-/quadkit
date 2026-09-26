"""The authentication endpoints this package serves.

Before this module existed, ``quadkit-auth`` shipped middleware that *exempted*
``/auth/login`` and ``/auth/register`` and a rate limiter that named the same
paths — but no package implemented either route. An application that imported
``AuthModule`` therefore authenticated nothing and refused everything: every
guarded controller answered ``401 Authentication required`` and no credential
could ever satisfy it, because the endpoint that mints credentials did not
exist.

These two handlers close that loop. They are registered by
:meth:`quadkit.auth.module.AuthModule.configure` (and ``stub``), so any
application that imports the module gets them without naming them — which is
the framework-correct split, as opposed to making the playground generate a
login controller that only generated apps would have.

Deliberately out of scope, and why:

* **No password-change or reset here.** ``/auth/password-reset`` is in the
  rate limiter's list but needs a mail transport, so it stays a consumer's
  concern rather than a route this package half-implements.
* **No refresh route.** ``AuthenticationService.refresh_token`` exists and is
  the right place to expose it; this lands the minimum that makes the guarded
  route reachable, and the refresh route is additive.
* **The store is whatever the consumer wired.** There is no built-in user
  table: ``UserStoreProtocol`` is injected, so an in-memory store is enough
  to boot and a real database drops in behind the same interface.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from starlette.requests import Request

from quadkit.auth import constants as const
from quadkit.auth.authn.schemas.requests import LoginRequest, RegisterRequest
from quadkit.auth.authn.services import AuthenticationService
from quadkit.auth.exceptions import AccountLockedError, InvalidCredentialsError
from quadkit.auth.models.user import User
from quadkit.contracts.web import post
from quadkit.result import Result
from quadkit.web import Controller
from quadkit.web.exceptions import BadRequestError, ConflictError, UnauthorizedError


async def _read_json_object(request: Request) -> dict[str, Any]:
    """Parse the request body as a non-empty JSON object."""
    try:
        data: Any = await request.json()
    except Exception as exc:  # noqa: BLE001 - any parse failure is a bad request
        raise BadRequestError("Invalid JSON body") from exc
    if not isinstance(data, dict) or not data:
        raise BadRequestError("Request body must be a non-empty JSON object")
    return data


class AuthController(Controller):
    """Serves ``/auth/login`` and ``/auth/register``.

    Injected with the :class:`AuthenticationService` the auth bundle provider
    exports, so the handlers add no authentication logic of their own — they
    translate HTTP into service calls and service results into status codes.
    """

    def __init__(self, auth_service: AuthenticationService) -> None:
        super().__init__()
        self.auth_service = auth_service

    @post(const.AUTH_LOGIN_PATH)
    async def login(self, request: Request) -> dict[str, Any]:
        """Exchange a credential for an access token.

        Returns 401 on an unknown email or a wrong password. The two are
        deliberately indistinguishable: the service always performs a hash
        verification regardless of whether the user exists, and this handler
        must not undo that by answering differently.
        """
        body = await _read_json_object(request)
        try:
            payload = LoginRequest(**body)
        except ValidationError as exc:
            raise BadRequestError(f"Invalid login payload: {exc}") from exc

        result: Result[
            User, InvalidCredentialsError | AccountLockedError
        ] = await self.auth_service.authenticate_user(
            email=payload.email,
            password=payload.password,
        )
        if result.is_err():
            # The service returns either InvalidCredentialsError or
            # AccountLockedError; both mean "no token for you", and neither
            # should reveal which.
            raise UnauthorizedError("Invalid credentials")

        user = result.unwrap()
        token = self.auth_service.create_token(user)
        return {
            "access_token": token.token,
            "refresh_token": token.refresh_token,
            "token_type": token.token_type,
            "expires_at": token.expires_at.isoformat(),
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "name": getattr(user, "name", None),
                "roles": list(getattr(user, "roles", []) or []),
            },
        }

    @post(const.AUTH_REGISTER_PATH)
    async def register(self, request: Request) -> dict[str, Any]:
        """Create a user and hand back a token for the new account.

        Returns 409 when the email is taken, 422 when the password violates
        the configured policy — both are actionable by the caller, so neither
        is collapsed into a generic 400.
        """
        body = await _read_json_object(request)
        try:
            payload = RegisterRequest(**body)
        except ValidationError as exc:
            raise BadRequestError(f"Invalid registration payload: {exc}") from exc

        result = await self.auth_service.register_user(payload)
        if result.is_err():
            error = result.unwrap_err()
            name = type(error).__name__
            if name == "EmailExistsError":
                raise ConflictError(str(error)) from error
            if name == "PasswordPolicyError":
                raise BadRequestError(str(error)) from error
            raise BadRequestError(str(error)) from error

        user = result.unwrap()
        token = self.auth_service.create_token(user)
        return {
            "access_token": token.token,
            "refresh_token": token.refresh_token,
            "token_type": token.token_type,
            "expires_at": token.expires_at.isoformat(),
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "name": getattr(user, "name", None),
                "roles": list(getattr(user, "roles", []) or []),
            },
        }


__all__ = ["AuthController"]
