"""Tests for core constants."""

import pytest

from quadkit.primitives.constants import (
    REQUEST_ID_KEY,
    REQUEST_METHOD_KEY,
    REQUEST_PATH_KEY,
    REQUEST_START_TIME_KEY,
    SPAN_ID_KEY,
    TENANT_ID_KEY,
    TRACE_ID_KEY,
    USER_ID_KEY,
)


class TestCoreConstants:
    """Tests for core constants."""

    def test_request_id_key(self) -> None:
        """Test request ID key."""
        assert REQUEST_ID_KEY == "request_id"
        assert isinstance(REQUEST_ID_KEY, str)

    def test_tenant_id_key(self) -> None:
        """Test tenant ID key."""
        assert TENANT_ID_KEY == "tenant_id"
        assert isinstance(TENANT_ID_KEY, str)

    def test_trace_id_key(self) -> None:
        """Test trace ID key."""
        assert TRACE_ID_KEY == "trace_id"
        assert isinstance(TRACE_ID_KEY, str)

    def test_span_id_key(self) -> None:
        """Test span ID key."""
        assert SPAN_ID_KEY == "span_id"
        assert isinstance(SPAN_ID_KEY, str)

    def test_user_id_key(self) -> None:
        """Test user ID key."""
        assert USER_ID_KEY == "user_id"
        assert isinstance(USER_ID_KEY, str)

    def test_request_path_key(self) -> None:
        """Test request path key."""
        assert REQUEST_PATH_KEY == "request_path"
        assert isinstance(REQUEST_PATH_KEY, str)

    def test_request_method_key(self) -> None:
        """Test request method key."""
        assert REQUEST_METHOD_KEY == "request_method"
        assert isinstance(REQUEST_METHOD_KEY, str)

    def test_request_start_time_key(self) -> None:
        """Test request start time key."""
        assert REQUEST_START_TIME_KEY == "request_start_time"
        assert isinstance(REQUEST_START_TIME_KEY, str)

    def test_all_keys_unique(self) -> None:
        """Test all keys are unique."""
        keys = [
            REQUEST_ID_KEY,
            TENANT_ID_KEY,
            TRACE_ID_KEY,
            SPAN_ID_KEY,
            USER_ID_KEY,
            REQUEST_PATH_KEY,
            REQUEST_METHOD_KEY,
            REQUEST_START_TIME_KEY,
        ]
        assert len(keys) == len(set(keys))

    def test_constants_exported(self) -> None:
        """Test that all constants are in __all__."""
        from quadkit.primitives.constants import __all__

        assert "REQUEST_ID_KEY" in __all__
        assert "USER_ID_KEY" in __all__
        assert "TENANT_ID_KEY" in __all__
