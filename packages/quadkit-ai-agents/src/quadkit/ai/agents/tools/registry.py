"""Tool registry for managing agent tools with module visibility control.

When module visibility is enabled, tool access is checked against
the compiled module graph before execution. An agent in
a specific module can only use tools exported by modules it imports.

Boundary rule
-------------
**Tools are atomic, stateless, single-purpose operations** invoked directly by
the agent reasoning loop (ReAct, PlanExecute, etc.). They should complete in
milliseconds and have no cross-call state.

**Skills** (``the optional provider``) are composed multi-step workflows that may
be stateful, long-running, or permission-gated. Skills may invoke tools
internally. Tools must NOT invoke skills.

The dependency direction is always:  ``Skill → Tool``, never the reverse.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.agents.exceptions import (
    ToolAccessDeniedError,
    ToolExecutionError,
    ToolNotFoundError,
)
from quadkit.contracts.ai.agents import ToolError, ToolProtocol, ToolRegistryProtocol
from quadkit.logging import get_logger
from quadkit.primitives.registry import Registry
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.contracts.core.module import CompiledModuleGraphProtocol


class ToolRegistryImpl(Registry[str, ToolProtocol], ToolRegistryProtocol):
    """Registry for atomic agent tools with optional module visibility control.

    Tools are stateless, single-purpose functions invoked directly by the agent
    reasoning loop (ReAct, PlanExecute, etc.). They should be fast (<500ms) and
    have no side effects beyond their stated purpose.

    **Boundary rule:** Tools do NOT invoke skills. Skills may invoke tools.

    Extends :class:`Registry` for unified introspection, lifecycle hooks,
    and thread-safe storage while implementing :class:`ToolRegistryProtocol`.

    When a ``CompiledModuleGraph`` is provided, tool access is checked against
    the module visibility map before execution.

    Example::

        registry = ToolRegistry()
        registry.register(lookup_order, module_class=OrdersModule)
        registry.register(process_refund, module_class=PaymentsModule)

        # Without visibility — all tools accessible
        result = await registry.execute("lookup_order", order_id="123")

        # With visibility — only tools visible to the caller's module
        registry.set_module_graph(compiled_graph)
        registry.set_caller_module(SupportModule)
        result = await registry.execute("lookup_order", order_id="123")
    """

    def __init__(self) -> None:
        super().__init__(name="agent.tools", allow_overwrite=False)
        self._tool_modules: dict[str, type | None] = {}
        self._module_graph: CompiledModuleGraphProtocol | None = None
        self._caller_module: type | None = None

    def register(  # type: ignore[override]
        self,
        tool: ToolProtocol,
        module_class: type | None = None,
    ) -> None:
        """Register a tool.

        Args:
            tool: Tool satisfying ``ToolProtocol``.
            module_class: Optional module that owns this tool
                (for visibility enforcement).

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if self.has(tool.name):
            raise ValueError("Tool already registered")
        super().register(tool.name, tool)
        self._tool_modules[tool.name] = module_class
        logger.debug("tool_registered")

    def unregister(self, name: str) -> ToolProtocol | None:
        """Remove and return a tool by name."""
        self._tool_modules.pop(name, None)
        return super().unregister(name)

    def get(self, name: str) -> ToolProtocol | None:  # type: ignore[override]
        """Get a tool by name, or None if not found."""
        return super().get(name)

    def list_tools(self) -> list[ToolProtocol]:
        """List all registered tools."""
        return list(self.values())

    def list_tool_names(self) -> list[str]:
        """List all registered tool names."""
        return list(self.keys())

    def list_visible_tools(self) -> list[ToolProtocol]:
        """List tools visible to the current caller module.

        If no caller module is set, returns all tools (standalone mode).
        """
        if not self._caller_module:
            return self.list_tools()

        visible = []
        for name, tool in self.items():
            if self._is_tool_visible(name):
                visible.append(tool)
        return visible

    def list_visible_tool_names(self) -> list[str]:
        """List names of tools visible to the current caller module."""
        return [t.name for t in self.list_visible_tools()]

    def list_tool_schemas(self) -> list[dict[str, Any]]:
        """Generate the tool schema list for LLM function calling.

        Returns only tools visible to the current caller module.
        """
        tools = self.list_visible_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema,
                },
            }
            for t in tools
        ]

    def set_module_graph(self, graph: CompiledModuleGraphProtocol | None) -> None:
        """Set the compiled module graph for visibility enforcement.

        Args:
            graph: A ``CompiledModuleGraph`` from the module compiler.
        """
        self._module_graph = graph
        logger.debug("tool_registry_module_graph_set")

    def set_caller_module(self, module_class: type | None) -> None:
        """Set the calling module for visibility checks.

        Args:
            module_class: The module class of the agent using this registry.
                ``None`` means standalone (no visibility restrictions).
        """
        self._caller_module = module_class

    async def execute(
        self,
        name: str,
        **kwargs: Any,
    ) -> Result[Any, ToolError]:
        """Execute a tool by name with visibility and error handling.

        Checks module visibility before execution when a module graph
        is configured.

        Args:
            name: Tool name to execute.
            **kwargs: Arguments to pass to the tool.

        Returns:
            ``Ok(result)`` on success, ``Err(ToolError)`` on failure.
        """
        tool = self.get(name)
        if tool is None:
            return Err(ToolNotFoundError(message="Tool not found"))

        # Module visibility check
        if not self._is_tool_visible(name):
            logger.warning("tool_access_denied")
            return Err(ToolAccessDeniedError(message="Tool access denied"))

        try:
            result = await tool.execute(**kwargs)
            logger.debug("tool_executed")
            return Ok(result)
        except Exception as exc:  # noqa: BLE001 - tool execution failures are returned safely
            error_type = type(exc).__name__
            logger.warning(
                "tool_execution_failed",
                error_type=error_type,
            )
            return Err(
                ToolExecutionError(
                    message="Tool execution failed",
                    details={"error_type": error_type},
                )
            )

    def _is_tool_visible(self, tool_name: str) -> bool:
        """Check if a tool is visible to the current caller module.

        Visibility rules:
        1. No caller module → all tools visible (standalone agent)
        2. Tool has no module → visible to everyone
        3. Tool module == caller module → visible (same module)
        4. Tool module exports are visible to caller → visible
        5. Tool module is global → visible
        6. Otherwise → not visible
        """
        if not self._caller_module:
            return True

        tool_module = self._tool_modules.get(tool_name)
        if tool_module is None:
            return True  # unowned tools are always visible

        if tool_module == self._caller_module:
            return True  # same module

        # Check module graph visibility
        try:
            graph_any = cast("Any", self._module_graph)
            caller_node = graph_any.get_module(self._caller_module)
            tool_node = graph_any.get_module(tool_module)

            if tool_node and getattr(tool_node, "is_global", False):
                return True

            if caller_node:
                imports = getattr(caller_node, "imports", [])
                if tool_module in imports:
                    return True
        except Exception:  # noqa: BLE001 — module graph lookup failures deny access
            # If module graph lookup fails, deny access (fail closed)
            logger.warning("module_graph_visibility_check_failed")
            return False

        return False

    def clear(self) -> None:
        """Remove all registered tools."""
        super().clear()
        self._tool_modules.clear()

    def __repr__(self) -> str:
        visible = len(self.list_visible_tools())
        total = len(self)
        if visible == total:
            return f"ToolRegistry(tools={total})"
        return f"ToolRegistry(tools={total}, visible={visible})"
