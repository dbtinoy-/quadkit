"""Tests for context protocols."""

from __future__ import annotations

from quadkit.contracts.core.context import ContextProtocol, RequestContextProtocol


class TestContextProtocol:
    """Tests for ContextProtocol."""

    def test_has_register_key_method(self) -> None:
        assert hasattr(ContextProtocol, "register_key")

    def test_has_set_method(self) -> None:
        assert hasattr(ContextProtocol, "set")

    def test_has_get_method(self) -> None:
        assert hasattr(ContextProtocol, "get")

    def test_has_reset_method(self) -> None:
        assert hasattr(ContextProtocol, "reset")

    def test_has_get_all_method(self) -> None:
        assert hasattr(ContextProtocol, "get_all")


class TestRequestContextProtocol:
    def test_request_context_protocol_has_identity_fields(self) -> None:
        assert "user_id" in RequestContextProtocol.__annotations__
        assert "tenant_id" in RequestContextProtocol.__annotations__
