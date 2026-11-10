"""User-facing decorators for quadkit-ai-mcp.

Applied by application developers when defining MCP tools, resources,
and prompts for model context protocol servers.
"""

from __future__ import annotations

from quadkit.ai.mcp.controllers.decorators import (
    prompt as prompt,
)
from quadkit.ai.mcp.controllers.decorators import (
    resource as resource,
)
from quadkit.ai.mcp.controllers.decorators import (
    tool as tool,
)

__all__ = ["prompt", "resource", "tool"]
