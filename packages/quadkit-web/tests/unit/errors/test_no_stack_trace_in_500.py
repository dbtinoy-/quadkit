"""Assert that 500 responses in non-debug mode do not leak stack traces."""

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.web.filters.builtin import DefaultExceptionFilter


class TestDefaultExceptionFilterNoTraceback:
    """DefaultExceptionFilter must never include Python tracebacks in responses."""

    @pytest.mark.asyncio
    async def test_generic_exception_response_has_no_traceback(self) -> None:
        """A bare RuntimeError must not expose its traceback in the JSON body."""
        exc = RuntimeError("This is a server-side bug")
        try:
            raise exc
        except RuntimeError as caught:
            exc = caught

        flt = DefaultExceptionFilter()
        response = await flt.handle(exc, None)

        body = response.body.decode()
        assert "Traceback" not in body
        assert 'File "' not in body
        assert "RuntimeError" not in body
        assert response.status_code == 500


@pytest.fixture
def bomb_app() -> Starlette:
    """Minimal Starlette app whose only route raises an unhandled RuntimeError."""

    async def endpoint(request: Request):
        raise RuntimeError("secret server-side failure")

    return Starlette(
        routes=[Route("/boom", endpoint, methods=["GET"])],
        # debug=False is the default; keep explicit for clarity
    )


def test_starlette_500_response_contains_no_stack_trace(bomb_app: Starlette) -> None:
    """Starlette returns a plain 500 without traceback when debug=False."""
    client = TestClient(bomb_app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    body = response.text
    assert "Traceback" not in body
    assert 'File "' not in body
    assert "secret server-side failure" not in body
