import pytest
from starlette.datastructures import Headers

from quadkit import serialization as json
from quadkit.web.routing.router import Router


class _DummyContainer:
    def __init__(self, instance):
        self._instance = instance

    def resolve(self, cls):
        return self._instance

    async def resolve(self, cls):
        return self._instance


class Controller:
    async def handler(self, foo: int):
        return {"ok": True}


@pytest.mark.asyncio
async def test_unexpected_validation_error_bubbles_up(monkeypatch):
    router = Router()
    controller = Controller()
    container = _DummyContainer(controller)

    # Make validate_and_merge_request raise an unexpected exception
    async def _bad(request, handler, path_params):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(
        "quadkit.web.routing.validation.validate_and_merge_request",
        _bad,
    )

    endpoint = router._create_endpoint(Controller, "handler", container)

    # Create a minimal request-like object
    class _Req:
        def __init__(self):
            self.path_params = {}
            self.query_params = {}
            self.headers = Headers({})
            self.state = type("State", (), {})()

        async def json(self):
            return {}

    req = _Req()

    from quadkit.web import JSONResponse

    resp = await endpoint(req)
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 500
    data = json.loads(resp.body)
    # The fallback uses the same RFC 7807 contract as every other filter.
    assert data["type"] == "urn:quadkit:internal-error"
    assert data["status"] == 500
    assert data["detail"] == "An unexpected error occurred"
