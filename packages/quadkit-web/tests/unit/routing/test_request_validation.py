from dataclasses import dataclass
"""Tests for request validation."""
import pytest

from starlette.testclient import TestClient

from quadkit.app.base import Application
from quadkit.web.config import RateLimitConfig, WebConfig, SecurityConfig, CSRFConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.routing.controllers import Controller
from quadkit.web import get, post


class SearchController(Controller):
    @get("/search")
    async def search(self, q: str, limit: int = 10):
        return {"q": q, "limit": limit}


@pytest.mark.asyncio
async def test_query_params_validation():
    """Test query parameter validation."""
    app = Application(name="test-app")
    web = WebProvider(
        controllers=[SearchController],
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False), security=SecurityConfig(csrf=CSRFConfig(enabled=False))),  # Disable rate limiting and CSRF
    )

    try:
        await web.register(app.container)
        await web.boot(app.container)

        client = TestClient(web.starlette)

        # Valid params
        r = client.get("/search?q=hello&limit=5")
        assert r.status_code == 200
        data = r.json()
        assert data["q"] == "hello"
        assert isinstance(data["limit"], int)
        assert data["limit"] == 5

        # Invalid limit (non-int)
        r = client.get("/search?q=hi&limit=foo")
        assert r.status_code == 422
        j = r.json()
        assert j["type"] == "urn:quadkit:validation-error"

    finally:
        await web.shutdown()


@pytest.mark.asyncio
async def test_combined_body_path_query_validation():
    """Test combined body, path, and query parameter validation."""
    from quadkit.domain import DomainModel

    @dataclass
    class Payload(DomainModel):
        name: str
        value: int

    class ItemsController(Controller):
        @post("/items/{item_id}")
        async def update(self, item_id: int, payload: Payload, q: int = 1):
            return {"item_id": item_id, "payload_name": payload.name, "q": q}

    app = Application(name="test-app")
    web = WebProvider(
        controllers=[ItemsController],
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False), security=SecurityConfig(csrf=CSRFConfig(enabled=False))),  # Disable rate limiting and CSRF
    )

    try:
        await web.register(app.container)
        await web.boot(app.container)

        client = TestClient(web.starlette)

        # Valid request
        r = client.post("/items/123?q=2", json={"name": "foo", "value": 5})
        assert r.status_code == 200
        data = r.json()
        assert data["item_id"] == 123
        assert data["payload_name"] == "foo"
        assert data["q"] == 2

        # Invalid body (value is not an int)
        r = client.post("/items/123", json={"name": "foo", "value": "not-int"})
        assert r.status_code == 422
        j = r.json()
        assert j["type"] == "urn:quadkit:validation-error"

    finally:
        await web.shutdown()


@pytest.mark.asyncio
async def test_path_param_validation_error():
    """Test path parameter validation error handling."""

    class PathController(Controller):
        @post("/items/{item_id}")
        async def get_item(self, item_id: int):
            return {"item_id": item_id}

    app = Application(name="test-app")
    web = WebProvider(
        controllers=[PathController],
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False), security=SecurityConfig(csrf=CSRFConfig(enabled=False))),  # Disable rate limiting and CSRF
    )

    try:
        await web.register(app.container)
        await web.boot(app.container)

        client = TestClient(web.starlette)

        # Invalid path parameter should result in 422
        r = client.post("/items/not-an-int", json={})
        assert r.status_code == 422
        j = r.json()
        assert j["type"] == "urn:quadkit:validation-error"

    finally:
        await web.shutdown()