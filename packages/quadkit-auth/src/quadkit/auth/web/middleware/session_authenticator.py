"""Session-based authentication component."""

from __future__ import annotations

from typing import Any

from quadkit.contracts import AuthProviderProtocol


class SessionAuthenticator:
    """Handles session validation and user resolution."""

    def __init__(self, auth_provider: AuthProviderProtocol):
        self.auth_provider = auth_provider

    async def authenticate(self, request: Any) -> Any:
        """Validate session from cookies and return user if valid."""
        session_id = request.cookies.get("session_id")
        if not session_id or not self.auth_provider.session_manager:
            return None

        session_result = await self.auth_provider.session_manager.validate_session(
            session_id,
        )
        # SessionManagerImpl.validate_session() returns a Result (Ok(session)
        # or Err(...)), not the session itself — unwrap it defensively so
        # callers that pass a simpler session manager (returning the session
        # directly, or None) keep working too.
        if session_result is None:
            return None
        if hasattr(session_result, "is_err"):
            if session_result.is_err():
                return None
            session = session_result.unwrap()
        else:
            session = session_result
        if not session:
            return None

        user = await self.auth_provider.get_user(session.user_id)
        if not user:
            return None

        # Store session in request state for downstream use
        request.state.session = session

        # Pre-fetch delegations for sync check_access
        if self.auth_provider.delegation_manager:
            request.state.delegations = (
                await self.auth_provider.delegation_manager.get_active_delegations(
                    user.user_id,
                )
            )

        return user


__all__ = [
    "SessionAuthenticator",
]
