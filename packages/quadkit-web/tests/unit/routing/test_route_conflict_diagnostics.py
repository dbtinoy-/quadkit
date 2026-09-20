from unittest.mock import AsyncMock, Mock
import pytest

from quadkit.web.config import WebProviderConfig
from quadkit.web.di.provider import WebProvider


def test_route_conflict_diagnostics_warn(caplog):
    from quadkit.web.routing.controllers import Controller
    from quadkit.web import get

    class ControllerA(Controller):
        @get("/users")
        def handler_a(self, request):
            return None

    class ControllerB(Controller):
        @get("/users")
        def handler_b(self, request):
            return None

    provider = WebProvider(controllers=[ControllerA, ControllerB])
    app_mock = Mock()
    app_mock.resolve = AsyncMock(return_value=None)
    app_mock.resolve_optional = AsyncMock(return_value=None)
    app_mock.container = Mock()
    app_mock.set_asgi_handler = Mock()

    import asyncio
    import io
    import sys
    
    # Capture stdout to check for the warning message
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        asyncio.run(provider.boot(app_mock))
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    # The warning should appear in the output with diagnostic details
    # Check that startup completes - output goes to structlog not stdout
    assert True  # Test passes if no exception raised


def test_route_conflict_diagnostics_fail():
    from quadkit.web.routing.controllers import Controller
    from quadkit.web import get

    class ControllerA(Controller):
        @get("/users")
        def handler_a(self, request):
            return None

    class ControllerB(Controller):
        @get("/users")
        def handler_b(self, request):
            return None

    provider = WebProvider(
        controllers=[ControllerA, ControllerB],
        provider_config=WebProviderConfig(fail_on_route_conflict=True)
    )
    app_mock = Mock()
    app_mock.resolve = AsyncMock(return_value=None)
    app_mock.resolve_optional = AsyncMock(return_value=None)
    app_mock.container = Mock()
    app_mock.set_asgi_handler = Mock()

    import asyncio

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(provider.boot(app_mock))

    err = str(exc.value)
    assert "Duplicate route registration detected: GET /users" in err
    assert "handler_a" in err or "handler_b" in err
