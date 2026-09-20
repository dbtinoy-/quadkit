"""Quick-start module for single-file Quadkit web applications.

Provides a module-level ``app`` ASGI instance so that a minimal API can be
built in 6 lines::

    from quadkit.web import app, get, singleton

    @singleton
    class UserRepo:
        async def find(self, id: str) -> dict:
            return {"id": id, "name": "Alice"}

    @get("/users/{id}")
    async def get_user(id: str, repo: UserRepo) -> dict:
        return await repo.find(id)

Routes registered with ``@get``, ``@post``, etc. are automatically picked up
by the :class:`~quadkit.web.routing.route_handlers.CoreRouteHandler` when the
application boots.

The ``app`` object is a lazy ASGI proxy — the real application is only created
when the first ASGI message arrives.

:func:`singleton` and :func:`injectable` decorators register classes directly
in a module-level registry so the quickstart container can discover them even
when they are defined inside functions or test scopes (not as module-level
names found by a ``sys.modules`` scan).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Quickstart DI registry
# ---------------------------------------------------------------------------

#: Global registry populated by :func:`singleton` and :func:`injectable`.
#: Entries are ``(cls, scope_string)`` pairs consumed at boot time by
#: :class:`_QuickstartApp._collect_script_services`.
_QUICKSTART_REGISTRY: list[tuple[type, str]] = []


def singleton(cls: type[T]) -> type[T]:
    """Mark *cls* as a singleton and auto-register it in the quickstart container.

    Combines the ``quadkit.di.singleton`` DI marker (which sets
    ``__quadkit_injectable__``) with a direct entry in the quickstart
    service registry so the class is discovered regardless of whether it
    is defined at module scope.

    Returns the class unchanged, so the decorator is transparent.

    Args:
        cls: The class to register as a container-managed singleton.

    Returns:
        The original *cls* with the injectable marker applied.

    Example::

        from quadkit.web import app, get, singleton

        @singleton
        class UserRepo:
            async def find(self, user_id: str) -> dict:
                return {"id": user_id}
    """
    from quadkit.contracts.core.scopes import ServiceScope
    from quadkit.di.decorators import Injectable

    Injectable(scope=ServiceScope.SINGLETON)(cls)
    _QUICKSTART_REGISTRY.append((cls, ServiceScope.SINGLETON))
    return cls


def injectable(cls: type[T]) -> type[T]:
    """Mark *cls* as transient and auto-register it in the quickstart container.

    Each DI resolution creates a new instance of the class (transient scope).
    This is the quickstart alias for the transient-scope decorator.

    Returns the class unchanged, so the decorator is transparent.

    Args:
        cls: The class to register as a transient (per-resolve) service.

    Returns:
        The original *cls* with the injectable marker applied.

    Example::

        from quadkit.web import app, get, injectable
        from quadkit.logging import get_logger

        logger = get_logger(__name__)

        @injectable
        class RequestLogger:
            def log(self, msg: str) -> None:
                logger.info("request_log", message=msg)
    """
    from quadkit.contracts.core.scopes import ServiceScope
    from quadkit.di.decorators import Injectable

    Injectable(scope=ServiceScope.TRANSIENT)(cls)
    _QUICKSTART_REGISTRY.append((cls, ServiceScope.TRANSIENT))
    return cls


def _reset_quickstart_registry() -> None:
    """Clear the quickstart service registry and reset the global application state.

    Intended for use in tests to prevent cross-test state pollution.
    """
    _QUICKSTART_REGISTRY.clear()

    # Also reset the global QuickstartApp state if it exists
    if "app" in globals():
        app_obj = globals()["app"]
        if isinstance(app_obj, _QuickstartApp):
            app_obj._booted = False
            app_obj._application = None
            app_obj._starlette = None


# ---------------------------------------------------------------------------
# Internal data types
# ---------------------------------------------------------------------------


@dataclass
class _PendingRoute:
    """Lightweight route definition for script-mode handlers."""

    path: str
    method: str
    handler: Callable[..., Any]


#: Global registry for routes in quickstart mode.
#: Previously populated implicitly via sys.modules scan. Now must be set
#: explicitly on :class:`_QuickstartApp` instance before boot.
_QUICKSTART_ROUTE_REGISTRY: list[_PendingRoute] = []


class _QuickstartApp:
    """Lazy ASGI proxy for **development and prototyping only**.

    On first ASGI call the real :class:`~quadkit.app.base.Application` and
    :class:`~quadkit.web.di.provider.WebProvider` are created and booted.
    All subsequent calls are forwarded directly to the underlying Starlette app.

    .. warning::
        Quickstart mode is intended for **single-file scripts and prototypes**.
        It maintains global module-level state (route registry, service registry)
        that does not support multi-module projects, hot-reload isolation, or
        running multiple applications in the same process.

        For production applications use the full provider pattern::

            from quadkit.app import Application
            from quadkit.web.di.provider import WebProvider

            app = Application()
            app.add_provider(WebProvider(controllers=[...]))
    """

    def __init__(self) -> None:
        import os

        env = os.environ.get("QK_ENV", os.environ.get("APP_ENV", "development"))
        if env == "production":
            import warnings

            warnings.warn(
                "quadkit.web quickstart module is loaded in a production environment "
                "(QK_ENV=production). Quickstart is for development only. "
                "Use the full Application + WebProvider pattern in production.",
                stacklevel=2,
                category=UserWarning,
            )
        self._starlette: Any = None
        self._application: Any = None
        self._booted: bool = False

    def _collect_script_routes(self) -> list[_PendingRoute]:
        """Collect routes from explicit registry and sys.modules (backward compatibility).

        Returns explicit routes first, then falls back to sys.modules scan for
        backward compatibility with code that relies on automatic route discovery.

        Returns:
            A list of :class:`_PendingRoute` instances.
        """
        import sys

        routes: list[_PendingRoute] = list(_QUICKSTART_ROUTE_REGISTRY)
        seen: set[int] = {id(r.handler) for r in routes}

        for mod in list(sys.modules.values()):
            module_name: str = getattr(mod, "__name__", "") or ""
            # Skip framework internals to avoid double-registration
            if module_name.startswith("quadkit"):
                continue

            try:
                module_vars = vars(mod)
            except TypeError:
                continue

            for attr in module_vars.values():
                if not callable(attr):
                    continue

                fn_id = id(attr)
                if fn_id in seen:
                    continue

                # Case 1: Function-based routes (@get, @post, etc)
                # Strict check to avoid Mock objects (REVISION SCR-4)
                config = getattr(attr, "_route_config", None)
                if isinstance(config, dict):
                    seen.add(fn_id)
                    routes.append(
                        _PendingRoute(
                            path=config["path"],
                            method=config["method"],
                            handler=attr,
                        )
                    )
                    continue

                # Case 2: Class-based WebSocket handlers (@websocket_handler)
                # Strict check to avoid Mock objects (REVISION SCR-5)
                is_ws = getattr(attr, "_is_websocket_handler", False)
                if is_ws is True:
                    path = getattr(attr, "_ws_path", None)
                    if isinstance(path, str):
                        seen.add(fn_id)
                        routes.append(
                            _PendingRoute(
                                path=path,
                                method="WEBSOCKET",
                                handler=attr,
                            )
                        )
                    continue
        return routes

    def _collect_script_services(self) -> list[tuple[type, Any]]:
        """Return services from the explicit registry.

        Previously this method combined the explicit quickstart registry with
        a sys.modules scan for module-level @injectable/@singleton classes.
        Now it returns only services from the explicit registry, making service
        discovery deterministic and not subject to module import order.

        Returns:
            A list of ``(cls, scope_string)`` pairs from the quickstart registry.
        """
        return list(_QUICKSTART_REGISTRY)

    async def _ensure_booted(self) -> None:
        if self._booted:
            return
        from quadkit.app.base import Application
        from quadkit.identity.di.provider import IdentityProvider
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )
        from quadkit.web.config import WebConfig
        from quadkit.web.di.provider import WebProvider
        from quadkit.web.security.config import CSRFConfig

        # Script mode: disable CSRF (pure API, no browser session auth)
        web_config = WebConfig()
        web_config.security.csrf = CSRFConfig(enabled=False)

        # Add core infrastructure providers first (web depends on them)
        self._application = Application(name="quadkit-quickstart")
        self._application.add_provider(IdentityProvider())
        self._application.add_provider(ObservabilityProvider())

        provider = WebProvider(web_config=web_config)
        # Pass @singleton / @injectable services collected from user modules
        provider._extra_injectable_services = self._collect_script_services()
        # Inject script-mode routes so CoreRouteHandler can discover them
        self._application._pending_routes = self._collect_script_routes()
        self._application.add_provider(provider)
        await self._application.start()
        self._starlette = provider.starlette
        logger.warning(
            "quickstart_cold_boot",
            message="First request triggered application boot. "
            "Use create_app() for production deployments.",
        )
        self._booted = True

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await self._ensure_booted()
        await self._starlette(scope, receive, send)


#: Module-level ASGI-compatible application.
#: Import as ``from quadkit.web import app``.
app: _QuickstartApp = _QuickstartApp()


__all__ = [
    "_PendingRoute",
    "_QuickstartApp",
    "_reset_quickstart_registry",
    "app",
    "injectable",
    "singleton",
]
