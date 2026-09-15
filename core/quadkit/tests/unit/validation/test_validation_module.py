from __future__ import annotations

from quadkit.di.module import DynamicModule
from quadkit.validation import ValidationModule


class TestValidationModule:
    def test_configure_returns_dynamic_module(self) -> None:
        result = ValidationModule.configure()

        assert isinstance(result, DynamicModule)
        assert result.module is ValidationModule
        assert result.providers == []
        assert result.exports == []

    def test_stub_returns_dynamic_module(self) -> None:
        result = ValidationModule.stub()

        assert isinstance(result, DynamicModule)
        assert result.module is ValidationModule
        assert result.providers == []
        assert result.exports == []

    def test_legacy_for_root_factory_is_removed(self) -> None:
        assert not hasattr(ValidationModule, "for_root")
