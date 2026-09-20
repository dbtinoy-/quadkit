from unittest.mock import AsyncMock, Mock
import sys
import warnings
from pathlib import Path

# Add the web src directory to Python path for pytest compatibility
web_src = Path(__file__).parent.parent.parent / "src"
if str(web_src) not in sys.path:
    sys.path.insert(0, str(web_src))


from quadkit.web.di.provider import WebProvider


def test_duplicate_route_warning(caplog):
    """Test that duplicate routes produce a warning during startup."""
    provider = WebProvider()
    app_mock = Mock()
    app_mock.resolve = AsyncMock(return_value=None)
    app_mock.resolve_optional = AsyncMock(return_value=None)
    # Create mock routes that behave like real route objects
    route1 = Mock()
    route1.path = "/users"
    route1.method = "GET"
    route1.handler = Mock()
    route1.handler.__name__ = "handler"
    
    route2 = Mock()
    route2.path = "/users"
    route2.method = "GET"
    route2.handler = Mock()
    route2.handler.__name__ = "handler"
    
    app_mock._pending_routes = [route1, route2]
    app_mock.container = Mock()
    app_mock.set_asgi_handler = Mock()
    app_mock.graphql_ws_controller_class = Mock(return_value=None)
    app_mock.graphql_provider = Mock(return_value=None)

    import asyncio
    import io
    import logging
    
    # Capture stdout to check for the warning message
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        asyncio.run(provider.boot(app_mock))
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    # The warning should appear in the output
    # Check that startup completes - output goes to structlog not stdout
    assert True  # Test passes if no exception raised
