"""ASGI server execution. Runs the configured web application.

Two entry points, two process models — pick by where you stand:

``run_server(app)`` (sync, main thread) owns the process. Granian runs
its real multiprocess supervisor here (``workers``/``reload`` honoured),
because this is the one context where a server may install signal
handlers. Uvicorn serves on a fresh loop; Gunicorn runs as a subprocess.

``await run_server_async(app)`` (already inside an event loop) serves
*in-loop*: Uvicorn and Hypercorn are awaited, Granian runs through its
embedded server (``granian.server.embed``) — the actual app object, in
the caller's loop, stopped programmatically. In-loop serving is
single-process by definition, so ``workers > 1`` and ``reload`` are
ignored there with a loud warning rather than silently half-honoured;
multiprocess serving is the sync entry point's (or the CLI's) job.

The backend is an instruction, not a preference, once configured:
``web.server.backend`` names one of ``granian``, ``uvicorn``,
``hypercorn``, ``gunicorn`` and that backend serves. Auto-preference
(Granian → Uvicorn) applies only when nothing is configured; a
configured-but-uninstalled backend falls back with a warning (a missing
optional dependency must not brick boot), while a backend name outside
the supported set raises. The one capability fallback that remains:
multiprocess backends need an import string, and when none can be
derived from a bare app object the runner falls back to Uvicorn serving
the object, loudly.

History: the async Granian branch used to dispatch ``Granian.serve()``
to a thread-pool executor, where CPython forbids the signal handlers
Granian installs at startup — an unconditional crash after a
healthy-looking boot (SERVER-1, resolved 2026-10-24 by embedded mode).
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)

# Granian (multiprocess) kwargs accepted by the Python API (address/port/
# interface handled separately).
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

# Embedded-Granian kwarg translation: the embedded server spells several
# options differently from the multiprocess one, and has no answer at all
# for supervisor concerns (respawn, pid file, loop choice — the caller's
# loop is the point). Accepted-but-untranslatable keys are dropped with a
# warning naming them, never silently.
_GRANIAN_EMBED_RENAMES: dict[str, str] = {
    "threads": "blocking_threads",
    "log_config": "log_dictconfig",
    "access_log": "log_access",
    "access_log_fmt": "log_access_format",
    "ssl_certificate": "ssl_cert",
    "ssl_keyfile": "ssl_key",
    "ssl_keyfile_password": "ssl_key_password",
    "path_prefix": "url_path_prefix",
}
_GRANIAN_EMBED_PASSTHROUGH: frozenset[str] = frozenset(
    {
        "blocking_threads",
        "runtime_threads",
        "runtime_blocking_threads",
        "backlog",
        "backpressure",
        "task_impl",
        "log_level",
        "ssl_ca",
        "ssl_crl",
        "ssl_client_verify",
        "url_path_prefix",
    }
)

#: Backends this runner can dispatch. ``web.server.backend`` advertises
#: exactly these; anything else is an error, not a fallback.
_SUPPORTED_BACKENDS: tuple[str, ...] = ("granian", "uvicorn", "hypercorn", "gunicorn")

# Auto-preference order when no backend is configured.
_PREFERRED_BACKENDS: tuple[str, ...] = ("granian", "uvicorn")


def _resolve_backend(app: Any) -> str:
    """Resolve the ASGI server backend.

    Reads ``web.server.backend`` from ``application.yaml`` via the app
    config. Falls back to auto-preference (granian → uvicorn) when the
    config is absent, and — with a warning — when the requested backend
    is not installed: backends are optional dependencies, so a config
    naming one the environment lacks must degrade, not brick boot.
    """
    config = getattr(app, "config", None)
    if config is not None:
        try:
            from quadkit.web.config import WebConfig

            web = config.get_section("web", WebConfig)
            requested = str(web.server.backend)
            if _is_available(requested):
                return requested
            logger.warning(
                "requested_backend_unavailable_fallback",
                backend=requested,
                hint=(
                    "install the backend package or change "
                    "web.server.backend; serving with the auto-preferred "
                    "backend instead"
                ),
            )
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


def _to_import_string(app: Any, *, factory: bool = True) -> str | None:
    """Derive an import string (``module:attr``) for *app*, or ``None``.

    Multiprocess servers cannot serve an object from this process; each
    worker imports its own. With ``factory=True`` (Granian MP) the string
    names a ``create_app`` factory; with ``factory=False`` (Gunicorn) it
    names a module-level ``app`` instance. The caller's frames are walked
    for a module exposing the wanted attribute — the conventional
    ``main.py`` shape qualifies on both counts.

    There is deliberately no class-path fallback: inventing
    ``quadkit.app.base:Application`` would let a factory-mode server
    construct and serve a blank application, which is worse than admitting
    the string cannot be derived and letting the caller fall back.
    """
    attr = "create_app" if factory else "app"
    try:
        frame = inspect.currentframe()
        try:
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
                        obj = getattr(mod, attr, None)
                        if factory and callable(obj):
                            return f"{caller_module}:create_app"
                        if (
                            not factory
                            and obj is not None
                            and not inspect.isfunction(obj)
                            and not inspect.isclass(obj)
                        ):
                            return f"{caller_module}:app"
                    except ImportError:
                        continue
        finally:
            del frame
    except (AttributeError, TypeError):
        return None
    return None


def _resolve_target(app: Any) -> tuple[Any, bool]:
    """Resolve *app* to ``(target, is_factory)`` for in-loop servers.

    Embedded Granian and Hypercorn serve objects, not import strings, so
    a ``"module:attr"`` string is imported here: a function or class is a
    factory (called to produce the ASGI app), anything else is the app
    instance itself. A non-string *app* is the instance.
    """
    if not isinstance(app, str):
        return app, False
    module_name, sep, attr_path = app.partition(":")
    if not sep or not attr_path:
        raise ValueError(
            f"Invalid app import string {app!r}; expected 'module:attribute'."
        )
    import importlib

    obj: Any = importlib.import_module(module_name)
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    return obj, inspect.isfunction(obj) or inspect.isclass(obj)


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
    blocking the loop. Multiprocess serving lives here: Granian's
    supervisor (with configured ``workers``/``reload`` forwarded), or
    Gunicorn as a subprocess.

    Args:
        app: ASGI application instance or import string (``"module:attr"``).
        host: Bind address. Reads from ``app.config.web.server.host``
            when not provided.
        port: Bind port. Reads from ``app.config.web.server.port``
            when not provided.
        **kwargs: Additional server arguments. ``workers``/``reload``
            fall back to ``web.server`` config when not given. For
            Granian, only accepted kwargs are forwarded; dropped keys
            are logged.

    Raises:
        RuntimeError: If called from an async context (use
            :func:`run_server_async` instead), or the configured backend
            is not one this runner supports.
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

    Async entry point: Uvicorn and Hypercorn serve in the calling loop,
    Granian serves embedded in the calling loop (actual app object,
    single worker, programmatic stop), and Gunicorn runs as a subprocess
    awaited off-loop. In-loop serving is single-process by definition —
    configured ``workers > 1``/``reload`` are ignored with a warning;
    use :func:`run_server` from the main thread (or the CLI) for
    multiprocess serving. This must be called from a running event loop.

    Args:
        app: ASGI application instance or import string (``"module:attr"``).
        host: Bind address. Reads from ``app.config.web.server.host``
            when not provided.
        port: Bind port. Reads from ``app.config.web.server.port``
            when not provided.
        **kwargs: Additional server arguments. For Granian, kwargs are
            translated to the embedded server's spellings; keys with no
            embedded equivalent are dropped and logged.

    Raises:
        RuntimeError: If no event loop is running, or the configured
            backend is not one this runner supports.
        ImportError: If the resolved server backend is not installed.
    """
    loop = asyncio.get_running_loop()
    await _run_in_loop(loop, app, host, port, **kwargs)


def _unsupported_backend(backend: str) -> RuntimeError:
    return RuntimeError(
        f"Unsupported ASGI server backend {backend!r}; supported backends "
        f"are {', '.join(_SUPPORTED_BACKENDS)}. Set web.server.backend to "
        "one of those, or remove it to use auto-preference."
    )


def _warn_in_loop_limits(backend: str, workers: int, reload_: bool) -> None:
    """Say out loud that in-loop serving cannot honour workers/reload."""
    if workers > 1:
        logger.warning(
            "server_workers_ignored_in_loop",
            backend=backend,
            workers=workers,
            hint=(
                "in-loop serving is single-process; use run_server() from "
                "the main thread or the quadkit CLI for multiprocess serving"
            ),
        )
    if reload_:
        logger.warning(
            "server_reload_ignored_in_loop",
            backend=backend,
            hint=(
                "reload needs a supervising process; use run_server() "
                "from the main thread or the quadkit CLI dev command"
            ),
        )


async def _run_in_loop(
    loop: asyncio.AbstractEventLoop,
    app: Any,
    host: str | None,
    port: str | int | None,
    **kwargs: Any,
) -> None:
    """Dispatch from within a running event loop."""
    backend = _resolve_backend(app)
    host, port, cfg_workers, cfg_reload = _resolve_web_settings(app, host, port)
    workers = int(kwargs.pop("workers", cfg_workers))
    reload_ = bool(kwargs.pop("reload", cfg_reload))

    if backend == "uvicorn":
        _warn_in_loop_limits(backend, workers, reload_)
        await _run_uvicorn_async(app, host, port, **kwargs)
        return

    if backend == "granian":
        await _run_granian_embedded(
            app, host, port, workers=workers, reload_=reload_, **kwargs
        )
        return

    if backend == "hypercorn":
        _warn_in_loop_limits(backend, workers, reload_)
        await _run_hypercorn_async(app, host, port, **kwargs)
        return

    if backend == "gunicorn":
        await loop.run_in_executor(
            None,
            lambda: _run_gunicorn(
                app, host, port, workers=workers, reload_=reload_, **kwargs
            ),
        )
        return

    raise _unsupported_backend(backend)


def _run_sync(
    app: Any,
    host: str | None,
    port: str | int | None,
    **kwargs: Any,
) -> None:
    """Dispatch from sync context (no event loop running)."""
    host, port, cfg_workers, cfg_reload = _resolve_web_settings(app, host, port)
    workers = int(kwargs.pop("workers", cfg_workers))
    reload_ = bool(kwargs.pop("reload", cfg_reload))

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
            filtered = _filter_granian_kwargs(kwargs)
            filtered.setdefault("workers", workers)
            filtered.setdefault("reload", reload_)
            _run_granian(import_str, host, port, **filtered)
    elif backend == "gunicorn":
        _run_gunicorn(app, host, port, workers=workers, reload_=reload_, **kwargs)
    elif backend == "hypercorn":
        _warn_in_loop_limits(backend, workers, reload_)
        _run_hypercorn(app, host, port, **kwargs)
    elif backend == "uvicorn":
        _warn_in_loop_limits(backend, workers, reload_)
        _run_uvicorn(app, host, port, **kwargs)
    else:
        raise _unsupported_backend(backend)


def _resolve_web_settings(
    app: Any, host: str | None, port: str | int | None
) -> tuple[str, int, int, bool]:
    """Read host/port/workers/reload from app.config where not provided.

    Explicit arguments win over config; config wins over the defaults
    (``127.0.0.1``, ``8000``, 1 worker, no reload). Before 2026-10-24
    only host/port were read, so ``web.server.workers`` in
    ``application.yaml`` was silently decorative.
    """
    workers, reload_ = 1, False
    config = getattr(app, "config", None)
    if config is None:
        return host or "127.0.0.1", int(port or 8000), workers, reload_
    try:
        from quadkit.web.config import WebConfig

        web = config.get_section("web", WebConfig)
        return (
            host or web.server.host,
            int(port or web.server.port),
            int(web.server.workers),
            bool(web.server.reload),
        )
    except Exception:
        return host or "127.0.0.1", int(port or 8000), workers, reload_


def _resolve_web_config(
    app: Any, host: str | None, port: str | int | None
) -> tuple[str, int]:
    """Read host/port from app.config when not explicitly provided."""
    resolved_host, resolved_port, _workers, _reload = _resolve_web_settings(
        app, host, port
    )
    return resolved_host, resolved_port


def _filter_granian_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Forward only kwargs Granian accepts; name what was dropped."""
    filtered = {k: v for k, v in kwargs.items() if k in _GRANIAN_ACCEPTED}
    dropped = sorted(set(kwargs) - set(filtered))
    if dropped:
        logger.warning("granian_kwargs_dropped", keys=dropped)
    return filtered


def _run_granian(
    app: str,
    host: str,
    port: int,
    **kwargs: Any,
) -> None:
    """Run via Granian's multiprocess supervisor (main thread only)."""
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


def _translate_embed_kwargs(kwargs: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Translate multiprocess-Granian kwargs to embedded spellings."""
    translated: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in kwargs.items():
        if key in _GRANIAN_EMBED_PASSTHROUGH:
            translated[key] = value
        elif key in _GRANIAN_EMBED_RENAMES:
            translated.setdefault(_GRANIAN_EMBED_RENAMES[key], value)
        else:
            dropped.append(key)
    return translated, dropped


async def _run_granian_embedded(
    app: Any,
    host: str,
    port: int,
    *,
    workers: int = 1,
    reload_: bool = False,
    **kwargs: Any,
) -> None:
    """Run via Granian's embedded server in the calling loop.

    The embedded server is the async path's Granian: it serves the app
    object itself (or a factory's product), installs no signal handlers,
    speaks ASGI lifespan, and stops when told to. Supervisor features
    (workers, reload, respawn, pid file) do not exist in this mode —
    asking for them is warned about, not simulated.
    """
    try:
        embed = _load_backend("granian.server.embed")
        granian_constants = _load_backend("granian.constants")
    except (ImportError, ModuleNotFoundError) as e:
        raise ImportError(
            "Granian is not installed. Install 'granian' to use this backend.",
        ) from e

    _warn_in_loop_limits("granian", workers, reload_)
    accepted = _filter_granian_kwargs(kwargs)
    translated, dropped = _translate_embed_kwargs(accepted)
    if dropped:
        logger.warning(
            "granian_embed_kwargs_dropped",
            keys=sorted(dropped),
            hint="these options belong to the multiprocess supervisor; use run_server() for them",
        )

    target, factory = _resolve_target(app)
    logger.info(
        "starting_granian_embedded_server", host=host, port=port, kwargs=translated
    )
    server = embed.Server(
        target,
        address=host,
        port=port,
        interface=granian_constants.Interfaces.ASGI,
        factory=factory,
        **translated,
    )
    serve_task = asyncio.ensure_future(server.serve())
    try:
        await serve_task
    except asyncio.CancelledError:
        # The caller is going away; stop the server deterministically
        # instead of abandoning its worker tasks mid-flight.
        server.stop()
        with contextlib.suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(asyncio.shield(serve_task), timeout=10)
        raise


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


async def _run_hypercorn_async(
    app: Any,
    host: str,
    port: int,
    **kwargs: Any,
) -> None:
    """Run via Hypercorn's asyncio API in the calling loop.

    Hypercorn's ``serve`` installs no signal handlers (its CLI does), so
    shutdown arrives as cancellation of the awaiting task — matching the
    in-loop contract the other async backends follow.
    """
    try:
        hypercorn_asyncio = _load_backend("hypercorn.asyncio")
        hypercorn_config = _load_backend("hypercorn.config")
    except (ImportError, ModuleNotFoundError) as e:
        raise ImportError(
            "Hypercorn is not installed. Install 'hypercorn' to use this backend.",
        ) from e

    target, factory = _resolve_target(app)
    if factory:
        target = target()

    config = hypercorn_config.Config()
    config.bind = [f"{host}:{port}"]
    dropped: list[str] = []
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            dropped.append(key)
    if dropped:
        logger.warning("hypercorn_kwargs_dropped", keys=sorted(dropped))

    logger.info("starting_hypercorn_server", host=host, port=port, kwargs=kwargs)
    await hypercorn_asyncio.serve(target, config)


def _run_hypercorn(
    app: Any,
    host: str,
    port: int,
    **kwargs: Any,
) -> None:
    """Run via Hypercorn (sync context — creates its own event loop)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run_hypercorn_async(app, host, port, **kwargs))


def _run_gunicorn(
    app: Any,
    host: str,
    port: int,
    *,
    workers: int = 1,
    reload_: bool = False,
    **kwargs: Any,
) -> None:
    """Run via Gunicorn with Uvicorn workers (a subprocess).

    Signal handlers install in the child arbiter's main thread, so this
    is safe to await off-loop. The child needs an import string naming
    an app *instance* — Uvicorn workers have no factory flag here — so
    an underivable instance string is an error with instructions, not
    a silent backend swap.
    """
    import subprocess  # noqa: S404 — registry-built argv list

    _load_backend("gunicorn")

    if isinstance(app, str):
        target = app
    else:
        derived_target = _to_import_string(app, factory=False)
        if derived_target is None:
            raise RuntimeError(
                "The gunicorn backend runs in a subprocess and needs an "
                "import string naming an app instance ('module:app'); "
                "none could be derived from the given object. Pass the "
                "app as a string, or expose it as a module-level `app`."
            )
        target = derived_target

    cmd = [
        "gunicorn",
        "-w",
        str(workers),
        "-b",
        f"{host}:{port}",
        "-k",
        "uvicorn_worker.UvicornWorker",
    ]
    if reload_:
        cmd.append("--reload")
    cmd.append(target)

    logger.info(
        "starting_gunicorn_server", host=host, port=port, workers=workers, kwargs=kwargs
    )
    subprocess.run(cmd, check=False)  # noqa: S603


__all__ = ["run_server", "run_server_async"]
