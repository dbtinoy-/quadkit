"""Unit tests for runtime protocol validation (validation/protocols.py)."""

from __future__ import annotations

from typing import Protocol

import pytest

from quadkit.sql.validation.protocols import (
    ProtocolValidationError,
    validate_protocol,
)


class GreeterProtocol(Protocol):
    def greet(self, name: str) -> str: ...

    def farewell(self, name: str) -> str: ...


class GoodGreeter:
    def greet(self, name: str) -> str:
        return f"hello {name}"

    def farewell(self, name: str) -> str:
        return f"bye {name}"


class MissingMethod:
    def greet(self, name: str) -> str:
        return f"hello {name}"


class WrongArity:
    def greet(self) -> str:
        return "hello"

    def farewell(self, name: str) -> str:
        return "bye"


class WrongParamName:
    def greet(self, who: str) -> str:
        return f"hello {who}"

    def farewell(self, name: str) -> str:
        return "bye"


class NotCallable:
    greet: Any = "not a function"
    farewell: Any = "not a function"


class TestValidateProtocol:
    def test_valid_object_passes(self) -> None:
        assert validate_protocol(GoodGreeter(), GreeterProtocol) is True

    def test_missing_method_raises_with_details(self) -> None:
        obj = MissingMethod()
        with pytest.raises(ProtocolValidationError) as excinfo:
            validate_protocol(obj, GreeterProtocol)
        err = excinfo.value
        assert err.missing_methods == ["farewell"]
        assert err.protocol is GreeterProtocol
        assert err.obj is obj
        assert "MissingMethod doesn't implement GreeterProtocol" in str(err)
        assert "farewell" in str(err)

    def test_missing_method_returns_false_when_not_raising(self) -> None:
        assert (
            validate_protocol(MissingMethod(), GreeterProtocol, raise_on_error=False)
            is False
        )

    def test_wrong_signature_reported(self) -> None:
        with pytest.raises(ProtocolValidationError) as excinfo:
            validate_protocol(WrongArity(), GreeterProtocol)
        assert "greet (wrong signature)" in excinfo.value.missing_methods

    def test_wrong_param_name_reported(self) -> None:
        with pytest.raises(ProtocolValidationError) as excinfo:
            validate_protocol(WrongParamName(), GreeterProtocol)
        assert "greet (wrong signature)" in excinfo.value.missing_methods

    def test_non_callable_attribute_reported(self) -> None:
        with pytest.raises(ProtocolValidationError) as excinfo:
            validate_protocol(NotCallable(), GreeterProtocol)
        methods = excinfo.value.missing_methods
        assert "greet (not callable)" in methods
        assert "farewell (not callable)" in methods
