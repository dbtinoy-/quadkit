"""MCP client transport protocol and concrete transport implementations."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

from quadkit.ai.mcp.exceptions import MCPTransportError
from quadkit.logging import get_logger, safe_error_type
from quadkit.serialization import dumps_str, loads

logger = get_logger(__name__)


@runtime_checkable
class MCPClientTransport(Protocol):
    """Protocol for outbound MCP transports.

    A transport is responsible for sending JSON-RPC requests to an external
    MCP server and returning the parsed JSON-RPC response.  Each call maps
    to one logical request-response pair; the transport handles any
    framing details (length-delimited lines, HTTP bodies, etc.).
    """

    async def connect(self) -> None:
        """Open the underlying connection (spawn process, open socket, etc.)."""
        ...

    async def disconnect(self) -> None:
        """Close the underlying connection and free resources."""
        ...

    async def send(self, message: dict[str, Any]) -> None:
        """Write a JSON-RPC message to the server.

        Args:
            message: Fully-formed JSON-RPC request or notification dict.
        """
        ...

    async def receive(self) -> dict[str, Any]:
        """Read and return the next JSON-RPC message from the server.

        Returns:
            Parsed JSON-RPC response dict.

        Raises:
            MCPTransportError: On I/O failure or malformed data.
        """
        ...


# ---------------------------------------------------------------------------
# Stdio transport  (subprocess  stdin ↔ stdout)
# ---------------------------------------------------------------------------


class StdioClientTransport:
    """MCP client transport that communicates with a subprocess via stdio.

    Spawns *command* as an asyncio subprocess and exchanges newline-delimited
    JSON-RPC messages over its stdin/stdout pipes.

    Args:
        command: The command and arguments to launch the MCP server process.
        env: Optional extra environment variables to pass to the subprocess.
            If *None*, the current process environment is inherited.
        startup_timeout: Seconds to wait for the process to start before
            raising :exc:`~quadkit.ai.mcp.exceptions.MCPTransportError`.
    """

    def __init__(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        startup_timeout: float = 10.0,
    ) -> None:
        if not command:
            raise ValueError("command must not be empty")
        self._command = command
        self._env = env
        self._startup_timeout = startup_timeout
        self._process: asyncio.subprocess.Process | None = None

    async def connect(self) -> None:
        """Spawn the subprocess."""
        try:
            self._process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *self._command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=self._env,
                ),
                timeout=self._startup_timeout,
            )
            logger.info("mcp_stdio_client_connected")
        except TimeoutError:
            raise MCPTransportError(
                message="Timed out spawning MCP server",
                transport_type="stdio",
            ) from None
        except (OSError, FileNotFoundError) as exc:
            raise MCPTransportError(
                message=f"Failed to spawn MCP server ({safe_error_type(exc)})",
                transport_type="stdio",
            ) from None

    async def disconnect(self) -> None:
        """Terminate the subprocess."""
        if self._process is None:
            return
        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except (TimeoutError, ProcessLookupError):
            self._process.kill()
        finally:
            self._process = None
            logger.info("mcp_stdio_client_disconnected")

    async def send(self, message: dict[str, Any]) -> None:
        """Write a newline-delimited JSON message to the subprocess stdin."""
        if self._process is None or self._process.stdin is None:
            raise MCPTransportError(
                message="Transport not connected",
                transport_type="stdio",
            )
        try:
            data = (dumps_str(message) + "\n").encode()
            self._process.stdin.write(data)
            await self._process.stdin.drain()
        except (OSError, BrokenPipeError) as exc:
            raise MCPTransportError(
                message=f"Failed to send to MCP server ({safe_error_type(exc)})",
                transport_type="stdio",
            ) from None

    async def receive(self) -> dict[str, Any]:
        """Read a newline-delimited JSON message from subprocess stdout."""
        if self._process is None or self._process.stdout is None:
            raise MCPTransportError(
                message="Transport not connected",
                transport_type="stdio",
            )
        try:
            line = await self._process.stdout.readline()
            if not line:
                raise MCPTransportError(
                    message="MCP server closed the connection",
                    transport_type="stdio",
                )
            return loads(line.decode().strip())
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise MCPTransportError(
                message=f"Failed to receive from MCP server ({safe_error_type(exc)})",
                transport_type="stdio",
            ) from None


# ---------------------------------------------------------------------------
# SSE / HTTP transport
# ---------------------------------------------------------------------------


class SSEClientTransport:
    """MCP client transport that communicates with an HTTP+SSE MCP server.

    Sends JSON-RPC requests as HTTP POST bodies and reads the responses from
    the response body.  Uses ``aiohttp`` for async HTTP — ensure it is
    installed (``pip install aiohttp`` or the ``http`` extra of this package).

    Args:
        url: Base URL of the MCP HTTP endpoint (e.g. ``http://localhost:8080/mcp``).
        headers: Additional HTTP headers to include with every request (e.g.
            ``{"Authorization": "Bearer <token>"}``.
        request_timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        request_timeout: float = 30.0,
    ) -> None:
        self._url = url
        self._extra_headers = headers or {}
        self._timeout = request_timeout
        self._session: Any = None  # aiohttp.ClientSession lazily imported
        self._pending_send: dict[str, Any] | None = None

    async def connect(self) -> None:
        """Open an aiohttp session."""
        try:
            import aiohttp
        except ImportError:
            raise MCPTransportError(
                message=(
                    "SSEClientTransport requires aiohttp. "
                    "Install it with: pip install aiohttp"
                ),
                transport_type="sse",
            ) from None

        self._session = aiohttp.ClientSession(
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **self._extra_headers,
            },
            timeout=aiohttp.ClientTimeout(total=self._timeout),
        )
        logger.info("mcp_sse_client_connected")

    async def disconnect(self) -> None:
        """Close the aiohttp session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("mcp_sse_client_disconnected")

    async def send(self, message: dict[str, Any]) -> None:
        """Queue *message* for the next :meth:`receive` call via HTTP POST."""
        # For HTTP transport, send and receive are paired — store pending message.
        self._pending_send = message

    async def receive(self) -> dict[str, Any]:
        """POST the pending request and return the parsed JSON-RPC response."""
        if self._session is None:
            raise MCPTransportError(
                message="Transport not connected",
                transport_type="sse",
            )
        message = getattr(self, "_pending_send", None)
        if message is None:
            raise MCPTransportError(
                message="receive() called before send()",
                transport_type="sse",
            )
        try:
            async with self._session.post(self._url, json=message) as resp:
                if resp.status >= 400:
                    raise MCPTransportError(
                        message=(f"MCP server returned HTTP {resp.status}"),
                        transport_type="sse",
                    )
                return await resp.json()
        except MCPTransportError:
            raise
        except Exception as exc:  # noqa: BLE001 — any SSE/HTTP failure is a MCPTransportError
            raise MCPTransportError(
                message=f"HTTP request to MCP server failed ({safe_error_type(exc)})",
                transport_type="sse",
            ) from None


__all__ = ["MCPClientTransport", "SSEClientTransport", "StdioClientTransport"]
