import asyncio
import pytest
from starlette.responses import HTMLResponse

from quadkit.web.routing.router import Router


class DummyRequest:
    path_params = {}
    query_params = {}
    state = None

    async def json(self):
        return {}


class DummyContainer:
    def resolve(self, cls):
        return cls()

    async def resolve(self, cls):
        return cls()


@pytest.mark.asyncio
async def test_router_returns_html_for_string_result():
    """Strings are no longer auto-detected as HTML.

    Use HTMLContent marker or return HTMLResponse explicitly.
    """
    class Controller:
        async def index(self):
            return "<html><body>hi</body></html>"

    router = Router()
    endpoint = router._create_endpoint(Controller, "index", DummyContainer())

    resp = await endpoint(DummyRequest())
    from starlette.responses import Response as StarletteResponse

    assert isinstance(resp, StarletteResponse)
    assert resp.media_type == "text/html"


@pytest.mark.asyncio
async def test_router_returns_html_for_bytes_result():
    class Controller:
        async def index(self):
            return b"<html><body>bytes</body></html>"

    router = Router()
    endpoint = router._create_endpoint(Controller, "index", DummyContainer())

    resp = await endpoint(DummyRequest())
    # Bytes should no longer be auto-detected as HTML; ensure raw bytes are returned
    from starlette.responses import Response as StarletteResponse

    assert isinstance(resp, StarletteResponse)
    assert not isinstance(resp, HTMLResponse)
    assert resp.media_type == "application/octet-stream"


@pytest.mark.asyncio
async def test_router_returns_html_for_htmlcontent_marker():
    from quadkit.web import HTMLContent

    class Controller:
        async def index(self):
            return HTMLContent("<div>marker</div>")

    router = Router()
    endpoint = router._create_endpoint(Controller, "index", DummyContainer())

    resp = await endpoint(DummyRequest())
    assert isinstance(resp, HTMLResponse)
    assert "text/html" in resp.media_type
