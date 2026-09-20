"""Unit tests for quadkit.app.discovery — provider, controller, and injectable scanning."""

from __future__ import annotations

import sys
import types

import pytest

from quadkit.app.discovery import (
    discover_injectables,
    discover_providers,
)
from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.decorators import INJECTABLE_ATTR
from quadkit.di.provider import Provider
from quadkit.web.routing.discovery import (
    discover_controllers,
    discover_websocket_handlers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLEANUP_PREFIXES: list[str] = []


def _make_pkg(name: str, classes: dict[str, type]) -> types.ModuleType:
    """Inject a fake package into sys.modules with the given classes.

    Each class has its ``__module__`` set to *name* so ``_collect_subclasses``
    recognises them as belonging to the package.
    """
    mod = types.ModuleType(name)
    mod.__path__ = []  # signals that this is a package (not a plain module)
    for attr, cls in classes.items():
        cls.__module__ = name
        setattr(mod, attr, cls)
    sys.modules[name] = mod
    _CLEANUP_PREFIXES.append(name)
    return mod


@pytest.fixture(autouse=True)
def _cleanup_sys_modules() -> types.GeneratorType:
    """Remove any fake packages injected during a test after it finishes."""
    yield
    for prefix in _CLEANUP_PREFIXES:
        keys_to_remove = [
            k for k in sys.modules if k == prefix or k.startswith(prefix + ".")
        ]
        for key in keys_to_remove:
            del sys.modules[key]
    _CLEANUP_PREFIXES.clear()


# ---------------------------------------------------------------------------
# discover_providers
# ---------------------------------------------------------------------------


class TestDiscoverProviders:
    def test_nonexistent_package_returns_empty_list(self) -> None:
        result = discover_providers(["quadkit_test_nonexistent_pkg_xyz"])
        assert result == []

    def test_finds_provider_subclass_with_default_init(self) -> None:
        class MyProvider(Provider):
            name = "my"

            async def register(self, container):  # type: ignore[override]
                pass

        _make_pkg("test_discovery_providers_simple", {"MyProvider": MyProvider})

        result = discover_providers(["test_discovery_providers_simple"])

        assert len(result) == 1
        assert isinstance(result[0], MyProvider)

    def test_skips_provider_requiring_constructor_args(self) -> None:
        class RequiresArgProvider(Provider):
            name = "req"

            def __init__(self, required_arg: str) -> None:
                # intentionally does not call super().__init__() — cannot be
                # auto-instantiated without a value for required_arg
                self._required = required_arg

        _make_pkg(
            "test_discovery_providers_skip",
            {"RequiresArgProvider": RequiresArgProvider},
        )

        result = discover_providers(["test_discovery_providers_skip"])

        assert result == []

    def test_deduplicates_same_class_across_repeated_calls(self) -> None:
        class DedupProvider(Provider):
            name = "dedup"

        _make_pkg("test_discovery_providers_dedup", {"DedupProvider": DedupProvider})

        result = discover_providers(
            ["test_discovery_providers_dedup", "test_discovery_providers_dedup"]
        )

        assert len(result) == 1

    def test_returns_empty_list_for_empty_package_list(self) -> None:
        result = discover_providers([])
        assert result == []


# ---------------------------------------------------------------------------
# discover_controllers
# ---------------------------------------------------------------------------


class TestDiscoverControllers:
    def test_nonexistent_package_returns_empty_list(self) -> None:
        result = discover_controllers(["quadkit_test_nonexistent_ctrl_pkg_xyz"])
        assert result == []

    def test_returns_empty_list_for_empty_package_list(self) -> None:
        result = discover_controllers([])
        assert result == []


class TestDiscoverWebSocketHandlers:
    def test_finds_decorated_handler_classes(self) -> None:
        class ChatHandler:
            _is_websocket_handler = True
            _ws_path = "/ws/chat/{room_id}"

        package = _make_pkg(
            "test_discovery_websocket_pkg", {"ChatHandler": ChatHandler}
        )

        assert discover_websocket_handlers([package.__name__]) == [ChatHandler]

    def test_returns_empty_list_for_empty_package_list(self) -> None:
        assert discover_websocket_handlers([]) == []


# ---------------------------------------------------------------------------
# discover_injectables
# ---------------------------------------------------------------------------


class TestDiscoverInjectables:
    def test_finds_singleton_decorated_class(self) -> None:
        from quadkit.di.decorators import singleton

        @singleton
        class MySingletonService:
            pass

        _make_pkg(
            "test_discovery_inj_singleton", {"MySingletonService": MySingletonService}
        )

        result = discover_injectables(["test_discovery_inj_singleton"])

        assert len(result) == 1
        found_cls, found_scope = result[0]
        assert found_cls is MySingletonService
        assert found_scope == ServiceScope.SINGLETON

    def test_finds_injectable_decorated_class(self) -> None:
        from quadkit.di.decorators import injectable

        @injectable
        class MyTransientService:
            pass

        _make_pkg(
            "test_discovery_inj_transient", {"MyTransientService": MyTransientService}
        )

        result = discover_injectables(["test_discovery_inj_transient"])

        assert len(result) == 1
        found_cls, found_scope = result[0]
        assert found_cls is MyTransientService
        assert found_scope == ServiceScope.TRANSIENT

    def test_ignores_plain_class_without_decorator(self) -> None:
        class PlainService:
            pass

        assert not hasattr(PlainService, INJECTABLE_ATTR)

        _make_pkg("test_discovery_inj_plain", {"PlainService": PlainService})

        result = discover_injectables(["test_discovery_inj_plain"])

        assert result == []

    def test_nonexistent_package_returns_empty_list(self) -> None:
        result = discover_injectables(["quadkit_test_nonexistent_inj_pkg_xyz"])
        assert result == []

    def test_multiple_decorated_classes_all_returned(self) -> None:
        from quadkit.di.decorators import injectable, singleton

        @singleton
        class Alpha:
            pass

        @injectable
        class Beta:
            pass

        _make_pkg("test_discovery_inj_multi", {"Alpha": Alpha, "Beta": Beta})

        result = discover_injectables(["test_discovery_inj_multi"])
        found_classes = {cls for cls, _ in result}

        assert Alpha in found_classes
        assert Beta in found_classes
        assert len(result) == 2
