"""MCP controller system — decorators, base class, and provider implementations."""

from __future__ import annotations

from quadkit.ai.mcp.controllers.base import MCPController
from quadkit.ai.mcp.controllers.decorators import prompt, resource, tool
from quadkit.ai.mcp.controllers.providers import (
    ControllerPromptProvider,
    ControllerResourceProvider,
    ControllerToolProvider,
    ModulePromptProvider,
    ModuleResourceProvider,
    ModuleToolProvider,
    ServiceToolProvider,
    _CombinedResourceProvider,
    _CombinedToolProvider,
)

__all__ = [
    "ControllerPromptProvider",
    "ControllerResourceProvider",
    "ControllerToolProvider",
    "MCPController",
    "ModulePromptProvider",
    "ModuleResourceProvider",
    "ModuleToolProvider",
    "ServiceToolProvider",
    "_CombinedResourceProvider",
    "_CombinedToolProvider",
    "prompt",
    "resource",
    "tool",
]
