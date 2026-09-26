from __future__ import annotations

from typing import Any

from quadkit.auth import constants as const


class AuthResponseHandler:
    """Handles authentication-related HTTP responses."""

    @staticmethod
    async def unauthorized_response(
        message: str = "Authentication required",
        request: Any = None,
        response_factory: Any | None = None,
    ) -> Any:
        """Return 401 Unauthorized response or redirect to login."""
        rf = response_factory or await _get_response_factory(request)

        if request and rf:
            # Check if client accepts HTML
            accept = request.headers.get("Accept", "")
            if "text/html" in accept:
                login_url = getattr(request, "login_url", "/login")
                return rf.redirect(
                    f"{login_url}?next={request.url.path}",
                    status_code=302,
                )

        if rf:
            return rf.json(
                status_code=401,
                content={"error": "unauthorized", "message": message},
                headers={"WWW-Authenticate": f'{const.DEFAULT_TOKEN_TYPE} realm="api"'},
            )

        raise RuntimeError(
            "ResponseFactoryProtocol not available for unauthorized_response — ensure DI container is configured",
        )

    @staticmethod
    async def forbidden_response(
        message: str = "Insufficient permissions",
        request: Any | None = None,
        response_factory: Any | None = None,
    ) -> Any:
        """Return 403 Forbidden response."""
        rf = response_factory or await _get_response_factory(request)
        if rf:
            return rf.json(
                status_code=403,
                content={"error": "forbidden", "message": message},
            )

        raise RuntimeError(
            "ResponseFactoryProtocol not available for forbidden_response — ensure DI container is configured",
        )


async def _get_response_factory(context: Any | None = None) -> Any:
    """Resolve `ResponseFactoryProtocol` from context or global container."""
    from quadkit.contracts.web import ResponseFactoryProtocol
    from quadkit.di.resolution.context import get_resolver

    resolver = get_resolver(context)
    if not resolver:
        return None

    return await resolver.resolve_optional(ResponseFactoryProtocol)


__all__ = [
    "AuthResponseHandler",
]
