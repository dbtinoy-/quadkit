"""MCP server management commands for the Quadkit CLI."""

from __future__ import annotations

import ast
import asyncio
import importlib
from pathlib import Path
import sys
from typing import Annotated

import typer

import quadkit.serialization as json

# ---------------------------------------------------------------------------
# Entry-point discovery helpers (inlined from quadkit-cli to avoid
# cross-extension imports — quadkit-ai-mcp must not import quadkit-cli)
# ---------------------------------------------------------------------------


def _path_to_module(file_path: str) -> str:
    """Convert a file path to a dotted Python module string."""
    p = Path(file_path)
    parts = list(p.with_suffix("").parts)
    # Drop "." / ".." / separator components — an absolute path's parts
    # start with "/", which would join into an invalid module name.
    parts = [part for part in parts if part not in (".", "..", "/")]
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


def _detect_factory_attr(file_path: str) -> str | None:
    """Return the first recognisable callable attr name in *file_path*."""
    try:
        source = Path(file_path).read_text()
        tree = ast.parse(source)
    except Exception:  # noqa: BLE001 — a bad config file is treated as absent
        return None

    top_level: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            top_level.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    top_level.add(t.id)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                top_level.add(alias.asname if alias.asname else alias.name)

    for candidate in ("create_app", "app", "asgi_app"):
        if candidate in top_level:
            return candidate
    return None


def _discover_entry_point() -> str | None:
    """Discover application entry point from common locations."""
    candidates = [
        Path("src/main.py"),
        Path("main.py"),
        Path("app.py"),
        Path("src/app.py"),
    ]
    src_path = Path("src")
    if src_path.exists():
        candidates.extend(src_path.rglob("main.py"))
        candidates.extend(src_path.rglob("app.py"))
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def create_mcp_app() -> typer.Typer:
    """Factory for the 'mcp' command group — called lazily by CommandAssembler."""
    app = typer.Typer(name="mcp", help="MCP server management commands")
    app.command("serve")(serve)
    return app


def _resolve_entry_point(target: str | None) -> str:
    """Resolve target to a 'module:attr' string, auto-detecting when needed.

    Args:
        target: Explicit ``module:attr`` or file path, or ``None`` for auto-detect.

    Returns:
        Resolved ``module:attr`` string.
    """
    if target and ":" in target:
        return target

    file_path = target if target else _discover_entry_point()
    if not file_path or not Path(file_path).exists():
        typer.echo(
            "Error: Could not find an application entry point.\n"
            "Hint: Specify it as 'my_app.app:create_app' or run from your project root.",
            err=True,
        )
        raise typer.Exit(1)

    attr = _detect_factory_attr(file_path)
    if not attr:
        typer.echo(
            f"Error: No ASGI app or factory found in {file_path}.\n"
            "Hint: Define 'app', 'asgi_app', or 'create_app' at module level.",
            err=True,
        )
        raise typer.Exit(1)

    module = _path_to_module(file_path)
    entry_point = f"{module}:{attr}"
    typer.echo(f"Detected entry point: {entry_point}", err=True)
    return entry_point


def _load_app(entry_point: str) -> object:
    """Import the factory, call it if callable, and return the Application.

    Args:
        entry_point: ``module:attr`` string pointing to a factory or app.

    Returns:
        The Quadkit Application instance.
    """
    module_path, _, attr_name = entry_point.partition(":")
    module = importlib.import_module(module_path)
    factory_or_app = getattr(module, attr_name)
    return factory_or_app() if callable(factory_or_app) else factory_or_app


async def _serve_stdio(mcp_server: object) -> None:
    """Run the MCP JSON-RPC server loop on stdin / stdout.

    Reads newline-delimited JSON-RPC messages from stdin, processes each
    via ``mcp_server``, and writes responses to stdout.

    Args:
        mcp_server: A resolved MCPServer instance.
    """
    import asyncio

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    transport, _ = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
    )
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            stripped = line.strip()
            if not stripped:
                continue
            try:
                message = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            response = await mcp_server.handle_message(message)  # type: ignore[attr-defined]
            if response is not None:
                # dumps() returns bytes — print would emit the b'...' repr
                # and corrupt the JSON-RPC stream on stdout.
                print(json.dumps_str(response), flush=True)
    finally:
        transport.close()


async def _serve_sse(mcp_server: object, host: str, port: int) -> None:
    """Run a minimal HTTP server exposing MCP JSON-RPC over POST /mcp.

    Implements a bare-asyncio HTTP server — no third-party web framework
    required.  The MCP client POSTs JSON-RPC requests to ``POST /mcp``.

    The server is loopback-oriented by design: requests carrying an
    ``Origin`` header are accepted only when the origin's host is a
    loopback address (``127.0.0.1`` / ``localhost`` / ``::1``), and the
    allowed origin is echoed back instead of ``*``.  This prevents a
    random webpage from driving the local MCP server (and reading its
    responses) via cross-origin ``text/plain`` POSTs, which otherwise
    bypass CORS preflight.  Non-browser clients without an ``Origin``
    header are unaffected.

    Args:
        mcp_server: A resolved MCPServer instance.
        host: Bind host.
        port: Bind port.
    """
    import asyncio

    async def _handle(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await _handle_http_connection(reader, writer, mcp_server)

    server = await asyncio.start_server(_handle, host, port)
    async with server:
        await server.serve_forever()


def _is_loopback_origin(origin: str) -> bool:
    """Return True when the Origin header's host is a loopback address."""
    from urllib.parse import urlsplit

    try:
        hostname = urlsplit(origin).hostname or ""
    except ValueError:
        return False
    return hostname in ("127.0.0.1", "localhost", "::1")


async def _handle_http_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    mcp_server: object,
) -> None:
    """Serve one HTTP request/response exchange for the SSE transport."""
    try:
        request_line = await reader.readline()
        if not request_line:
            return

        headers: dict[str, str] = {}
        while True:
            hdr = await reader.readline()
            if hdr in (b"\r\n", b"\n", b""):
                break
            if b":" in hdr:
                key, _, val = hdr.decode(errors="replace").partition(":")
                headers[key.strip().lower()] = val.strip()

        content_length = int(headers.get("content-length", 0))
        body = await reader.read(content_length) if content_length else b""

        parts = request_line.decode(errors="replace").split(" ", 2)
        method = parts[0] if parts else ""

        origin = headers.get("origin", "")
        if origin and not _is_loopback_origin(origin):
            writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            return

        cors_headers = b""
        if origin:
            cors_headers = (
                f"Access-Control-Allow-Origin: {origin}\r\n"
                "Vary: Origin\r\n"
                "Access-Control-Allow-Methods: POST, OPTIONS\r\n"
                "Access-Control-Allow-Headers: Content-Type\r\n"
            ).encode()

        if method == "OPTIONS":
            writer.write(
                b"HTTP/1.1 204 No Content\r\n"
                + cors_headers
                + b"Connection: close\r\n\r\n"
            )
            return

        if method == "POST" and body:
            try:
                message = json.loads(body)
                response = await mcp_server.handle_message(message)  # type: ignore[attr-defined]
                if response is not None:
                    response_body = json.dumps(response)
                    writer.write(
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: application/json\r\n"
                        + cors_headers
                        + f"Content-Length: {len(response_body)}\r\n".encode()
                        + b"Connection: close\r\n\r\n"
                        + response_body
                    )
                else:
                    writer.write(
                        b"HTTP/1.1 204 No Content\r\n"
                        + cors_headers
                        + b"Connection: close\r\n\r\n"
                    )
            except json.JSONDecodeError:
                writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
        else:
            writer.write(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")
    except Exception:  # noqa: BLE001 — best-effort teardown must not raise
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001 — best-effort teardown must not raise
            pass


def _load_script_module(target: str) -> object:
    """Load a Python module from a file path or dotted name.

    Supports:
    - Absolute/relative ``.py`` file paths (``my_tools.py``, ``./tools.py``)
    - Dotted module names (``my_app.tools``)

    Args:
        target: File path or dotted module name.

    Returns:
        Imported Python module object.
    """
    import importlib
    import importlib.util

    if target.endswith(".py"):
        spec = importlib.util.spec_from_file_location(
            "_mcp_script", Path(target).resolve()
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load script: {target}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return importlib.import_module(target)


def _build_script_server(module: object) -> object:
    """Build a standalone MCPServer from a Python module's decorated functions.

    Scans *module* for ``@tool``, ``@resource``, ``@prompt`` decorated callables,
    constructs providers, and returns a ready-to-use ``MCPServer`` instance —
    no full Quadkit application required.

    Args:
        module: A Python module object containing decorated functions.

    Returns:
        A configured ``MCPServer`` instance.
    """
    from quadkit.ai.mcp.controllers import (
        ModulePromptProvider,
        ModuleResourceProvider,
        ModuleToolProvider,
    )
    from quadkit.ai.mcp.server import MCPServer
    from quadkit.ai.mcp.server.handlers import (
        PromptHandler,
        ResourceHandler,
        ToolHandler,
    )

    tool_provider = ModuleToolProvider.from_module(module)
    resource_provider = ModuleResourceProvider.from_module(module)
    prompt_provider = ModulePromptProvider.from_module(module)

    return MCPServer(
        name=getattr(module, "__mcp_name__", getattr(module, "__name__", "mcp-script")),
        version=getattr(module, "__mcp_version__", "1.0.0"),
        tool_handler=ToolHandler(tool_provider),
        resource_handler=ResourceHandler(resource_provider),
        prompt_handler=PromptHandler(prompt_provider),
        allow_unauthenticated=True,
    )


def _is_script_target(target: str) -> bool:
    """Return True if *target* should be treated as a script module.

    A target is a script when:
    - It ends with ``.py`` (explicit file), or
    - It contains no ``:`` (no factory separator) AND does not point
      to an auto-detectable app factory.

    Args:
        target: The target string from the CLI argument.

    Returns:
        ``True`` if the target should be loaded in script mode.
    """
    if target.endswith(".py"):
        return True
    if ":" in target:
        return False
    attr = _detect_factory_attr(target) if Path(target).exists() else None
    return attr is None


def _route_logs_to_stderr() -> None:
    """Send structlog output to stderr.

    structlog's default ``PrintLoggerFactory`` writes to stdout, which
    corrupts the newline-delimited JSON-RPC stream of the stdio transport.
    """
    import structlog

    _cfg = structlog.get_config()
    structlog.configure(
        processors=_cfg.get("processors", []),
        context_class=_cfg.get("context_class", dict),
        wrapper_class=_cfg.get("wrapper_class", structlog.BoundLogger),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=_cfg.get("cache_logger_on_first_use", True),
    )


def serve(
    target: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Module:attr entry point (e.g. my_app.app:create_app), "
                "a .py script file (e.g. tools.py), "
                "or a dotted module name with @tool-decorated functions. "
                "Auto-detected if omitted."
            )
        ),
    ] = None,
    transport: Annotated[
        str,
        typer.Option(
            "--transport",
            "-t",
            help="Transport protocol: 'stdio' (default) or 'sse'.",
        ),
    ] = "stdio",
    host: Annotated[
        str,
        typer.Option("--host", help="Bind host for SSE transport."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Bind port for SSE transport."),
    ] = 8001,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Config profile (sets QK_PROFILE)."),
    ] = None,
) -> None:
    """Start an MCP server backed by your Quadkit application or a script file.

    Three invocation modes:

    **App mode** — loads a full Quadkit application and serves its MCP module::

        quadkit mcp serve                        # auto-detect
        quadkit mcp serve my_app.app:create_app  # explicit entry point

    **Script mode** — loads a .py file or module with @tool-decorated functions,
    no application required::

        quadkit mcp serve tools.py               # from a file
        quadkit mcp serve my_app.mcp_tools       # from a dotted module

    **Transport options**::

        quadkit mcp serve                        # stdio (Claude Desktop)
        quadkit mcp serve --transport sse        # HTTP port 8001
    """
    import asyncio
    import os

    try:
        if transport not in ("stdio", "sse"):
            typer.echo(
                f"Error: Unknown transport: {transport!r}\n"
                "Hint: Supported transports: stdio, sse",
                err=True,
            )
            raise typer.Exit(1)

        if transport == "stdio":
            _route_logs_to_stderr()

        if transport == "sse" and host not in ("127.0.0.1", "localhost", "::1"):
            # The SSE endpoint is unauthenticated by design and the origin
            # check only filters browser clients — flag network exposure.
            typer.echo(
                "Warning: binding the MCP SSE server to a non-loopback host "
                "exposes the JSON-RPC endpoint to the network",
                err=True,
            )

        if profile:
            os.environ["QK_PROFILE"] = profile
            typer.echo(f"Profile: {profile}", err=True)

        if target is not None and _is_script_target(target):
            typer.echo(f"Script mode: loading {target}", err=True)

            async def _run_script() -> None:
                module = _load_script_module(target)
                mcp_server = _build_script_server(module)

                if transport == "stdio":
                    typer.echo(
                        "MCP server started (stdio transport — reading from stdin)",
                        err=True,
                    )
                    await _serve_stdio(mcp_server)
                else:
                    typer.echo(
                        f"MCP server started (SSE transport — listening on {host}:{port})",
                        err=True,
                    )
                    await _serve_sse(mcp_server, host, port)

            asyncio.run(_run_script())
            return

        entry_point = _resolve_entry_point(target)

        async def _run() -> None:
            from quadkit.app.runner import start_application, stop_application

            quadkit_app = _load_app(entry_point)
            await start_application(quadkit_app)  # type: ignore[arg-type]
            if transport == "stdio":
                _route_logs_to_stderr()
            try:
                mcp_server = quadkit_app.container.resolve(  # type: ignore[attr-defined]
                    "quadkit.ai.mcp.server.core.MCPServer"
                )

                if transport == "stdio":
                    typer.echo(
                        "MCP server started (stdio transport — reading from stdin)"
                    )
                    await _serve_stdio(mcp_server)
                else:
                    typer.echo(
                        f"MCP server started (SSE transport — listening on {host}:{port})"
                    )
                    typer.echo(f"POST JSON-RPC requests to http://{host}:{port}/mcp")
                    await _serve_sse(mcp_server, host, port)
            finally:
                await stop_application(quadkit_app)  # type: ignore[arg-type]

        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error ({type(exc).__name__})", err=True)
        raise typer.Exit(1) from None
