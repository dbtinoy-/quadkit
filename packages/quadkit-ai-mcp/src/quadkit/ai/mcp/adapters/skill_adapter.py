"""Skill adapter for exposing the optional provider as MCP tools.

Bridges the ``SkillRegistryProtocol`` from ``quadkit-contracts`` into the MCP
tool layer so that registered skills are automatically discoverable and callable
by MCP clients.  The adapter performs property-name mapping only — no schema
transformation — keeping the skills subsystem decoupled from MCP transport.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger, safe_error_type

if TYPE_CHECKING:
    from quadkit.contracts.ai.skills import (
        SkillExecutorProtocol,
        SkillRegistryProtocol,
    )

logger = get_logger(__name__)


class SkillToolAdapter:
    """Adapter that exposes registered skills as MCP tools.

    Translation mapping:

    * ``SkillDefinition.name``             → MCP tool ``name``
    * ``SkillDefinition.description``      → MCP tool ``description``
    * ``SkillDefinition.parameters_schema`` → MCP ``inputSchema``
    * ``SkillExecutorProtocol.execute()``  → MCP tool invocation
    """

    def __init__(
        self,
        skill_registry: SkillRegistryProtocol | None = None,
        skill_executor: SkillExecutorProtocol | None = None,
    ) -> None:
        self._registry = skill_registry
        self._executor = skill_executor

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all skills as MCP-formatted tool definitions.

        Returns:
            List of tool definitions with ``name``, ``description``,
            and ``inputSchema``.
        """
        if self._registry is None:
            return []

        try:
            definitions = self._registry.list_skills()
            return [
                {
                    "name": d.name,
                    "description": d.description,
                    "inputSchema": d.parameters_schema,
                }
                for d in definitions
            ]
        except Exception:  # noqa: BLE001 — skill conversion falls back to an empty list
            return []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> Any:
        """Execute a skill by name with given arguments.

        Args:
            name: Name of the skill to execute.
            arguments: Arguments to pass to the skill.
            user_id: Optional user ID for permission checks.
            session_id: Optional session ID for context.

        Returns:
            Skill execution result output.

        Raises:
            RuntimeError: If no skill executor is configured.
            ValueError: If the skill is not found.
        """
        if self._executor is None:
            raise RuntimeError("No skill executor configured")

        if self._registry is not None:
            skill = self._registry.get(name)
            if skill is None:
                raise ValueError("Requested skill was not found")

        result = await self._executor.execute(
            skill_name=name,
            params=arguments,
            user_id=user_id,
            session_id=session_id,
        )

        if result.is_ok():
            return result.unwrap().output
        error = result.unwrap_err()
        raise RuntimeError(
            f"Skill execution failed ({safe_error_type(error)})"
        ) from None


__all__ = ["SkillToolAdapter"]
