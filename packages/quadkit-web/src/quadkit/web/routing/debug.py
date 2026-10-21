from __future__ import annotations

import hmac
import ipaddress
from typing import TYPE_CHECKING, Any, cast

from quadkit.logging import get_logger
from quadkit.web.transport.responses import JSONResponse

if TYPE_CHECKING:
    from quadkit.web.di.provider import WebProvider

logger = get_logger(__name__)


async def _check_debug_auth(
    request: Any,
    provider: WebProvider,
) -> JSONResponse | None:
    """Check debug route authorization.

    Returns None when the request is authorized, or a denial JSONResponse
    (403 / 404) when it is not.
    """
    cfg = provider.web_config
    authorized = False

    # Token check
    token = getattr(cfg, "debug_routes_token", None) or getattr(
        provider.provider_config, "debug_routes_token", None
    )
    token_value = (
        token.get_secret_value()
        if token is not None and hasattr(token, "get_secret_value")
        else token
    )
    provided = request.headers.get("X-Debug-Token")
    if (
        token_value
        and provided is not None
        and hmac.compare_digest(provided, token_value)
    ):
        authorized = True

    # Custom auth callback
    if not authorized and provider.debug_routes_auth:
        try:
            authorized = await provider.debug_routes_auth(request)
        except Exception as exc:  # noqa: BLE001 — a failing auth callback must not crash the route
            logger.warning("Debug route auth callback failed: %s", exc)
            return JSONResponse({"error": "internal_error"}, status_code=500)

    # Middleware gate
    req_mw = getattr(cfg, "debug_routes_require_middleware", None) or getattr(
        provider.provider_config, "debug_routes_require_middleware", None
    )
    if req_mw:
        middleware_names = [type(mw).__name__ for mw in provider.middleware]
        if req_mw in middleware_names:
            authorized = True
        else:
            return JSONResponse({"error": "Not Found"}, status_code=404)

    # IP fallback — allow local, deny remote when no other auth is configured
    if not authorized and not token and not provider.debug_routes_auth and not req_mw:
        client_ip = _get_client_ip(request)
        if not client_ip or _is_local_ip(client_ip):
            authorized = True

    if not authorized:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    return None


async def _apply_rate_limit(
    request: Any,
    provider: WebProvider,
) -> JSONResponse | None:
    """Apply rate limiting to a debug route request.

    Returns None when the request is within limits, or a 429 JSONResponse
    when the rate limit is exceeded.
    """
    cfg = provider.web_config
    try:
        rate_limit_raw = getattr(cfg, "debug_routes_rate_limit", 0) or getattr(
            provider.provider_config, "debug_routes_rate_limit", 0
        )
        rate_limit = (
            int(str(rate_limit_raw))
            if rate_limit_raw is not None and not isinstance(rate_limit_raw, bool)
            else 0
        )
        if isinstance(rate_limit_raw, bool) and rate_limit_raw:
            rate_limit = 100
    except (ValueError, TypeError):
        rate_limit = 0

    logger.debug(
        "Debug route rate limit: %s (client: %s)",
        rate_limit,
        provider._debug_redis_client,
    )

    if rate_limit > 0 and provider._debug_redis_client:
        try:
            window_raw = getattr(
                cfg, "debug_routes_rate_window_seconds", 60
            ) or getattr(
                provider.provider_config, "debug_routes_rate_window_seconds", 60
            )
            window = int(str(window_raw)) if window_raw is not None else 60
        except (ValueError, TypeError):
            window = 60

        client_ip = _get_client_ip(request) or "unknown"
        key = f"debug_rate_limit:{client_ip}"

        try:
            count = await provider._debug_redis_client.incr(key)
            if count == 1:
                await provider._debug_redis_client.expire(key, window)
            if count > rate_limit:
                return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)
        except Exception as e:  # noqa: BLE001
            logger.warning("Debug rate limiting error: %s", e)

    return None


def register_debug_routes(provider: WebProvider) -> None:
    """Register the /debug/routes diagnostic endpoint."""
    starlette = provider.starlette
    if starlette is None:
        raise RuntimeError("Starlette application not initialized in provider")

    async def debug_routes(request: Any) -> JSONResponse:
        deny = await _check_debug_auth(request, provider)
        if deny is not None:
            return deny

        deny = await _apply_rate_limit(request, provider)
        if deny is not None:
            return deny

        server_cfg = getattr(provider.web_config, "server", None)
        redact = not getattr(server_cfg, "debug", False)
        diagnostics = []

        if hasattr(provider, "router_manager") and hasattr(
            provider.router_manager, "_registered_routes"
        ):
            for (
                method,
                path,
            ), origins in provider.router_manager._registered_routes.items():
                sanitized = [_sanitize_origin(o, redact) for o in origins]
                diagnostics.append(
                    {"method": method, "path": path, "origins": sanitized}
                )

        return JSONResponse({"routes": diagnostics})

    starlette.add_route("/debug/routes", debug_routes, methods=["GET"])


def _get_client_ip(request: Any) -> str | None:
    """Get client IP from request headers or connection info."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return cast("str", xff.split(",")[0].strip())

    xri = request.headers.get("X-Real-IP")
    if xri:
        return cast("str", xri.strip())

    if hasattr(request, "client") and request.client:
        return cast("str", request.client.host)

    return None


def _sanitize_origin(origin: Any, redact: bool) -> Any:
    """Sanitize origin information for debug output."""
    if not isinstance(origin, dict):
        return origin

    sanitized = origin.copy()

    if redact:
        if "registered_file" in sanitized:
            sanitized["registered_file"] = "<REDACTED>"
        if sanitized.get("registered_stack"):
            sanitized["registered_stack"] = ["<REDACTED>"] * len(
                sanitized["registered_stack"]
            )

    return sanitized


def _is_local_ip(ip: str) -> bool:
    """Check if IP address is local/private."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_loopback or addr.is_private or addr.is_link_local
    except ValueError:
        return True
