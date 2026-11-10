"""MCP prompt handler for the MCP server."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.mcp.exceptions import MCPError, MCPPromptError
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class PromptHandler:
    """Handler for MCP prompt-related methods.

    Handles prompts/list and prompts/get methods by delegating to an
    MCPPromptProviderProtocol implementation.
    """

    def __init__(
        self,
        prompt_provider: Any | None = None,
    ) -> None:
        """Initialize the prompt handler.

        Args:
            prompt_provider: Provider that handles prompt operations.
        """
        self._provider = prompt_provider

    async def list_prompts(self) -> Result[dict[str, Any], MCPError]:
        """Handle prompts/list method.

        Returns:
            ``Result`` containing prompts list in MCP format.
        """
        if self._provider is None:
            return Ok({"prompts": []})

        try:
            prompts = await self._provider.list_prompts()
            return Ok({"prompts": prompts})
        except Exception as exc:  # noqa: BLE001 — list failures are logged, never raised
            error_type = type(exc).__name__
            logger.error("mcp_list_prompts_error", error_type=error_type)
            return Err(
                MCPPromptError(
                    message=f"Failed to list prompts ({error_type})",
                    prompt_name="prompts/list",
                )
            )

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Result[dict[str, Any], MCPError]:
        """Handle prompts/get method.

        Args:
            name: Name of the prompt to get.
            arguments: Arguments to fill in the prompt template.

        Returns:
            ``Result[dict[str, Any], MCPError]`` with prompt payload.
        """
        if self._provider is None:
            return Err(
                MCPPromptError(
                    message="No prompt provider configured",
                    prompt_name=name,
                )
            )

        if arguments is None:
            arguments = {}

        try:
            prompt = await self._provider.get_prompt(name, arguments)
            return Ok(prompt)
        except MCPPromptError as exc:
            return Err(
                MCPPromptError(
                    message=f"Failed to get prompt ({type(exc).__name__})",
                    prompt_name=name,
                )
            )
        except Exception as exc:  # noqa: BLE001 — prompt failures are logged, never raised
            error_type = type(exc).__name__
            logger.error(
                "mcp_get_prompt_error",
                error_type=error_type,
            )
            return Err(
                MCPPromptError(
                    message=f"Failed to get prompt ({error_type})",
                    prompt_name=name,
                )
            )


__all__ = ["PromptHandler"]
