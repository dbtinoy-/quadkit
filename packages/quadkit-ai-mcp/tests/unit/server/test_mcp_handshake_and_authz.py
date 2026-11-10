"""MCP initialize-handshake and authz enforcement matrix."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.mcp.server.core import MCPServer

INIT_MESSAGE = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}


@pytest.fixture
def tool_handler() -> MagicMock:
    handler = MagicMock()
    handler.call_tool = AsyncMock(
        return_value={"content": [{"type": "text", "text": "ok"}]}
    )
    return handler


@pytest.fixture
def resource_handler() -> MagicMock:
    handler = MagicMock()
    handler.read_resource = AsyncMock(return_value={"contents": []})
    return handler


@pytest.fixture
def prompt_handler() -> MagicMock:
    handler = MagicMock()
    handler.get_prompt = AsyncMock(return_value={"messages": []})
    return handler


@pytest.fixture
def logging_handler() -> MagicMock:
    handler = MagicMock()
    handler.set_level = AsyncMock(return_value={})
    return handler


class TestPreInitMatrix:
    """Pre-init: only whitelisted methods are serviced."""

    @pytest.mark.asyncio
    async def test_tools_call_rejected_pre_init(self, tool_handler: MagicMock) -> None:
        server = MCPServer(tool_handler=tool_handler)
        response = await server.handle_message(
            {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {}}
        )
        assert response is not None
        assert response["error"]["code"] == -32002
        assert response["error"]["message"] == "Server not initialized"
        tool_handler.call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_whitelisted_methods_rejected_pre_init(
        self, resource_handler: MagicMock, prompt_handler: MagicMock, logging_handler: MagicMock
    ) -> None:
        server = MCPServer(
            resource_handler=resource_handler,
            prompt_handler=prompt_handler,
            logging_handler=logging_handler,
        )
        for method in ["resources/read", "prompts/get", "logging/setLevel"]:
            response = await server.handle_message(
                {"jsonrpc": "2.0", "id": 9, "method": method, "params": {}}
            )
            assert response is not None
            assert response["error"]["code"] == -32002, f"method: {method}"

    @pytest.mark.asyncio
    async def test_initialize_succeeds_pre_init(self) -> None:
        server = MCPServer()
        response = await server.handle_message(INIT_MESSAGE)
        assert response is not None
        assert "result" in response
        assert "protocolVersion" in response["result"]

    @pytest.mark.asyncio
    async def test_ping_and_notification_serviced_pre_init(self) -> None:
        server = MCPServer()
        ping = await server.handle_message(
            {"jsonrpc": "2.0", "id": 9, "method": "ping"}
        )
        assert ping == {"jsonrpc": "2.0", "id": 9, "result": {}}
        notification = await server.handle_message(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        assert notification is None


class TestAuthzMatrix:
    """Post-init: authorizer consulted, fail-closed by default."""

    @pytest.mark.asyncio
    async def test_denier_blocks_dispatch(
        self, resource_handler: MagicMock
    ) -> None:
        authorizer = MagicMock()
        authorizer.authorize = AsyncMock(return_value=False)
        server = MCPServer(resource_handler=resource_handler, authorizer=authorizer)
        await server.handle_message(INIT_MESSAGE)

        response = await server.handle_message(
            {"jsonrpc": "2.0", "id": 9, "method": "resources/read", "params": {}}
        )
        assert response is not None
        assert response["error"]["code"] == -32000
        assert response["error"]["message"] == "Request not authorized"
        resource_handler.read_resource.assert_not_awaited()
        authorizer.authorize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_allow_callback_forwards_result(
        self, tool_handler: MagicMock
    ) -> None:
        authorizer = MagicMock()
        authorizer.authorize = AsyncMock(return_value=True)
        server = MCPServer(tool_handler=tool_handler, authorizer=authorizer)
        await server.handle_message(INIT_MESSAGE)

        response = await server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {"name": "t", "arguments": {}},
            }
        )
        assert response is not None
        assert "result" in response
        tool_handler.call_tool.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_default_posture_rejects_post_init(
        self, prompt_handler: MagicMock
    ) -> None:
        server = MCPServer(prompt_handler=prompt_handler)
        await server.handle_message(INIT_MESSAGE)

        response = await server.handle_message(
            {"jsonrpc": "2.0", "id": 9, "method": "prompts/get", "params": {}}
        )
        assert response is not None
        assert response["error"]["code"] == -32000
        prompt_handler.get_prompt.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_allow_unauthenticated_restores_open_dispatch(
        self, tool_handler: MagicMock
    ) -> None:
        server = MCPServer(tool_handler=tool_handler, allow_unauthenticated=True)
        await server.handle_message(INIT_MESSAGE)

        response = await server.handle_message(
            {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {}}
        )
        assert response is not None
        assert "result" in response

    @pytest.mark.asyncio
    async def test_client_info_captured_at_initialize(
        self, tool_handler: MagicMock
    ) -> None:
        authorizer = MagicMock()
        authorizer.authorize = AsyncMock(return_value=False)
        server = MCPServer(tool_handler=tool_handler, authorizer=authorizer)
        client_info = {"name": "matrix-client", "version": "1.0"}
        await server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"clientInfo": client_info},
            }
        )

        await server.handle_message(
            {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {}}
        )
        assert authorizer.authorize.await_args.kwargs["client_info"] == client_info

    @pytest.mark.asyncio
    async def test_whitelist_not_authorizer_gated(self) -> None:
        authorizer = MagicMock()
        authorizer.authorize = AsyncMock(return_value=False)
        server = MCPServer(authorizer=authorizer)

        init = await server.handle_message(INIT_MESSAGE)
        assert "result" in init
        ping = await server.handle_message(
            {"jsonrpc": "2.0", "id": 9, "method": "ping"}
        )
        assert "result" in ping
        authorizer.authorize.assert_not_awaited()