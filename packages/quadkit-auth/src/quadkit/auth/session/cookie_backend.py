"""Session-cookie authentication backend for SSR admin flows.

This module provides :class:`SessionCookieBackend`, which authenticates
requests by reading a session-ID cookie, looking up the session in a
:class:`~quadkit.contracts.auth.repositories.SessionRepositoryProtocol`
implementation, and then resolving the owning user via a caller-supplied
async callable.

This is intentionally separate from :class:`~quadkit.auth.authn.jwt.JWTTokenManager`
— it targets SSR pages where the browser (not a JS client) manages
credentials through an ``HttpOnly`` cookie rather than a ``Bearer`` header.

Dependency graph (all injected, nothing imported from sibling extensions):

    request → cookie → SessionRepositoryProtocol.find_active
                     → user_fetcher(user_id) → AuthenticatedUserProtocol
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, timedelta
from typing import Any

from quadkit.contracts.auth.repositories import SessionRepositoryProtocol
from quadkit.contracts.auth.user import AuthenticatedUserProtocol
from quadkit.contracts.core.identity import IdGeneratorProtocol
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

logger = get_logger(__name__)


class SessionCookieBackend:
    """Session-cookie authentication backend for SSR flows.

    Reads session ID from cookie, resolves user from
    :class:`~quadkit.contracts.auth.repositories.SessionRepositoryProtocol`.

    Because session records contain only a ``user_id``, resolving the full
    :class:`~quadkit.contracts.auth.user.AuthenticatedUserProtocol` requires
    a ``user_fetcher`` callable that looks up the concrete user object from
    whatever store the application uses (database, cache, etc.).  This keeps
    the backend decoupled from any specific user-store implementation.

    Constructor args:
        session_repository: Persistence backend for session records.
        user_fetcher: Async callable that accepts a ``user_id`` string and
            returns the matching :class:`AuthenticatedUserProtocol`, or
            ``None`` when no user exists for that ID.
        cookie_name: Name of the session cookie (default ``"session_id"``).
        secure: Whether to set the ``Secure`` flag (default ``True``).
        http_only: Whether to set the ``HttpOnly`` flag (default ``True``).
        same_site: The ``SameSite`` policy (default ``"lax"``).

    Example::

        backend = SessionCookieBackend(
            session_repository=sql_session_repo,
            user_fetcher=user_service.get_authenticated_user,
        )

        # In an SSR handler:
        user = await backend.authenticate(request)
        if user is None:
            # redirect to /login
            ...
    """

    def __init__(
        self,
        session_repository: SessionRepositoryProtocol,
        user_fetcher: Callable[[str], Awaitable[AuthenticatedUserProtocol | None]],
        ids: IdGeneratorProtocol | None = None,
        cookie_name: str = "session_id",
        secure: bool = True,
        http_only: bool = True,
        same_site: str = "lax",
    ) -> None:
        from quadkit.identity.generator import Uuid4Generator

        self._repo = session_repository
        self._user_fetcher = user_fetcher
        self._ids = ids if ids is not None else Uuid4Generator()
        self._cookie_name = cookie_name
        self._secure = secure
        self._http_only = http_only
        self._same_site = same_site

    async def authenticate(self, request: Any) -> AuthenticatedUserProtocol | None:
        """Extract session cookie, validate, return user or ``None``.

        Reads ``cookie_name`` from ``request.cookies``, fetches the
        corresponding active session record, resolves the user via
        ``user_fetcher``, and refreshes the ``last_active_at`` timestamp.

        Args:
            request: The incoming request object.  Must expose a
                ``cookies`` mapping attribute (Starlette / ASGI-compatible).

        Returns:
            The authenticated user if the session is valid, ``None`` otherwise.
        """
        session_id: str | None = request.cookies.get(self._cookie_name)
        if not session_id:
            return None

        row = await self._repo.find_active(session_id)
        if row is None:
            logger.debug("session_not_found", session_id=session_id)
            return None

        user_id: str = row["user_id"]
        user = await self._user_fetcher(user_id)
        if user is None:
            logger.warning(
                "session_user_not_found",
                session_id=session_id,
                user_id=user_id,
            )
            return None

        # Touch the last-active timestamp so the session stays warm.
        await self._repo.update_activity(
            session_id, ambient_clock.now().replace(tzinfo=UTC)
        )

        return user

    async def login(
        self,
        response: Any,
        user_id: str,
        expires_in: int = 86400,
    ) -> str:
        """Create a session record and set the session cookie on *response*.

        Args:
            response: The outgoing response object.  Must expose a
                ``set_cookie`` method with ``key``, ``value``, ``max_age``,
                ``secure``, ``httponly``, and ``samesite`` kwargs
                (Starlette / ASGI-compatible).
            user_id: Identifier of the user to create a session for.
            expires_in: Session lifetime in **seconds** (default 86 400 = 1 day).

        Returns:
            The newly created ``session_id``.
        """
        session_id = self._ids.generate_for("Session")
        expires_at = ambient_clock.now().replace(tzinfo=UTC) + timedelta(
            seconds=expires_in
        )

        await self._repo.insert(
            {
                "session_id": session_id,
                "user_id": user_id,
                "device_id": "ssr",
                "expires_at": expires_at,
            }
        )

        response.set_cookie(
            key=self._cookie_name,
            value=session_id,
            max_age=expires_in,
            secure=self._secure,
            httponly=self._http_only,
            samesite=self._same_site,
        )

        logger.info("session_created", session_id=session_id, user_id=user_id)
        return session_id

    async def logout(self, request: Any, response: Any) -> None:
        """Invalidate the session and clear the cookie.

        Args:
            request: The incoming request.  ``request.cookies`` is read to
                find the current session ID.
            response: The outgoing response.  ``delete_cookie`` is called to
                remove the session cookie from the browser.
        """
        session_id: str | None = request.cookies.get(self._cookie_name)
        if session_id:
            await self._repo.revoke(session_id)
            logger.info("session_revoked", session_id=session_id)

        response.delete_cookie(key=self._cookie_name)


__all__ = ["SessionCookieBackend"]
