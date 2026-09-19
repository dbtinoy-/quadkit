from __future__ import annotations

from quadkit.di.module import DynamicModule
from quadkit.domain import DomainModule


class TestDomainModule:
    def test_configure_returns_dynamic_module(self) -> None:
        result = DomainModule.configure()

        assert isinstance(result, DynamicModule)
        assert result.module is DomainModule
        assert result.providers == []
        assert result.exports == []

    def test_stub_returns_dynamic_module(self) -> None:
        result = DomainModule.stub()

        assert isinstance(result, DynamicModule)
        assert result.module is DomainModule
        assert result.providers == []
        assert result.exports == []

    def test_legacy_for_root_factory_is_removed(self) -> None:
        assert not hasattr(DomainModule, "for_root")
