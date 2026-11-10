"""MCP resource handler for the MCP server."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.mcp.exceptions import MCPError, MCPResourceError
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class ResourceHandler:
    """Handler for MCP resource-related methods.

    Handles resources/list, resources/read, and resources/templates/list
    methods by delegating to an MCPResourceProviderProtocol implementation.
    """

    def __init__(
        self,
        resource_provider: Any | None = None,
    ) -> None:
        """Initialize the resource handler.

        Args:
            resource_provider: Provider that handles resource operations.
        """
        self._provider = resource_provider

    async def list_resources(self) -> Result[dict[str, Any], MCPError]:
        """Handle resources/list method.

        Returns:
            ``Result`` containing resources list in MCP format.
        """
        if self._provider is None:
            return Ok({"resources": []})

        try:
            resources = await self._provider.list_resources()
            return Ok({"resources": resources})
        except Exception as exc:  # noqa: BLE001 — list failures are logged, never raised
            error_type = type(exc).__name__
            logger.error("mcp_list_resources_error", error_type=error_type)
            return Err(
                MCPResourceError(
                    message=f"Failed to list resources ({error_type})",
                    uri="resources/list",
                )
            )

    async def read_resource(self, uri: str) -> Result[dict[str, Any], MCPError]:
        """Handle resources/read method.

        Args:
            uri: URI of the resource to read.

        Returns:
            ``Result[dict[str, Any], MCPError]`` with MCP-formatted contents.
        """
        if self._provider is None:
            return Err(
                MCPResourceError(
                    message="No resource provider configured",
                    uri="resources/read",
                )
            )

        try:
            content = await self._provider.read_resource(uri)
            return Ok({"contents": [content]})
        except MCPResourceError as exc:
            return Err(
                MCPResourceError(
                    message=f"Failed to read resource ({type(exc).__name__})",
                    uri="resources/read",
                )
            )
        except Exception as exc:  # noqa: BLE001 — read failures are logged, never raised
            error_type = type(exc).__name__
            logger.error(
                "mcp_read_resource_error",
                error_type=error_type,
            )
            return Err(
                MCPResourceError(
                    message=f"Failed to read resource ({error_type})",
                    uri="resources/read",
                )
            )

    async def list_templates(self) -> Result[dict[str, Any], MCPError]:
        """Handle resources/templates/list method.

        Returns:
            ``Result`` containing URI templates in MCP format.
        """
        if self._provider is None:
            return Ok({"resourceTemplates": []})

        try:
            # Try to get templates if the provider supports it
            if hasattr(self._provider, "list_templates"):
                templates = await self._provider.list_templates()
                return Ok({"resourceTemplates": templates})
            return Ok({"resourceTemplates": []})
        except Exception as exc:  # noqa: BLE001 — list failures are logged, never raised
            error_type = type(exc).__name__
            logger.error("mcp_list_templates_error", error_type=error_type)
            return Err(
                MCPResourceError(
                    message=f"Failed to list resource templates ({error_type})",
                    uri="resources/templates/list",
                )
            )


__all__ = ["ResourceHandler"]
