from __future__ import annotations

from types import SimpleNamespace
from typing import Annotated
from unittest.mock import MagicMock

import pytest

from quadkit.contracts.exceptions.provider import ModuleVisibilityError
from quadkit.di.context import clear_module_context, set_module_context
from quadkit.di.markers import Named


class _FakeModule:
    pass


class _SomeService:
    pass


class TestContainerVisibilityEnforcement:
    """Integration tests: Container.resolve() + ContextVar visibility."""

    @pytest.fixture
    def container(self):
        """Minimal container with _SomeService registered."""
        from quadkit.di.container import Container

        c = Container()
        c.transient(_SomeService, _SomeService)
        return c

    @pytest.mark.asyncio
    async def test_standalone_resolves_normally(self, container) -> None:
        """No module context = no visibility enforcement."""
        result = await container.resolve(_SomeService)
        assert isinstance(result, _SomeService)

    @pytest.mark.asyncio
    async def test_raises_module_visibility_error_when_blocked(self, container) -> None:
        """Active module context + is_visible=False → ModuleVisibilityError."""

        class AuthModule:
            __name__ = "AuthModule"

        class FakeGraph:
            def is_visible(self, _module, _service_type) -> bool:
                return False

            def get_module(self, module_cls):
                if module_cls is _FakeModule:
                    return SimpleNamespace(name="OrderModule", imports=[AuthModule])
                if module_cls is AuthModule:
                    return SimpleNamespace(name="AuthModule", imports=[])
                return None

            def find_modules_exporting(self, service_type):
                if service_type is _SomeService:
                    return [
                        SimpleNamespace(
                            name="AuthModule",
                            imports=[],
                            exports=[_SomeService],
                        )
                    ]
                return []

        mock_graph = FakeGraph()
        tokens = set_module_context(_FakeModule, mock_graph)
        try:
            with pytest.raises(ModuleVisibilityError) as exc_info:
                await container.resolve(_SomeService)
            rendered = str(exc_info.value)
            assert "_SomeService" in rendered
            assert "Fix one of:" in rendered
            assert "Reference:" in rendered
        finally:
            clear_module_context(tokens)

    @pytest.mark.asyncio
    async def test_bypass_visibility_skips_check(self, container) -> None:
        """bypass_visibility=True resolves despite blocked visibility."""
        mock_graph = MagicMock()
        mock_graph.is_visible.return_value = False
        tokens = set_module_context(_FakeModule, mock_graph)
        try:
            result = await container.resolve(_SomeService, bypass_visibility=True)
            assert isinstance(result, _SomeService)
        finally:
            clear_module_context(tokens)

    @pytest.mark.asyncio
    async def test_allowed_visibility_resolves_normally(self, container) -> None:
        """Active module context + is_visible=True → resolves normally."""
        mock_graph = MagicMock()
        mock_graph.is_visible.return_value = True
        tokens = set_module_context(_FakeModule, mock_graph)
        try:
            result = await container.resolve(_SomeService)
            assert isinstance(result, _SomeService)
        finally:
            clear_module_context(tokens)

    @pytest.mark.asyncio
    async def test_annotated_named_binding_uses_inner_type_for_visibility(
        self, container
    ) -> None:
        """Annotated named bindings should be visible when the base contract is visible."""
        named_service = _SomeService()
        container.singleton(_SomeService, named_service, name="maps")

        mock_graph = MagicMock()
        mock_graph.is_visible.side_effect = lambda _module, service_type: (
            service_type is _SomeService
        )
        tokens = set_module_context(_FakeModule, mock_graph)
        try:
            result = await container.resolve(Annotated[_SomeService, Named("maps")])
            assert result is named_service
        finally:
            clear_module_context(tokens)
