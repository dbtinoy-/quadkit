"""ASGI server execution. Runs the configured web application."""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)

# Granian kwargs accepted by the Python API (address/port/interface handled separately).
_GRANIAN_ACCEPTED: frozenset[str] = frozenset(
    {
        "workers",
        "threads",
        "blocking_threads",
        "runtime_threads",
        "runtime_blocking_threads",
        "backlog",
        "backpressure",
        "loop",
        "task_impl",
        "log_level",
        "log_config",
        "access_log",
        "access_log_fmt",
        "ssl_certificate",
        "ssl_keyfile",
        "ssl_keyfile_password",
        "ssl_ca",
        "ssl_crl",
        "ssl_client_verify",
        "url_path_prefix",
        "factory",
        "reload",
        "reload_paths",
        "reload_ignore_dirs",
        "reload_ignore_patterns",
        "respawn_failed_workers",
        "respawn_interval",
        "pid_file",
        "path_prefix",
    }
)

# Auto-preference order when no backend is configured.
_PREFERRED_BACKENDS: tuple[str, ...] = ("granian", "uvicorn")


def _resolve_backend(app: Any) -> str:
    """Resolve the ASGI server backend.

    Reads ``web.server.backend`` from ``application.yaml`` via the app
    config.  Falls back to auto-preference (granian → uvicorn) when the
    config is absent or the requested backend is not installed.
    """
    config = getattr(app, "config", None)
    if config is not None:
        try:
            from quadkit.web.config import WebConfig

            web = config.get_section("web", WebConfig)
            requested = web.server.backend
            if _is_available(requested):
                result: str = str(requested)
                return result
        except Exception:
            pass

    for name in _PREFERRED_BACKENDS:
        if _is_available(name):
            return name

    return "uvicorn"


def _load_backend(name: str) -> Any:
    """Import an optional server backend by name.

    Optional backends are resolved through :func:`importlib.import_module`
    so type checkers treat them as dynamic (they are only present when the
    user installs the matching server), and tests can exercise them by
    patching ``sys.modules``.
    """
    import importlib

    return importlib.import_module(name)


def _is_available(name: str) -> bool:
    """Check if a server backend is importable."""
    try:
        _load_backend(name)
    except (ImportError, ModuleNotFoundError):
        return False
    return True


def _to_import_string(app: Any) -> str | None:
    """Derive an import string (``module:attr``) from an ASGI app instance.

    Granian requires a string import path for multiprocessing workers.
    We look for a ``create_app`` factory in the caller's frame module,
    because Granian needs to call a factory (with ``factory=True``) to
    create the app in each worker process.
    """
    try:
        # Walk the call stack to find the caller's module that has create_app
        import inspect

        frame = inspect.currentframe()
        try:
            # Walk up to 10 frames looking for a module with create_app
            caller_frame = frame
            for _ in range(10):
                caller_frame = caller_frame.f_back if caller_frame is not None else None
                if caller_frame is None:
                    break
                caller_module = caller_frame.f_globals.get("__name__")
                if caller_module and caller_module != __name__:
                    try:
                        mod = __import__(
                            caller_module, fromlist=[caller_module.rsplit(".", 1)[-1]]
                        )
                        if hasattr(mod, "create_app") and callable(mod.create_app):
                            return f"{caller_module}:create_app"
                    except ImportError:
                        continue
        finally:
            del frame

        # Fallback: class module
        module = app.__class__.__module__
        if module == "builtins" or module.startswith("starlette."):
            return None
        return str(f"{module}:{app.__class__.__name__}")
    except (AttributeError, TypeError):
        return None


def run_server(
    app: Any,
    host: str | None = None,
    port: int | None = None,
    **kwargs: Any,
) -> None:
    """Run the web application synchronously, blocking the caller.

    This is the sync entry point: it always runs the server directly in
    the calling thread and never inspects the surrounding context. Call
    :func:`run_server_async` from async code instead — calling this from a
    running event loop raises :class:`RuntimeError` rather than silently
    blocking the loop.

    The backend is resolved in this order:

    1. ``web.server.backend`` in ``application.yaml`` (config-driven)
    2. Auto-preference: Granian → Uvicorn (when config is absent)

    Args:
        app: ASGI application instance or import string (``"module:attr"``).
        host: Bind address.  Reads from ``app.config.web.server.host``
            when not provided.
        port: Bind port.  Reads from ``app.config.web.server.port``
            when not provided.
        **kwargs: Additional server arguments. For Granian, only accepted
            kwargs are forwarded; unknown keys are silently dropped.

    Raises:
        RuntimeError: If called from an async context (use
            :func:`run_server_async` instead).
        ImportError: If the resolved server backend is not installed.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "run_server() is a sync, blocking API and cannot be called from "
            "a running event loop; use run_server_async() instead."
        )

    _run_sync(app, host, port, **kwargs)


async def run_server_async(
    app: Any,
    host: str | None = None,
    port: int | None = None,
    **kwargs: Any,
) -> None:
    """Run the web application from a running event loop.

    Async entry point: Uvicorn serves in the calling loop; Granian and
    Gunicorn run in an executor thread (they manage their own processes /
    loops). This must be called from a running event loop.

    Args:
        app: ASGI application instance or import string (``"module:attr"``).
        host: Bind address.  Reads from ``app.config.web.server.host``
            when not provided.
        port: Bind port.  Reads from ``app.config.web.server.port``
            when not provided.
        **kwargs: Additional server arguments. For Granian, only accepted
            kwargs are forwarded; unknown keys are silently dropped.

    Raises:
        RuntimeError: If no event loop is running.

    Returns:
        A coroutine that completes when the server stops.
    """
    loop = asyncio.get_running_loop()
    await _run_in_loop(loop, app, host, port, **kwargs)


async def _run_in_loop(
    loop: asyncio.AbstractEventLoop,
    app: Any,
    host: str | None,
    port: str | int | None,
    **kwargs: Any,
) -> None:
    """Dispatch from within a running event loop."""
    backend = _resolve_backend(app)
    host, port = _resolve_web_config(app, host, port)

    if backend == "uvicorn":
        await _run_uvicorn_async(app, host, port, **kwargs)
        return

    if backend == "granian":
        import_str = _to_import_string(app) if not isinstance(app, str) else app
        if import_str is None:
            logger.warning(
                "granian_fallback_uvicorn",
                reason="could not derive import string from app instance",
            )
            await _run_uvicorn_async(app, host, port, **kwargs)
        else:
            filtered = {k: v for k, v in kwargs.items() if k in _GRANIAN_ACCEPTED}
            await loop.run_in_executor(
                None, lambda: _run_granian(import_str, host, port, **filtered)
            )
        return

    if backend == "gunicorn":
        await loop.run_in_executor(
            None, lambda: _run_gunicorn(app, host, port, **kwargs)
        )
        return

    logger.warning("unknown_backend_fallback_uvicorn", backend=backend)
    await _run_uvicorn_async(app, host, port, **kwargs)


def _run_sync(
    app: Any,
    host: str | None,
    port: str | int | None,
    **kwargs: Any,
) -> None:
    """Dispatch from sync context (no event loop running)."""
    host, port = _resolve_web_config(app, host, port)

    backend = _resolve_backend(app)
    logger.info("server_backend_resolved", backend=backend, host=host, port=port)

    if backend == "granian":
        import_str = _to_import_string(app) if not isinstance(app, str) else app
        if import_str is None:
            logger.warning(
                "granian_fallback_uvicorn",
                reason="could not derive import string from app instance",
            )
            _run_uvicorn(app, host, port, **kwargs)
        else:
            filtered = {k: v for k, v in kwargs.items() if k in _GRANIAN_ACCEPTED}
            _run_granian(import_str, host, port, **filtered)
    elif backend == "gunicorn":
        _run_gunicorn(app, host, port, **kwargs)
    else:
        _run_uvicorn(app, host, port, **kwargs)


def _resolve_web_config(
    app: Any, host: str | None, port: str | int | None
) -> tuple[str, int]:
    """Read host/port from app.config when not explicitly provided."""
    config = getattr(app, "config", None)
    if config is None:
        return host or "127.0.0.1", int(port or 8000)
    try:
        from quadkit.web.config import WebConfig

        web = config.get_section("web", WebConfig)
        return host or web.server.host, int(port or web.server.port)
    except Exception:
        return host or "127.0.0.1", int(port or 8000)


def _run_granian(
    app: str,
    host: str,
    port: int,
    **kwargs: Any,
) -> None:
    """Run via Granian (multiprocess)."""
    try:
        granian = _load_backend("granian")
        granian_constants = _load_backend("granian.constants")
    except (ImportError, ModuleNotFoundError) as e:
        raise ImportError(
            "Granian is not installed. Install 'granian' to use this backend.",
        ) from e

    logger.info("starting_granian_server", host=host, port=port, kwargs=kwargs)
    server = granian.Granian(
        app,
        address=host,
        port=port,
        interface=granian_constants.Interfaces.ASGI,
        factory=True,
        **kwargs,
    )
    server.serve()


def _run_uvicorn(
    app: Any,
    host: str,
    port: int,
    **kwargs: Any,
) -> None:
    """Run via Uvicorn (sync context — creates its own event loop)."""
    uvicorn = _load_backend("uvicorn")

    logger.info("starting_uvicorn_server", host=host, port=port, kwargs=kwargs)
    config = uvicorn.Config(app, host=host, port=port, **kwargs)
    server = uvicorn.Server(config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.serve())


async def _run_uvicorn_async(
    app: Any,
    host: str,
    port: int,
    **kwargs: Any,
) -> None:
    """Run via Uvicorn (async context — reuses the running loop)."""
    uvicorn = _load_backend("uvicorn")

    logger.info("starting_uvicorn_server", host=host, port=port, kwargs=kwargs)
    config = uvicorn.Config(app, host=host, port=port, **kwargs)
    server = uvicorn.Server(config)
    await server.serve()


def _run_gunicorn(
    app: Any,
    host: str,
    port: int,
    **kwargs: Any,
) -> None:
    """Run via Gunicorn with Uvicorn workers."""
    import subprocess  # noqa: S404 — registry-built argv list

    _load_backend("gunicorn")

    workers = kwargs.get("workers", 1)
    cmd = [
        "gunicorn",
        "-w",
        str(workers),
        "-b",
        f"{host}:{port}",
        "-k",
        "uvicorn_worker.UvicornWorker",
    ]
    if isinstance(app, str):
        cmd.append(app)
    else:
        import_str = _to_import_string(app)
        if import_str:
            cmd.append(import_str)
        else:
            logger.warning(
                "gunicorn_fallback_uvicorn", reason="could not derive import string"
            )
            _run_uvicorn(app, host, port, **kwargs)
            return

    logger.info("starting_gunicorn_server", host=host, port=port, kwargs=kwargs)
    subprocess.run(cmd, check=False)  # noqa: S603


__all__ = ["run_server", "run_server_async"]
