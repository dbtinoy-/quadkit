import pytest
from starlette.testclient import TestClient

from quadkit.web.config import WebProviderConfig
from quadkit.web.routing.controllers import Controller
from quadkit.web import get


class DebugController(Controller):
    @get("/x")
    def x(self):
        return {"ok": True}


@pytest.mark.asyncio
async def test_debug_routes_endpoint_lists_routes(test_bed):
    """Test that the debug routes endpoint returns a list of registered routes."""
    from quadkit.web.di.provider import WebProvider
    
    web = await test_bed.resolve(WebProvider)
    
    client = TestClient(web.starlette)
    r = client.get("/debug/routes")
    assert r.status_code == 200
    j = r.json()
    assert "routes" in j
