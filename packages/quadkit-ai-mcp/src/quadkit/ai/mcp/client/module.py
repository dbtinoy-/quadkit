"""MCPClientModule — consume external MCP servers as DI injectables.

An ``MCPClientModule`` registers one or more :class:`MCPClient` instances
in the DI container so that application services can call external MCP
servers without managing connection lifecycle manually.

Each connection is described by an :class:`MCPConnection` dataclass.  Named
connections are exposed via a single :class:`MCPClientRegistry` injectable,
and the *first* connection is also registered directly as ``MCPClient`` for
single-connection use cases.

Basic usage::

    from quadkit.ai.mcp import MCPClientModule, MCPConnection

    app = QuadkitApplication(
        modules=[
            MCPClientModule.configure(
                connections=[
                    MCPConnection.stdio(
                        ["uvx", "mcp-server-git", "--repository", "/repo"],
                        name="git",
                    ),
                    MCPConnection.sse(
                        "http://localhost:8080/mcp",
                        name="analytics",
                    ),
                ]
            ),
        ],
    )

    # Inject in services:
    class ReportService:
        def __init__(self, registry: MCPClientRegistry) -> None:
            self._git = registry.get("git")
            self._analytics = registry.get("analytics")

    # Single-connection shorthand — MCPClient is registered directly:
    class SimpleService:
        def __init__(self, mcp: MCPClient) -> None:
            self._mcp = mcp
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quadkit.ai.mcp.client.core import (
    MCPClient,
    SSEClientTransport,
    StdioClientTransport,
)
from quadkit.contracts import (
    ProviderPriority,
)
from quadkit.di.module import Module
from quadkit.di.provider import Provider
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


# ── MCPConnection ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MCPConnection:
    """Immutable description of one external MCP server connection.

    Do not construct directly — use the :meth:`stdio` or :meth:`sse` class
    methods.

    Attributes:
        name: Unique identifier for this connection used by
              :class:`MCPClientRegistry`.
        transport_type: ``"stdio"`` or ``"sse"``.
        command: (stdio only) Subprocess command to launch the MCP server.
        url: (sse only) Base HTTP URL of the MCP server.
        env: (stdio only) Optional extra environment variables.
        headers: (sse only) Optional extra HTTP headers.
        request_timeout: Per-request timeout in seconds (default 30).
        startup_timeout: (stdio only) Wait timeout for process start (default 10).
    """

    name: str
    transport_type: str
    command: list[str] = field(default_factory=list)
    url: str = ""
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    request_timeout: float = 30.0
    startup_timeout: float = 10.0

    @classmethod
    def stdio(
        cls,
        command: list[str],
        *,
        name: str,
        env: dict[str, str] | None = None,
        startup_timeout: float = 10.0,
        request_timeout: float = 30.0,
    ) -> MCPConnection:
        """Create a connection that communicates with a stdio-based MCP server.

        Spawns *command* as a subprocess and exchanges newline-delimited
        JSON-RPC messages over its stdin/stdout.

        Args:
            command: The command and arguments to launch the MCP server.
            name: Unique name for use with :class:`MCPClientRegistry`.
            env: Optional extra environment variables.
            startup_timeout: Seconds to wait for process start.
            request_timeout: Per-request timeout in seconds.

        Returns:
            A configured ``MCPConnection`` describing this stdio server.

        Example::

            MCPConnection.stdio(
                ["uvx", "mcp-server-git", "--repository", "/repo"],
                name="git",
            )
        """
        if not command:
            raise ValueError("command must not be empty for stdio connections")
        return cls(
            name=name,
            transport_type="stdio",
            command=list(command),
            env=env,
            startup_timeout=startup_timeout,
            request_timeout=request_timeout,
        )

    @classmethod
    def sse(
        cls,
        url: str,
        *,
        name: str,
        headers: dict[str, str] | None = None,
        request_timeout: float = 30.0,
    ) -> MCPConnection:
        """Create a connection to an HTTP+SSE MCP server.

        Args:
            url: Base URL of the MCP server (e.g. ``http://localhost:8080/mcp``).
            name: Unique name for use with :class:`MCPClientRegistry`.
            headers: Optional extra HTTP headers (e.g. auth tokens).
            request_timeout: Per-request timeout in seconds.

        Returns:
            A configured ``MCPConnection`` describing this SSE server.

        Example::

            MCPConnection.sse(
                "http://localhost:8080/mcp",
                name="analytics",
                headers={"Authorization": "Bearer secret"},
            )
        """
        if not url:
            raise ValueError("url must not be empty for sse connections")
        return cls(
            name=name,
            transport_type="sse",
            url=url,
            headers=headers,
            request_timeout=request_timeout,
        )

    def build_transport(self) -> Any:
        """Instantiate and return the appropriate transport for this connection.

        Returns:
            A :class:`~quadkit.ai.mcp.client.StdioClientTransport` or
            :class:`~quadkit.ai.mcp.client.SSEClientTransport` instance.

        Raises:
            ValueError: If *transport_type* is not ``"stdio"`` or ``"sse"``.
        """
        if self.transport_type == "stdio":
            return StdioClientTransport(
                self.command,
                env=self.env,
                startup_timeout=self.startup_timeout,
            )
        if self.transport_type == "sse":
            return SSEClientTransport(
                self.url,
                headers=self.headers,
                request_timeout=self.request_timeout,
            )
        raise ValueError(
            f"Unknown MCPConnection transport_type: {self.transport_type!r}. "
            "Use MCPConnection.stdio() or MCPConnection.sse()."
        )

    def build_client(self) -> MCPClient:
        """Build an :class:`MCPClient` from this connection description.

        Returns:
            An unconnected :class:`MCPClient` ready for use.
        """
        return MCPClient(
            self.build_transport(),
            request_timeout=self.request_timeout,
        )


# ── MCPClientRegistry ────────────────────────────────────────────────────────


class MCPClientRegistry:
    """Registry of named :class:`MCPClient` instances.

    Registered in the DI container by :class:`MCPClientModule`.  Inject this
    in services that need to call multiple external MCP servers::

        class ReportService:
            def __init__(self, registry: MCPClientRegistry) -> None:
                self._git = registry.get("git")
                self._analytics = registry.get("analytics")

    Call :meth:`MCPClient.connect` before making requests (or use the client
    as an async context manager for automatic lifecycle management).
    """

    def __init__(self, clients: dict[str, MCPClient]) -> None:
        """Initialize with a pre-built mapping of names → clients.

        Args:
            clients: Dict mapping each connection name to its
                     :class:`MCPClient` instance.
        """
        self._clients: dict[str, MCPClient] = dict(clients)

    def get(self, name: str) -> MCPClient:
        """Return the client registered under *name*.

        Args:
            name: The connection name passed to :meth:`MCPConnection.stdio`
                  or :meth:`MCPConnection.sse`.

        Returns:
            The corresponding :class:`MCPClient`.

        Raises:
            KeyError: If no client was registered with the given *name*.
        """
        if name not in self._clients:
            available = ", ".join(self._clients.keys()) or "(none)"
            raise KeyError(
                f"MCP connection {name!r} not found. Available connections: {available}"
            )
        return self._clients[name]

    def names(self) -> list[str]:
        """Return the names of all registered connections.

        Returns:
            Sorted list of registered connection names.
        """
        return sorted(self._clients)

    def __len__(self) -> int:
        return len(self._clients)

    def __repr__(self) -> str:
        names = ", ".join(self._clients)
        return f"MCPClientRegistry(connections=[{names}])"


# ── MCPClientProvider ─────────────────────────────────────────────────────────


class MCPClientProvider(Provider):
    name = "mcp_client"
    priority = ProviderPriority.COMMS

    """Provider that registers :class:`MCPClientRegistry` and :class:`MCPClient`
    instances in the DI container.

    Registered automatically by :class:`MCPClientModule`.  Not normally
    instantiated directly.
    """

    def __init__(self, connections: list[MCPConnection]) -> None:
        super().__init__()
        self._connections = list(connections)
        self._clients: list[MCPClient] = []

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register MCPClientRegistry (and a single MCPClient if one connection)."""
        clients: dict[str, MCPClient] = {}
        self._clients = []
        for conn in self._connections:
            client = conn.build_client()
            clients[conn.name] = client
            self._clients.append(client)
            logger.debug(
                "mcp_client_connection_registered",
                name=conn.name,
                transport=conn.transport_type,
            )

        registry = MCPClientRegistry(clients)
        container.singleton(MCPClientRegistry, registry)

        # Register the primary client directly for single-connection use cases
        if self._connections:
            primary_client = clients[self._connections[0].name]
            container.singleton(MCPClient, primary_client)
            logger.info(
                "mcp_client_module_registered",
                connections=[c.name for c in self._connections],
            )

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Boot hook for MCP client provider."""

    async def shutdown(self) -> None:
        """Shutdown MCP client provider resources."""
        for client in self._clients:
            try:
                await client.disconnect()
            except Exception as exc:  # noqa: BLE001 — client disconnect is best-effort
                logger.warning(
                    "mcp_client_disconnect_failed", error_type=type(exc).__name__
                )

        self._clients.clear()


# ── MCPClientModule ───────────────────────────────────────────────────────────


class MCPClientModule(Module):
    """Module for consuming external MCP servers via DI-injected clients.

    Registers one or more :class:`MCPClient` instances (wrapped in an
    :class:`MCPClientRegistry`) so any service in the application can call
    external MCP tools.

    Use :meth:`configure` to configure connections::

        app = QuadkitApplication(
            modules=[
                MCPClientModule.configure(
                    connections=[
                        MCPConnection.stdio(
                            ["uvx", "mcp-server-git"],
                            name="git",
                        ),
                    ]
                ),
            ],
        )
    """

    def __init__(self, connections: list[MCPConnection] | None = None) -> None:
        super().__init__()
        self._connections: list[MCPConnection] = connections or []

    @classmethod
    def configure(cls, connections: list[MCPConnection]) -> MCPClientModule:  # type: ignore[override]
        """Create an ``MCPClientModule`` for the given connections.

        Args:
            connections: List of :class:`MCPConnection` objects describing
                         each external MCP server.  Each must have a unique
                         *name*.

        Returns:
            An ``MCPClientModule`` ready to be added to the application.

        Raises:
            ValueError: If *connections* is empty or contains duplicate names.

        Example::

            MCPClientModule.configure(
                connections=[
                    MCPConnection.stdio(["npx", "github-mcp"], name="github"),
                    MCPConnection.sse("http://localhost:9000/mcp", name="local"),
                ],
            )
        """
        if not connections:
            raise ValueError("At least one MCPConnection is required")
        names = [c.name for c in connections]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"Duplicate MCPConnection names: {sorted(duplicates)}")
        return cls(connections=list(connections))

    def providers(self) -> list:  # type: ignore[override]
        """Return the DI providers for this module."""
        return [MCPClientProvider(connections=self._connections)]


__all__ = [
    "MCPClientModule",
    "MCPClientProvider",
    "MCPClientRegistry",
    "MCPConnection",
]
