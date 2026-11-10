"""Config resource provider — exposes application configuration as MCP resource."""

from __future__ import annotations

from quadkit.ai.mcp.types import MCPResource
from quadkit.contracts.core.config import ConfigProtocol
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str

logger = get_logger(__name__)


class ConfigResourceProvider:
    """Exposes application configuration as an MCP resource.

    Allows MCP clients to read the current application configuration
    (with secrets redacted).

    Usage::

        provider = ConfigResourceProvider(config=quadkit_config)
        registry.register(provider)

    URI: ``config://app``
    """

    name = "config"
    description = "Application configuration"
    mime_type = "application/json"
    uri_template = "config://{section}"

    def __init__(self, config: ConfigProtocol) -> None:
        self._config = config

    def can_handle(self, uri: str) -> bool:
        return uri.startswith("config://")

    async def list(self) -> list[MCPResource]:
        return [
            MCPResource(
                uri="config://app",
                name="Application Config",
                description="Current application configuration (secrets redacted)",
                mime_type="application/json",
            ),
        ]

    async def read(self, uri: str) -> str:
        section = uri.replace("config://", "")

        if hasattr(self._config, "to_dict"):
            data = self._config.to_dict(redact_secrets=True)
        elif hasattr(self._config, "__dict__"):
            data = {
                k: v for k, v in self._config.__dict__.items() if not k.startswith("_")
            }
        else:
            data = {"error": "Config not serializable"}

        if section and section != "app":
            data = data.get(section, {"error": f"Section '{section}' not found"})

        return dumps_str(data)
