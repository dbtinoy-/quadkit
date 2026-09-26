"""Tests for quadkit.http.protocols."""
from __future__ import annotations

import inspect

from quadkit.http.protocols import (
    HTTPClientProtocol,
    InterceptorChainProtocol,
    InterceptorProtocol,
)


class TestHTTPClientProtocol:
    """Tests for HTTPClientProtocol."""

    def test_is_protocol(self) -> None:
        """HTTPClientProtocol is a Protocol class."""
        assert inspect.isclass(HTTPClientProtocol)

    def test_is_importable(self) -> None:
        """HTTPClientProtocol is importable via quadkit.http.protocols."""
        assert HTTPClientProtocol.__name__ == "HTTPClientProtocol"


class TestInterceptorChainProtocol:
    """Tests for InterceptorChainProtocol."""

    def test_is_protocol(self) -> None:
        """InterceptorChainProtocol is a Protocol class."""
        assert inspect.isclass(InterceptorChainProtocol)

    def test_is_importable(self) -> None:
        """InterceptorChainProtocol is importable via quadkit.http.protocols."""
        assert InterceptorChainProtocol.__name__ == "InterceptorChainProtocol"


class TestInterceptorProtocol:
    """Tests for InterceptorProtocol."""

    def test_is_protocol(self) -> None:
        """InterceptorProtocol is a Protocol class."""
        assert inspect.isclass(InterceptorProtocol)

    def test_is_importable(self) -> None:
        """InterceptorProtocol is importable via quadkit.http.protocols."""
        assert InterceptorProtocol.__name__ == "InterceptorProtocol"


class TestModuleAll:
    """Tests for __all__ in protocols module."""

    def test_all_contains_all_protocols(self) -> None:
        """__all__ lists all three protocol types."""
        from quadkit.http import protocols

        assert protocols.__all__ == [
            "HTTPClientProtocol",
            "InterceptorChainProtocol",
            "InterceptorProtocol",
        ]
