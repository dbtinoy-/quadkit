"""Tests for specification protocol."""

from __future__ import annotations

from quadkit.contracts.domain.specification import SpecificationProtocol


class TestSpecificationProtocol:
    """Tests for SpecificationProtocol."""

    def test_is_runtime_checkable(self) -> None:
        assert hasattr(SpecificationProtocol, "__protocol_attrs__") or hasattr(SpecificationProtocol, "__annotations__")

    def test_has_is_satisfied_by_method(self) -> None:
        assert hasattr(SpecificationProtocol, "is_satisfied_by")

    def test_has_and_method(self) -> None:
        assert hasattr(SpecificationProtocol, "__and__")

    def test_has_or_method(self) -> None:
        assert hasattr(SpecificationProtocol, "__or__")

    def test_has_invert_method(self) -> None:
        assert hasattr(SpecificationProtocol, "__invert__")