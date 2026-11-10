"""MCP server configuration for the Quadkit framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, cast

from quadkit.ai.mcp.constants import ENV_NESTED_DELIMITER, ENV_PREFIX
from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass
class FilesystemConnectorConfig:
    """Configuration for the built-in FilesystemConnector."""

    root_dir: str = ""
    """Sandboxed root directory.  Must be set to a non-empty path to enable."""

    read_only: bool = False
    """When True, write_file and other mutating tools are disabled."""


@dataclass
class GitHubConnectorConfig:
    """Configuration for the built-in GitHubConnector."""

    token: str = ""
    """GitHub personal access token or fine-grained token."""

    api_url: str = "https://api.github.com"
    """Override for GitHub Enterprise installations."""


@dataclass
class WebFetchConnectorConfig:
    """Configuration for the built-in WebFetchConnector."""

    enabled: bool = False
    """When True, the web-fetch tool is active (disabled by default)."""

    max_content_bytes: int = 512 * 1024
    """Maximum response body size to fetch (default 512 KB)."""

    user_agent: str = "the optional provider/1.0"
    """HTTP User-Agent header to send."""


@dataclass
class WebSearchConnectorConfig:
    """Configuration for the built-in WebSearchConnector."""

    provider: str = "brave"
    """Search provider name: 'brave', 'serpapi', or 'google'."""

    api_key: str = ""
    """API key for the configured search provider."""

    max_results: int = 10
    """Maximum number of results to return."""


@dataclass
class SlackConnectorConfig:
    """Configuration for the built-in SlackConnector."""

    bot_token: str = ""
    """Slack bot OAuth token (xoxb-...)."""

    max_messages: int = 100
    """Maximum messages to return per channel history request."""


@dataclass
class GoogleDriveConnectorConfig:
    """Configuration for the built-in GoogleDriveConnector."""

    service_account_json: str = ""
    """Path to the Google service-account credentials JSON file."""

    impersonated_email: str = ""
    """Email to impersonate via domain-wide delegation (optional)."""


@dataclass
class SQLConnectorConfig:
    """Configuration for the built-in SQLConnector."""

    dsn: str = ""
    """Database connection string (e.g. postgresql://user:pass@host/db)."""

    allowed_tables: list[str] = field(default_factory=list)
    """Explicit allowlist of table names that the connector may query."""

    read_only: bool = True
    """When True, only SELECT statements are permitted (default True)."""


@dataclass
class ConnectorsConfig:
    """Top-level connector configuration block inside ``MCPConfig``."""

    filesystem: FilesystemConnectorConfig = field(
        default_factory=FilesystemConnectorConfig
    )
    github: GitHubConnectorConfig = field(default_factory=GitHubConnectorConfig)
    web_fetch: WebFetchConnectorConfig = field(default_factory=WebFetchConnectorConfig)
    web_search: WebSearchConnectorConfig = field(
        default_factory=WebSearchConnectorConfig
    )
    slack: SlackConnectorConfig = field(default_factory=SlackConnectorConfig)
    google_drive: GoogleDriveConnectorConfig = field(
        default_factory=GoogleDriveConnectorConfig
    )
    sql: SQLConnectorConfig = field(default_factory=SQLConnectorConfig)


@dataclass(init=False)
class MCPConfig(BaseConfig):
    """Configuration for the MCP server.

    Attributes:
        host: Host to bind to (for HTTP transport).
        port: Port to bind to (for HTTP transport).
        path: URL path for MCP endpoint (default /mcp).
        enable_sse: Enable Server-Sent Events for streaming responses.
        stdio_mode: Use stdio transport instead of HTTP.
        server_name: Name of the MCP server.
        server_version: Version of the MCP server.
        cors_origins: CORS allowed origins (for HTTP transport).
    """

    config_section: ClassVar[str] = "ai_mcp"

    model_config: ClassVar[ConfigDict] = cast(
        "ConfigDict",
        {
            "env_prefix": ENV_PREFIX,
            "env_nested_delimiter": ENV_NESTED_DELIMITER,
            "extra": "ignore",
        },
    )

    enabled: bool = Field(default=True, description="Enable the MCP server subsystem")
    name: str = "ai_mcp"
    env: Environment | None = Field(None, description="Deployment environment")

    host: str = Field(default="0.0.0.0")  # noqa: S104 — config default, operator overridable
    """Host to bind to (for HTTP transport)."""

    port: int = Field(default=8080, ge=1, le=65535)
    """Port to bind to (for HTTP transport)."""

    path: str = Field(default="/mcp")
    """URL path for MCP endpoint."""

    enable_sse: bool = Field(default=True)
    """Enable Server-Sent Events for streaming responses."""

    stdio_mode: bool = Field(default=False)
    """Use stdio transport instead of HTTP."""

    server_name: str = Field(default="the optional provider")
    """Name of the MCP server."""

    server_version: str = Field(default="1.0.0")
    """Version of the MCP server."""

    cors_origins: list[str] = field(default_factory=list)
    """CORS allowed origins (for HTTP transport)."""

    max_request_size: int = Field(default=1024 * 1024, ge=1024)
    """Maximum request size in bytes."""

    request_timeout: float = Field(default=30.0, ge=1.0)
    """Request timeout in seconds."""

    allow_unauthenticated: bool = Field(default=False)
    """Permit non-authorizer request dispatch.

    ``False`` (default) fails closed: after ``initialize``, requests for
    non-handshake methods are rejected with ``-32000`` unless an
    authorizer is bound or this flag is ``True``.  ``True`` is an explicit
    opt-out restoring the open posture for local/development use.
    """

    # Client-side configuration
    client_url: str | None = Field(default=None)
    """URL of an external MCP server to connect to as a client.

    When set, :class:`~quadkit.ai.mcp.client.MCPClient` is registered in the
    container using :class:`~quadkit.ai.mcp.client.SSEClientTransport`.
    For stdio-based clients, construct :class:`~quadkit.ai.mcp.client.MCPClient`
    directly via the container or code.
    """

    client_stdio_command: list[str] = field(default_factory=list)
    """Command and args to spawn a local MCP server as a subprocess client.

    When non-empty, :class:`~quadkit.ai.mcp.client.MCPClient` is registered
    using :class:`~quadkit.ai.mcp.client.StdioClientTransport`.
    Takes precedence over ``client_url`` when both are set.
    """

    connectors: ConnectorsConfig = field(default_factory=ConnectorsConfig)
    """Optional built-in connector configuration.

    Each connector is enabled by supplying a non-empty key value (e.g. a
    ``root_dir`` for the filesystem connector or a ``token`` for GitHub).
    """


__all__ = ["MCPConfig"]
