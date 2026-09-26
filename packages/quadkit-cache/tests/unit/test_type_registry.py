"""Tests for the @cacheable type registry (security D3)."""

from __future__ import annotations

import pytest

from quadkit.cache.serialization.type_registry import DEFAULT_REGISTRY, TypeRegistry


class _SampleModel:
    """Sample model exposing the model_validate protocol."""

    @classmethod
    def model_validate(cls, data: dict) -> _SampleModel:
        return cls()


class _NotAValidatedModel:  # noqa: N801
    pass


class TestTypeRegistry:
    """Test the TypeRegistry registration boundary."""

    def test_register_validates_model_validate(self) -> None:
        registry = TypeRegistry()
        registry.register(_SampleModel)
        assert (
            registry.get(_SampleModel.__module__, _SampleModel.__qualname__)
            is _SampleModel
        )

    def test_register_rejects_missing_model_validate(self) -> None:
        registry = TypeRegistry()
        with pytest.raises(TypeError):
            registry.register(_NotAValidatedModel)

    def test_get_unknown_tag_returns_none(self) -> None:
        registry = TypeRegistry()
        registry.register(_SampleModel)
        assert registry.get(_SampleModel.__module__, "Missing") is None

    def test_default_registry_starts_deny_all(self) -> None:
        DEFAULT_REGISTRY.clear()
        assert DEFAULT_REGISTRY.get("any.module", "AnyClass") is None

    def test_clear_removes_registered_types(self) -> None:
        registry = TypeRegistry()
        registry.register(_SampleModel)
        registry.clear()
        assert registry.get(_SampleModel.__module__, _SampleModel.__qualname__) is None
