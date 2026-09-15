"""Tests for the Gear 2 (Structured App) example: structured_users."""

import os

import pytest
from starlette.testclient import TestClient
from quadkit.web.quickstart import _reset_quickstart_registry


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


@pytest.fixture
def client():
    """Create a test client for the structured-users example app."""
    os.environ["QK_CONFIG_PATH"] = (
        "quadkit-web/examples/structured_users/application.yaml"
    )
    from structured_users.app import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.skip(reason="examples/structured_users not yet implemented")
def test_structured_users_gear_2(client):
    """Exercises Create, List, Get, and NotFound flows on the UserController."""
    # Create a user — controller uses status_code=201
    user_data = {"email": "test@example.com"}
    response = client.post("/api/v1/users/", json=user_data)
    assert response.status_code == 201, response.text
    user = response.json()
    assert user["email"] == "test@example.com"
    user_id = user["id"]

    # Get the user
    response = client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == user_id

    # List users — the created user should appear
    response = client.get("/api/v1/users/")
    assert response.status_code == 200, response.text
    users = response.json()
    assert any(u["id"] == user_id for u in users)

    # Not found
    response = client.get("/api/v1/users/nonexistent")
    assert response.status_code == 400, response.text
