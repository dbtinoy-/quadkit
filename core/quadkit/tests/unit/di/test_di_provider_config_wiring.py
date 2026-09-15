"""Tests for DiProvider wiring of DiConfig fields."""

from __future__ import annotations

import pytest

from quadkit.contracts.exceptions import UnresolvableDependencyError
from quadkit.di.config.models import DiConfig
from quadkit.di.container import Container
from quadkit.di.integration.provider import DiProvider
from quadkit.di.resolution.resolver import ServiceResolver


class TestDiProviderBootWiring:
    """boot() applies DiConfig to resolver and container."""

    @pytest.mark.asyncio
    async def test_boot_applies_resolver_settings(self) -> None:
        container = Container()
        container.singleton(DiConfig, DiConfig(
            max_resolution_depth=33,
            debug_resolution=True,
        ))

        await DiProvider().boot(container)

        assert ServiceResolver._max_resolution_depth == 33
        assert ServiceResolver._debug_resolution is True
        ServiceResolver.configure()  # reset

    @pytest.mark.asyncio
    async def test_boot_applies_container_settings(self) -> None:
        container = Container()
        container.singleton(DiConfig, DiConfig(
            strict_mode=True,
            validate_on_register=False,
        ))

        await DiProvider().boot(container)

        assert container.strict_mode is True
        assert container.validate_on_register is False


class TestContainerStrictMode:
    """strict_mode makes resolve_optional raise on missing services."""

    @pytest.mark.asyncio
    async def test_resolve_optional_returns_none_by_default(self) -> None:
        container = Container()

        result = await container.resolve_optional(dict)

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_optional_raises_in_strict_mode(self) -> None:
        container = Container(strict_mode=True)

        with pytest.raises(UnresolvableDependencyError):
            await container.resolve_optional(dict)

    @pytest.mark.asyncio
    async def test_resolve_optional_returns_instance_in_strict_mode(self) -> None:
        container = Container(strict_mode=True)
        sentinel = object()
        container.singleton(object, sentinel)

        result = await container.resolve_optional(object)

        assert result is sentinel


class TestValidateOnRegister:
    """Registration validate=None falls back to validate_on_register."""

    def test_validate_none_uses_instance_default(self) -> None:
        from unittest.mock import patch

        container = Container(validate_on_register=False)
        with patch.object(
            container._registrar, "transient"
        ) as mock_transient:
            container.transient(dict, lambda: {})
        mock_transient.assert_called_once_with(dict, mock_transient.call_args[0][1], validate=False)

    def test_explicit_validate_overrides_instance_default(self) -> None:
        from unittest.mock import patch

        container = Container(validate_on_register=False)
        with patch.object(container._registrar, "transient") as mock_transient:
            container.transient(dict, lambda: {}, validate=True)
        mock_transient.assert_called_once_with(dict, mock_transient.call_args[0][1], validate=True)


class TestResolutionDepthCap:
    """max_resolution_depth bounds nested resolution."""

    @pytest.mark.asyncio
    async def test_depth_exceeded_raises(self) -> None:
        from quadkit.contracts.exceptions import CircularDependencyError

        container = Container()
        ServiceResolver.configure(max_resolution_depth=2)
        try:
            resolver = container._Container__service_resolver
            # Simulate a resolution stack at the configured cap: the next
            # nested resolution must be rejected as a depth overflow.
            stack = resolver._get_stack()
            stack.extend([object(), object()])
            try:
                resolver._check_circular(object())
                raise AssertionError("expected CircularDependencyError")
            except CircularDependencyError as err:
                assert "depth" in str(err).lower()
        finally:
            ServiceResolver.configure()
