"""MCP provider classes for controller-, module-, and service-based dispatch."""

from __future__ import annotations

from quadkit.ai.mcp.controllers._controller_providers import (
    ControllerPromptProvider,
    ControllerResourceProvider,
    ControllerToolProvider,
)
from quadkit.ai.mcp.controllers._module_providers import (
    ModulePromptProvider,
    ModuleResourceProvider,
    ModuleToolProvider,
)
from quadkit.ai.mcp.controllers._service_providers import (
    ServiceToolProvider,
    _CombinedResourceProvider,
    _CombinedToolProvider,
)

__all__ = [
    "ControllerPromptProvider",
    "ControllerResourceProvider",
    "ControllerToolProvider",
    "ModulePromptProvider",
    "ModuleResourceProvider",
    "ModuleToolProvider",
    "ServiceToolProvider",
    "_CombinedResourceProvider",
    "_CombinedToolProvider",
]
