"""Health check route registration for quadkit-web."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from starlette.responses import JSONResponse, Response

from quadkit.contracts.core import HealthStatus
from quadkit.logging import get_logger
from quadkit.web import constants as const
from quadkit.web.routing.health_checks import WebHealthChecker

if TYPE_CHECKING:
    from starlette.requests import Request

    from quadkit.app.base import Application
    from quadkit.web.di.provider import WebProvider

logger = get_logger(__name__)

_STATUS_CODE_MAP: dict[HealthStatus, int] = {
    HealthStatus.HEALTHY: 200,
    HealthStatus.DEGRADED: 207,
    HealthStatus.UNHEALTHY: 503,
    HealthStatus.UNKNOWN: 503,
    HealthStatus.STARTING: 503,
}


async def _resolve_application(request: Request) -> Application:
    """Resolve the quadkit Application from the Starlette request."""
    from quadkit.app.base import Application as QuadkitApplication

    container = getattr(getattr(request, "app", None), "state", None)
    container = getattr(container, "container", None)
    if container is None:
        raise RuntimeError("Application container not available")
    return cast(
        "QuadkitApplication",
        await container.resolve(QuadkitApplication, bypass_visibility=True),
    )


def _status_code_for(status: HealthStatus) -> int:
    """Map a health status to an HTTP status code."""
    return _STATUS_CODE_MAP.get(status, 503)


async def _probe_response(request: Request, probe_name: str) -> Response:
    """Run a named application probe and return a JSON response."""
    app = await _resolve_application(request)
    probe = getattr(app, probe_name)
    result = await probe()
    return JSONResponse(result.to_dict(), status_code=_status_code_for(result.status))


def register_health_route(provider: WebProvider, _app: Application) -> None:
    """Register comprehensive health check routes.

    Idempotent: skips registration when a route for the health path is
    already present (e.g. registered before contributor mounts so that
    extension-provided routes cannot shadow the canonical endpoint).
    """
    starlette = provider.starlette
    if starlette is None:
        raise RuntimeError("Starlette application not initialized")

    prefix = str(
        getattr(
            provider.web_config,
            "health_check_prefix",
            const.DEFAULT_HEALTH_PATH,
        )
    )
    if any(
        getattr(route, "path", None) == prefix
        for route in getattr(starlette, "routes", [])
    ):
        logger.debug("web.health_route_already_registered", path=prefix)
        return

    async def health_handler(request: Request) -> Response:
        """Return 200/207/503 based on real dependency health checks."""
        container = getattr(getattr(request, "app", None), "state", {})
        container = getattr(container, "container", None)

        db_provider = None
        redis_client = None

        if container is not None:
            try:
                from quadkit.contracts.data import DatabaseProviderProtocol

                db_provider = await container.resolve(DatabaseProviderProtocol)
            except Exception:  # noqa: BLE001, S110
                pass
            try:
                from quadkit.contracts.infra.cache import CacheBackendProtocol

                redis_client = await container.resolve(CacheBackendProtocol)
            except Exception:  # noqa: BLE001, S110
                pass

        checker = WebHealthChecker(
            db_provider=db_provider,
            cache_backend=redis_client,
        )
        result = await checker.check_health()
        status_code = _status_code_for(result.status)
        return JSONResponse(result.model_dump(mode="json"), status_code=status_code)

    async def liveness_handler(request: Request) -> Response:
        """Return liveness probe results from the application."""
        return await _probe_response(request, "liveness")

    async def readiness_handler(request: Request) -> Response:
        """Return readiness probe results from the application."""
        return await _probe_response(request, "readiness")

    async def startup_handler(request: Request) -> Response:
        """Return startup probe results from the application."""
        return await _probe_response(request, "startup_check")

    # Use prefix from config if available
    starlette.add_route(prefix, health_handler, methods=["GET"])
    starlette.add_route(f"{prefix.rstrip('/')}/live", liveness_handler, methods=["GET"])
    starlette.add_route(
        f"{prefix.rstrip('/')}/ready",
        readiness_handler,
        methods=["GET"],
    )
    starlette.add_route(
        f"{prefix.rstrip('/')}/startup",
        startup_handler,
        methods=["GET"],
    )
