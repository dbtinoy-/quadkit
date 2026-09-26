"""Tests for HTTP exceptions."""

import pytest

from quadkit.http.exceptions import HTTPClientError


class TestHTTPClientError:
    """Tests for HTTPClientError."""

    def test_can_instantiate(self) -> None:
        """Should be able to create an error."""
        error = HTTPClientError("test")
        assert "test" in str(error)
