import pytest
from starlette.testclient import TestClient
from quadkit.web.quickstart import _reset_quickstart_registry
import sys

@pytest.fixture(autouse=True)
def cleanup_quickstart():
    """Reset quickstart state before and after each test."""
    import sys
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

@pytest.mark.skip(reason="examples/greeting not yet implemented")
def test_greeting_gear_1():
    # Quickstart uses relative paths in some cases
    import os
    original_cwd = os.getcwd()
    os.chdir(os.path.join(original_cwd, "quadkit-web/examples/greeting"))
    
    try:
        from greeting.app import app
        
        with TestClient(app) as client:
            # Test Root
            response = client.get("/")
            assert response.status_code == 200
            assert response.json()["message"] == "Welcome to Quadkit Gear 1"
            
            # Test Greet
            response = client.get("/greet/testuser")
            assert response.status_code == 200
            assert response.json()["message"] == "Hello, testuser!"
            
            # Test Echo
            data = {"hello": "world"}
            response = client.post("/echo", json=data)
            assert response.status_code == 200
            assert response.json()["received"] == data
    finally:
        os.chdir(original_cwd)
