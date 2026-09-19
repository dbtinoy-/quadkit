"""Tests for primitives constants."""

from __future__ import annotations

from quadkit.primitives.constants import (
    REQUEST_ID_KEY,
    TENANT_ID_KEY,
    TRACE_ID_KEY,
    SPAN_ID_KEY,
    USER_ID_KEY,
    REQUEST_PATH_KEY,
    REQUEST_METHOD_KEY,
    REQUEST_START_TIME_KEY,
)


class TestContextKeys:
    """Tests for context key constants."""

    def test_request_id_key(self) -> None:
        assert REQUEST_ID_KEY == "request_id"

    def test_tenant_id_key(self) -> None:
        assert TENANT_ID_KEY == "tenant_id"

    def test_trace_id_key(self) -> None:
        assert TRACE_ID_KEY == "trace_id"

    def test_span_id_key(self) -> None:
        assert SPAN_ID_KEY == "span_id"

    def test_user_id_key(self) -> None:
        assert USER_ID_KEY == "user_id"

    def test_request_path_key(self) -> None:
        assert REQUEST_PATH_KEY == "request_path"

    def test_request_method_key(self) -> None:
        assert REQUEST_METHOD_KEY == "request_method"

    def test_request_start_time_key(self) -> None:
        assert REQUEST_START_TIME_KEY == "request_start_time"

    def test_all_keys_are_strings(self) -> None:
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
        for key in keys:
            assert isinstance(key, str)