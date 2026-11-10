"""Built-in MCP resource providers."""

from __future__ import annotations

from quadkit.ai.mcp.resources.config import ConfigResourceProvider
from quadkit.ai.mcp.resources.database import DatabaseResourceProvider
from quadkit.ai.mcp.resources.search import SearchResourceProvider

__all__ = [
    "ConfigResourceProvider",
    "DatabaseResourceProvider",
    "SearchResourceProvider",
]
