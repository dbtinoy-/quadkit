"""Regression tests for sensitive MCP inputs and private transport details."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import quadkit.ai.mcp.client._transports as transports_module
import quadkit.ai.mcp.server.handlers.tools as tools_module
from quadkit.ai.mcp.client._transports import StdioClientTransport
from quadkit.ai.mcp.server.handlers.tools import ToolHandler


class _PrivateProviderError(Exception):
    """Provider error carrying data that must not reach logs or responses."""


@pytest.mark.asyncio
async def test_tool_handler_omits_tool_names_and_raw_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_tool_name = "PRIVATE_TOOL_NAME_SENTINEL"
    private_error = "PRIVATE_PROVIDER_ERROR_SENTINEL"
    logger = MagicMock()
    monkeypatch.setattr(tools_module, "logger", logger)
    provider = MagicMock()
    provider.call_tool = AsyncMock(side_effect=_PrivateProviderError(private_error))

    result = await ToolHandler(provider).call_tool(
        private_tool_name,
        {"private_argument": "PRIVATE_TOOL_ARGUMENT_SENTINEL"},
    )

    error = result.unwrap_err()
    assert "_PrivateProviderError" in error.message
    assert private_tool_name not in error.message
    assert error.details == {}
    logged = repr(logger.mock_calls)
    assert private_tool_name not in logged
    assert "PRIVATE_TOOL_ARGUMENT_SENTINEL" not in logged
    assert private_error not in logged
    assert "_PrivateProviderError" in logged


@pytest.mark.asyncio
async def test_tool_handler_invalid_argument_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_tool_name = "PRIVATE_INVALID_TOOL_NAME_SENTINEL"
    private_error = "PRIVATE_ARGUMENT_ERROR_SENTINEL"
    logger = MagicMock()
    monkeypatch.setattr(tools_module, "logger", logger)
    provider = MagicMock()
    provider.call_tool = AsyncMock(side_effect=ValueError(private_error))

    result = await ToolHandler(provider).call_tool(private_tool_name, {})

    error = result.unwrap_err()
    assert "ValueError" in error.message
    assert private_tool_name not in str(error)
    assert private_error not in str(error)
    assert error.details == {}
    logged = repr(logger.mock_calls)
    assert private_tool_name not in logged
    assert private_error not in logged


@pytest.mark.asyncio
async def test_stdio_connection_logs_do_not_expose_command_or_process_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_command = "/PRIVATE/COMMAND/PATH/SENTINEL"
    private_pid = 987654321
    logger = MagicMock()
    monkeypatch.setattr(transports_module, "logger", logger)
    process = MagicMock()
    process.pid = private_pid
    process.stdin = MagicMock()
    process.stdout = MagicMock()
    process.wait = AsyncMock(return_value=0)
    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=process),
    )

    transport = StdioClientTransport([private_command, "PRIVATE_ARGUMENT_SENTINEL"])
    await transport.connect()
    await transport.disconnect()

    logged = repr(logger.mock_calls)
    assert private_command not in logged
    assert "PRIVATE_ARGUMENT_SENTINEL" not in logged
    assert str(private_pid) not in logged
