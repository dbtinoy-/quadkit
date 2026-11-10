import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.mcp.server.core import MCPServer
from quadkit.ai.mcp.server.host import MCPServerHost
from quadkit.ai.mcp.types import MCPJSONRPCRequest, MCPJSONRPCResponse


@pytest.fixture
def mock_server() -> MagicMock:
    server = MagicMock(spec=MCPServer)
    server.config = MagicMock()
    server.config.cors_origins = ["*"]
    
    # Setup handle_message mock
    async def mock_handle(message: dict) -> dict:
        return {"jsonrpc": "2.0", "id": message.get("id"), "result": "ok"}
        
    server.handle_message = AsyncMock(side_effect=mock_handle)
    return server


@pytest.mark.asyncio
async def test_mcp_server_host_sse_connection(mock_server: MagicMock) -> None:
    """Test SSE connection endpoint."""
    host = MCPServerHost(mock_server)
    
    # Mock ASGI scope and channels
    scope = {"type": "http", "method": "GET", "path": "/mcp/sse"}
    
    # We will simulate a disconnect after receiving the first two messages 
    # (headers and endpoint)
    receive_queue = asyncio.Queue()
    send_queue = asyncio.Queue()
    
    async def receive():
        return await receive_queue.get()
        
    async def send(message):
        await send_queue.put(message)
        
    # Start the ASGI app in the background
    app_task = asyncio.create_task(host(scope, receive, send))
    
    # Wait for the response start
    resp_start = await send_queue.get()
    assert resp_start["type"] == "http.response.start"
    assert resp_start["status"] == 200
    headers = dict(resp_start["headers"])
    assert headers[b"content-type"] == b"text/event-stream"
    
    # Wait for the endpoint event
    resp_body = await send_queue.get()
    assert resp_body["type"] == "http.response.body"
    body_str = resp_body["body"].decode()
    assert "event: endpoint\n" in body_str
    assert "data: /mcp/messages\n" in body_str
    
    # Now simulate a message from the server
    await host._transport.send({"jsonrpc": "2.0", "method": "test"})
    
    # Should receive the message event
    resp_body = await send_queue.get()
    body_str = resp_body["body"].decode()
    assert "event: message\n" in body_str
    assert 'data: {"jsonrpc":"2.0","method":"test"}\n' in body_str
    
    # Disconnect
    await receive_queue.put({"type": "http.disconnect"})
    
    # Wait for app to finish
    await asyncio.wait_for(app_task, timeout=1.0)


@pytest.mark.asyncio
async def test_mcp_server_host_messages_endpoint(mock_server: MagicMock) -> None:
    """Test messages POST endpoint."""
    host = MCPServerHost(mock_server)
    
    scope = {"type": "http", "method": "POST", "path": "/mcp/messages"}
    
    req_body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode()
    
    async def receive():
        return {"type": "http.request", "body": req_body, "more_body": False}
        
    send_queue = asyncio.Queue()
    async def send(message):
        await send_queue.put(message)
        
    await host._transport.start()
    await host(scope, receive, send)
    
    mock_server.handle_message.assert_awaited_once_with(
        {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    )
    
    # The response is sent via transport (queue), and we get a 202 Accepted
    resp_start = await send_queue.get()
    assert resp_start["type"] == "http.response.start"
    assert resp_start["status"] == 202
    
    queued = host._transport.get_queued_messages()
    assert len(queued) == 1
    assert queued[0] == {"jsonrpc": "2.0", "id": 1, "result": "ok"}


@pytest.mark.asyncio
async def test_mcp_server_host_404(mock_server: MagicMock) -> None:
    """Test 404 for unknown endpoint."""
    host = MCPServerHost(mock_server)
    
    scope = {"type": "http", "method": "GET", "path": "/mcp/unknown"}
    
    async def receive():
        return {"type": "http.request"}
        
    send_queue = asyncio.Queue()
    async def send(message):
        await send_queue.put(message)
        
    await host(scope, receive, send)
    
    resp_start = await send_queue.get()
    assert resp_start["status"] == 404


@pytest.mark.asyncio
async def test_host_default_posture_is_fail_closed() -> None:
    """A real MCPServer host boots and rejects non-handshake methods post-init."""
    tool_handler = MagicMock()
    tool_handler.call_tool = AsyncMock(
        return_value={"content": [{"type": "text", "text": "ok"}]}
    )
    server = MCPServer(tool_handler=tool_handler, name="smoke")
    host = MCPServerHost(server)
    assert host._server is server

    init_resp = await server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    assert "result" in init_resp

    resp = await server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "t", "arguments": {}},
        }
    )
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32000
    tool_handler.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_host_opt_in_posture_dispatches() -> None:
    """A real MCPServer host mounts and dispatches under the opt-in posture."""
    tool_handler = MagicMock()
    tool_handler.call_tool = AsyncMock(
        return_value={"content": [{"type": "text", "text": "ok"}]}
    )
    server = MCPServer(tool_handler=tool_handler, name="smoke", allow_unauthenticated=True)
    host = MCPServerHost(server)
    assert host._server is server

    await server.handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )

    resp = await server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "t", "arguments": {}},
        }
    )
    assert resp is not None
    assert "result" in resp
    tool_handler.call_tool.assert_awaited_once()
