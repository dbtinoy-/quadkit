"""MCP (Model Context Protocol) constants — JSON-RPC methods and defaults."""

from __future__ import annotations

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("quadkit-ai-mcp")
except ImportError:
    __version__ = "0.0.0"


# -- Environment Variable Prefixes -------------------------------------------
ENV_PREFIX: str = "QK_AI_MCP__"
"""Environment variable prefix for MCP configuration."""

ENV_NESTED_DELIMITER: str = "__"
"""Delimiter for nested env var keys."""


# ---------------------------------------------------------------------------
# JSON-RPC methods
# ---------------------------------------------------------------------------

MCP_METHOD_INITIALIZE: str = "initialize"
MCP_METHOD_TOOLS_LIST: str = "tools/list"
MCP_METHOD_TOOLS_CALL: str = "tools/call"
MCP_METHOD_RESOURCES_LIST: str = "resources/list"
MCP_METHOD_RESOURCES_READ: str = "resources/read"
MCP_METHOD_PROMPTS_LIST: str = "prompts/list"
MCP_METHOD_PROMPTS_GET: str = "prompts/get"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_MCP_TIMEOUT_S: int = 30
DEFAULT_MCP_MAX_RETRIES: int = 3
MCP_PROTOCOL_VERSION: str = "2024-11-05"

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

ERROR_MCP_TOOL_NOT_FOUND: str = "QK_MCP_001"
ERROR_MCP_CONNECTION_FAILED: str = "QK_MCP_002"
ERROR_MCP_INVALID_RESPONSE: str = "QK_MCP_003"

__all__ = [
    "DEFAULT_MCP_MAX_RETRIES",
    "DEFAULT_MCP_TIMEOUT_S",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "ERROR_MCP_CONNECTION_FAILED",
    "ERROR_MCP_INVALID_RESPONSE",
    "ERROR_MCP_TOOL_NOT_FOUND",
    "MCP_METHOD_INITIALIZE",
    "MCP_METHOD_PROMPTS_GET",
    "MCP_METHOD_PROMPTS_LIST",
    "MCP_METHOD_RESOURCES_LIST",
    "MCP_METHOD_RESOURCES_READ",
    "MCP_METHOD_TOOLS_CALL",
    "MCP_METHOD_TOOLS_LIST",
    "MCP_PROTOCOL_VERSION",
    "__version__",
]
