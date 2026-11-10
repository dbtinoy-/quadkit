"""MCP package CLI contributor."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import CommandContribution
from quadkit.contracts.cli.types import GeneratorDefinition


class McpCliContributor:
    """CLI contributor for the quadkit-ai-mcp package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "mcp"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for MCP."""
        return [
            GeneratorDefinition(
                name="mcp-controller",
                title="Generate Mcp Controller",
                description="Generate an MCPController class with tool, resource, and prompt examples",
                contributor="mcp",
                generator_path="quadkit.ai.mcp.cli.generators.mcp_controller:MCPControllerGenerator",
                default_output_dir="src/mcp",
            ),
            GeneratorDefinition(
                name="mcp-server",
                title="Generate Mcp Server",
                description="Generate a standalone MCP server script with module-level decorators",
                contributor="mcp",
                generator_path="quadkit.ai.mcp.cli.generators.mcp_server:MCPServerGenerator",
                default_output_dir="src",
            ),
        ]

    def get_commands(self) -> list[CommandContribution]:
        """Return the contributed `mcp` command group."""
        return [
            CommandContribution(
                name="mcp",
                help="MCP server management — serve, inspect, list tools",
                app_factory_path="quadkit.ai.mcp.cli.commands:create_mcp_app",
                contributor="mcp",
                category="ai",
            ),
        ]


__all__ = ["McpCliContributor"]
