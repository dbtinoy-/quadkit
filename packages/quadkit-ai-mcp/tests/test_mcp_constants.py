"""Tests for MCP constants."""

from __future__ import annotations

import pytest


class TestMCPConstants:
    """Tests for MCP constants."""

    def test_env_prefix(self) -> None:
        from quadkit.ai.mcp.constants import ENV_PREFIX

        assert ENV_PREFIX == "QK_AI_MCP__"

    def test_env_nested_delimiter(self) -> None:
        from quadkit.ai.mcp.constants import ENV_NESTED_DELIMITER

        assert ENV_NESTED_DELIMITER == "__"

    def test_jsonrpc_methods(self) -> None:
        from quadkit.ai.mcp.constants import (
            MCP_METHOD_INITIALIZE,
            MCP_METHOD_TOOLS_LIST,
            MCP_METHOD_TOOLS_CALL,
            MCP_METHOD_RESOURCES_LIST,
            MCP_METHOD_RESOURCES_READ,
            MCP_METHOD_PROMPTS_LIST,
            MCP_METHOD_PROMPTS_GET,
        )

        assert MCP_METHOD_INITIALIZE == "initialize"
        assert MCP_METHOD_TOOLS_LIST == "tools/list"
        assert MCP_METHOD_TOOLS_CALL == "tools/call"
        assert MCP_METHOD_RESOURCES_LIST == "resources/list"
        assert MCP_METHOD_RESOURCES_READ == "resources/read"
        assert MCP_METHOD_PROMPTS_LIST == "prompts/list"
        assert MCP_METHOD_PROMPTS_GET == "prompts/get"

    def test_defaults(self) -> None:
        from quadkit.ai.mcp.constants import (
            DEFAULT_MCP_TIMEOUT_S,
            DEFAULT_MCP_MAX_RETRIES,
            MCP_PROTOCOL_VERSION,
        )

        assert DEFAULT_MCP_TIMEOUT_S == 30
        assert DEFAULT_MCP_MAX_RETRIES == 3
        assert MCP_PROTOCOL_VERSION == "2024-11-05"

    def test_error_codes(self) -> None:
        from quadkit.ai.mcp.constants import (
            ERROR_MCP_TOOL_NOT_FOUND,
            ERROR_MCP_CONNECTION_FAILED,
            ERROR_MCP_INVALID_RESPONSE,
        )

        assert ERROR_MCP_TOOL_NOT_FOUND == "QK_MCP_001"
        assert ERROR_MCP_CONNECTION_FAILED == "QK_MCP_002"
        assert ERROR_MCP_INVALID_RESPONSE == "QK_MCP_003"

    def test_version_is_string(self) -> None:
        from quadkit.ai.mcp.constants import __version__

        assert isinstance(__version__, str)

    def test_all_exports(self) -> None:
        from quadkit.ai.mcp import constants

        expected = [
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
        for name in expected:
            assert hasattr(constants, name)