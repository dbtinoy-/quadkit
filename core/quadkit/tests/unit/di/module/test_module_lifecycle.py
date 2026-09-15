"""Tests for Module lifecycle hooks."""

from __future__ import annotations

import pytest

from quadkit.di.module.base import Module
from quadkit.di.module.decorator import module


class TestModuleLifecycleHooks:
    """Test on_module_booted and on_module_shutdown lifecycle hooks."""

    @pytest.mark.asyncio
    async def test_on_module_booted_default_is_noop(self) -> None:
        """Test that default on_module_booted is a no-op."""

        @module()
        class MyModule(Module):
            pass

        # Should not raise
        await MyModule.on_module_booted()

    @pytest.mark.asyncio
    async def test_on_module_shutdown_default_is_noop(self) -> None:
        """Test that default on_module_shutdown is a no-op."""

        @module()
        class MyModule(Module):
            pass

        # Should not raise
        await MyModule.on_module_shutdown()

    @pytest.mark.asyncio
    async def test_on_module_booted_can_be_overridden(self) -> None:
        """Test that on_module_booted can be overridden in subclasses."""
        booted = []

        @module()
        class MyModule(Module):
            @classmethod
            async def on_module_booted(cls) -> None:
                booted.append(cls.__name__)

        await MyModule.on_module_booted()
        assert booted == ["MyModule"]

    @pytest.mark.asyncio
    async def test_on_module_shutdown_can_be_overridden(self) -> None:
        """Test that on_module_shutdown can be overridden in subclasses."""
        shutdown = []

        @module()
        class MyModule(Module):
            @classmethod
            async def on_module_shutdown(cls) -> None:
                shutdown.append(cls.__name__)

        await MyModule.on_module_shutdown()
        assert shutdown == ["MyModule"]
