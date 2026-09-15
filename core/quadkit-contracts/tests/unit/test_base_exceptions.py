"""Tests for contract base exceptions."""

import pytest
from quadkit.contracts.exceptions.base import QuadkitError


class TestQuadkitError:
    def test_quadkit_error_default(self) -> None:
        exc = QuadkitError()
        assert exc.code == "QK_ERR_CORE_001"
        assert exc.message == "An internal error occurred"
        assert exc.details == {}
        assert exc.cause is None
        assert exc.hint is None

    def test_quadkit_error_with_message(self) -> None:
        exc = QuadkitError(message="Custom error")
        assert exc.message == "Custom error"

    def test_quadkit_error_with_details(self) -> None:
        exc = QuadkitError(details={"key": "value"})
        assert exc.details == {"key": "value"}

    def test_quadkit_error_with_cause(self) -> None:
        original = ValueError("original")
        exc = QuadkitError(cause=original)
        assert exc.cause is original

    def test_quadkit_error_with_hint(self) -> None:
        exc = QuadkitError(hint="Try again later")
        assert exc.hint == "Try again later"

    def test_quadkit_error_str(self) -> None:
        exc = QuadkitError(message="Test error")
        assert str(exc) == "[QK_ERR_CORE_001] Test error"

    def test_quadkit_error_repr(self) -> None:
        exc = QuadkitError(message="Test error")
        assert "QuadkitError" in repr(exc)
        assert "QK_ERR_CORE_001" in repr(exc)

    def test_quadkit_error_to_dict(self) -> None:
        exc = QuadkitError(message="Test", details={"key": "value"})
        d = exc.to_dict()
        assert d["code"] == "QK_ERR_CORE_001"
        assert d["message"] == "Test"
        assert d["details"] == {"key": "value"}

    def test_quadkit_error_to_dict_with_hint(self) -> None:
        exc = QuadkitError(message="Test", hint="Try again")
        d = exc.to_dict()
        assert d["hint"] == "Try again"

    def test_quadkit_error_to_dict_with_cause(self) -> None:
        original = ValueError("original error")
        exc = QuadkitError(message="Test", cause=original)
        d = exc.to_dict()
        assert "cause" in d
        assert d["cause"]["type"] == "ValueError"

    def test_quadkit_error_with_details_method(self) -> None:
        exc = QuadkitError(message="Test", details={"key1": "value1"})
        exc2 = exc.with_details(key2="value2")
        assert exc2.details["key1"] == "value1"
        assert exc2.details["key2"] == "value2"
        assert exc2.code == "QK_ERR_CORE_001"

    def test_quadkit_error_with_hint_method(self) -> None:
        exc = QuadkitError(message="Test")
        exc2 = exc.with_hint("Try again")
        assert exc2.hint == "Try again"

    def test_quadkit_error_with_cause_method(self) -> None:
        original = ValueError("original")
        exc = QuadkitError(message="Test")
        exc2 = exc.with_cause(original)
        assert exc2.cause is original

    def test_quadkit_error_format(self) -> None:
        exc = QuadkitError(message="Test error", details={"key": "value"})
        formatted = exc.format()
        assert "Test error" in formatted
        assert "key: value" in formatted

    def test_quadkit_error_format_with_hint(self) -> None:
        exc = QuadkitError(message="Test", hint="Try again")
        formatted = exc.format()
        assert "Hint: Try again" in formatted
