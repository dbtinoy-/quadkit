import pytest
import os
from starlette.testclient import TestClient
from quadkit.web.quickstart import _reset_quickstart_registry

@pytest.fixture(autouse=True)
def cleanup_quickstart():
    import sys
    from quadkit.web.quickstart import _reset_quickstart_registry
    _reset_quickstart_registry()
    yield
    _reset_quickstart_registry()
    
    # Remove from sys.modules to prevent cross-test route discovery
    to_remove = [
        "chat", "chat.app", 
        "greeting", "greeting.app",
        "structured_users", "structured_users.app"
    ]
    for mod in to_remove:
        sys.modules.pop(mod, None)
    # Also remove any submodules of the above
    for mod_name in list(sys.modules.keys()):
        for prefix in to_remove:
            if mod_name.startswith(f"{prefix}."):
                sys.modules.pop(mod_name, None)

from unittest.mock import patch

@pytest.mark.skip(reason="examples/chat not yet implemented")
def test_chat_websocket():
    # Quickstart uses default template_directory="templates" relative to CWD.
    import os
    original_cwd = os.getcwd()
    os.chdir(os.path.join(original_cwd, "quadkit-web/examples/chat"))
    
    try:
        from chat.app import app
        
        with TestClient(app) as client:
            # Test UI Home
            response = client.get("/")
            assert response.status_code == 200
            assert "Quadkit WebSocket Chat" in response.text
            
            # Test WebSocket with two clients to verify broadcast
            with client.websocket_connect("/ws/chat") as ws1:
                # ws1 should receive system message
                data1 = ws1.receive_json()
                assert data1["event"] == "system"
                assert "User joined" in data1["message"]
                
                with client.websocket_connect("/ws/chat") as ws2:
                    # ws2 should receive its own system message
                    data2 = ws2.receive_json()
                    assert data2["event"] == "system"
                    
                    # ws1 should receive ws2's join message
                    data1_again = ws1.receive_json()
                    assert data1_again["event"] == "system"
                    
                    # ws1 sends a message
                    ws1.send_json({"text": "Hello from WS1"})
                    
                    # ws2 should receive it (ws1 will not because of exclude=websocket)
                    received = ws2.receive_json()
                    assert received["event"] == "message"
                    assert received["data"]["text"] == "Hello from WS1"
    finally:
        os.chdir(original_cwd)
