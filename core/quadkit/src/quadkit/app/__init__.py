"""Application runtime package for Quadkit Framework.

Entry-point for creating, starting, and stopping a Quadkit
:class:`Application`.  Lifecycle helper functions live in
:mod:`quadkit.app.runner`; the DI :class:`CoreProvider` lives in
:mod:`quadkit.app.di.provider`.

Exports:
    Application: The main application class.
    AppState: Application lifecycle state enum.
    run_application: Start, await OS signal, then stop.
    start_application: Start the application and its providers.
    stop_application: Gracefully stop the application.
"""

from __future__ import annotations

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.app.base import Application, AppState
    from quadkit.app.factory import create_app
    from quadkit.app.module import CoreModule
    from quadkit.app.pipeline import MiddlewarePipeline
    from quadkit.app.runner import (
        run_application,
        start_application,
        stop_application,
    )
    from quadkit.app.standard import StandardModule

_LAZY_IMPORTS: dict[str, str] = {
    "Application": "quadkit.app.base",
    "CoreModule": "quadkit.app.module",
    "StandardModule": "quadkit.app.standard",
    "create_app": "quadkit.app.factory",
    "run_application": "quadkit.app.runner",
    "start_application": "quadkit.app.runner",
    "stop_application": "quadkit.app.runner",
    # types
    "AppState": "quadkit.app.types",
    "ApplicationStarted": "quadkit.app.types",
    "ApplicationStarting": "quadkit.app.types",
    "ApplicationStopped": "quadkit.app.types",
    "ApplicationStopping": "quadkit.app.types",
    "HealthCheckCompleted": "quadkit.app.types",
    "ProviderBooted": "quadkit.app.types",
    "ProviderRegistered": "quadkit.app.types",
    # constants
    "DEFAULT_APP_NAME": "quadkit.app.constants",
    "DEFAULT_HEALTH_CHECK_TIMEOUT": "quadkit.app.constants",
    "DEFAULT_SHUTDOWN_TIMEOUT": "quadkit.app.constants",
    # protocols
    "AppLifecycleProtocol": "quadkit.app.protocols",
    # --- added by migration script ---
    "AppConfig": "quadkit.app.config.models",
    "AppError": "quadkit.app.exceptions",
    "AppShutdownError": "quadkit.app.exceptions",
    "AppStartupError": "quadkit.app.exceptions",
    "CoreProvider": "quadkit.app.di.provider",
    "InjectableAutoProvider": "quadkit.app.injectable_provider",
    # pipeline
    "MiddlewarePipeline": "quadkit.app.pipeline",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return list(_LAZY_IMPORTS.keys())


__all__ = list(_LAZY_IMPORTS.keys())
