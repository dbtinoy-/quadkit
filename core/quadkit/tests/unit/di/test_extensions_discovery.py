"""DI extension discovery: ProviderScanner, import_string."""

from __future__ import annotations

import pytest

from quadkit.di.extensions.discovery import (
    ProviderScanner,
    _import_namespace,
    import_string,
)
from quadkit.di.provider import Provider, ProviderPriority


class _AlphaProvider(Provider):
    name = "alpha"
    priority = ProviderPriority.NORMAL

    def __init__(self, config: object | None = None) -> None:
        super().__init__()
        self.config = config


class _BetaProvider(Provider):
    name = "beta"

    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def from_config(cls, config: object) -> _BetaProvider:
        return cls()


class TestImportString:
    def test_class_path(self) -> None:
        assert import_string("quadkit.security.provider.SecurityProvider") is not None

    def test_module_attribute(self) -> None:
        assert import_string("quadkit.di.provider.Provider") is Provider

    def test_invalid_path_raises(self) -> None:
        with pytest.raises(ImportError, match="not a valid dotted"):
            import_string("no_dots_here")

    def test_missing_attribute_raises(self) -> None:
        with pytest.raises(ImportError, match="no attribute"):
            import_string("quadkit.di.provider.DoesNotExist")


class TestImportNamespace:
    def test_package_import(self) -> None:
        modules = _import_namespace("quadkit.security")
        assert any(m.__name__ == "quadkit.security" for m in modules)

    def test_missing_namespace(self) -> None:
        assert _import_namespace("definitely.not.a.package") == []


class TestProviderScanner:
    def test_scan_finds_providers(self) -> None:
        found = ProviderScanner.scan("quadkit.security")
        from quadkit.security import SecurityProvider

        assert SecurityProvider in found

    def test_scan_excludes_base_and_abstract(self) -> None:
        found = ProviderScanner.scan("quadkit.security")
        assert Provider not in found
        assert all(not issubclass(c, _BetaProvider) for c in found)

    def test_scan_missing_namespace_empty(self) -> None:
        assert ProviderScanner.scan("definitely.not.a.package") == []

    def test_instantiate_with_config_param(self) -> None:
        p = ProviderScanner.instantiate(_AlphaProvider, "cfg")
        assert isinstance(p, _AlphaProvider)
        assert p.config == "cfg"

    def test_instantiate_from_config_classmethod(self) -> None:
        p = ProviderScanner.instantiate(_BetaProvider, "cfg")
        assert isinstance(p, _BetaProvider)

    def test_instantiate_no_params(self) -> None:
        p = ProviderScanner.instantiate(_BetaProvider, None)
        assert isinstance(p, _BetaProvider)
