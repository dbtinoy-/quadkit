"""Integration tests for Module lifecycle hooks (on_module_booted / on_module_shutdown).

Tests verify that:
- on_module_booted() fires after all providers finish booting
- on_module_shutdown() fires before providers are shut down
- Hooks are called in module-graph iteration order (boot) and reversed order (shutdown)
- Hook errors are swallowed and do NOT crash boot or shutdown
"""

from __future__ import annotations

import pytest

from quadkit.app import Application
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.module import DynamicModule, Module, module
from quadkit.di.provider import Provider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(name: str) -> type[Provider]:
    """Factory for minimal no-op Provider classes with unique names."""

    class _NoopProvider(Provider):
        priority = ProviderPriority.APPLICATION

        async def register(self, container: ContainerRegistrarProtocol) -> None:
            pass

        async def boot(self, container: ContainerResolverProtocol) -> None:
            pass

        async def shutdown(self) -> None:
            pass

    _NoopProvider.name = name  # type: ignore[attr-defined]
    _NoopProvider.__name__ = f"_NoopProvider_{name}"
    return _NoopProvider


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestModuleLifecycleHooks:
    """Integration tests for Module.on_module_booted and on_module_shutdown."""

    @pytest.mark.asyncio
    async def test_on_module_booted_called_after_app_boot(self) -> None:
        """on_module_booted fires after the app finishes booting."""
        booted_flags: list[bool] = []

        _Provider = _make_provider("boot_flag_provider")

        @module(providers=[_Provider], exports=[])
        class _BootFlagModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[_Provider], exports=[])

            @classmethod
            async def on_module_booted(cls) -> None:
                booted_flags.append(True)

        app = Application(name="test-booted")
        app.add_module(_BootFlagModule)
        await app.start()
        try:
            assert booted_flags == [True], "on_module_booted was not called after boot"
        finally:
            await app.stop()

    @pytest.mark.asyncio
    async def test_on_module_shutdown_called_during_app_shutdown(self) -> None:
        """on_module_shutdown fires when the app is stopped."""
        shutdown_flags: list[bool] = []

        _Provider = _make_provider("shutdown_flag_provider")

        @module(providers=[_Provider], exports=[])
        class _ShutdownFlagModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[_Provider], exports=[])

            @classmethod
            async def on_module_shutdown(cls) -> None:
                shutdown_flags.append(True)

        app = Application(name="test-shutdown")
        app.add_module(_ShutdownFlagModule)
        await app.start()
        try:
            assert shutdown_flags == [], "shutdown hook should not fire during boot"
            await app.stop()
            assert shutdown_flags == [True], "on_module_shutdown was not called during stop"
        finally:
            # Ensure app.stop() is called even if assertions fail (idempotent)
            from quadkit.app import AppState

            if app._state != AppState.STOPPED:  # noqa: SLF001
                await app.stop()

    @pytest.mark.asyncio
    async def test_hooks_called_in_topological_order(self) -> None:
        """Boot hooks fire in module-graph order: root module (child) before its dependency.

        The compiled graph stores modules in collection order — the root module
        (passed to app.add_module) is inserted first, its imports second.
        on_module_booted iterates nodes in that order.
        """
        boot_order: list[str] = []

        _ParentProvider = _make_provider("topo_parent_provider")
        _ChildProvider = _make_provider("topo_child_provider")

        @module(providers=[_ParentProvider], exports=[])
        class _ParentModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(
                    module=cls, providers=[_ParentProvider], exports=[]
                )

            @classmethod
            async def on_module_booted(cls) -> None:
                boot_order.append("ParentModule")

        @module(providers=[_ChildProvider], imports=[_ParentModule], exports=[])
        class _ChildModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(
                    module=cls,
                    providers=[_ChildProvider],
                    imports=[_ParentModule],
                    exports=[],
                )

            @classmethod
            async def on_module_booted(cls) -> None:
                boot_order.append("ChildModule")

        # ChildModule is the root; ParentModule is its import
        app = Application(name="test-topo-boot")
        app.add_module(_ChildModule)
        await app.start()
        try:
            assert len(boot_order) == 2, f"Expected 2 hooks, got {boot_order}"
            # Root module (ChildModule) fires before its dependency (ParentModule)
            child_idx = boot_order.index("ChildModule")
            parent_idx = boot_order.index("ParentModule")
            assert child_idx < parent_idx, (
                f"Expected ChildModule before ParentModule in boot, got: {boot_order}"
            )
        finally:
            await app.stop()

    @pytest.mark.asyncio
    async def test_shutdown_hooks_called_in_reverse_topological_order(self) -> None:
        """Shutdown hooks fire in reversed graph order: dependency before root module.

        on_module_shutdown iterates nodes in reverse — since boot iterates
        [Child, Parent], shutdown iterates [Parent, Child].
        """
        shutdown_order: list[str] = []

        _ParentProvider = _make_provider("rev_parent_provider")
        _ChildProvider = _make_provider("rev_child_provider")

        @module(providers=[_ParentProvider], exports=[])
        class _RevParentModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(
                    module=cls, providers=[_ParentProvider], exports=[]
                )

            @classmethod
            async def on_module_shutdown(cls) -> None:
                shutdown_order.append("RevParentModule")

        @module(providers=[_ChildProvider], imports=[_RevParentModule], exports=[])
        class _RevChildModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(
                    module=cls,
                    providers=[_ChildProvider],
                    imports=[_RevParentModule],
                    exports=[],
                )

            @classmethod
            async def on_module_shutdown(cls) -> None:
                shutdown_order.append("RevChildModule")

        # RevChildModule is the root; RevParentModule is its import
        app = Application(name="test-rev-shutdown")
        app.add_module(_RevChildModule)
        await app.start()
        await app.stop()

        assert len(shutdown_order) == 2, (
            f"Expected 2 shutdown hooks, got {shutdown_order}"
        )
        # Shutdown is reversed graph order: dependency (Parent) fires before root (Child)
        parent_idx = shutdown_order.index("RevParentModule")
        child_idx = shutdown_order.index("RevChildModule")
        assert parent_idx < child_idx, (
            f"Expected RevParentModule before RevChildModule in shutdown, got: {shutdown_order}"
        )

    @pytest.mark.asyncio
    async def test_hook_error_does_not_crash_boot(self) -> None:
        """A RuntimeError raised in on_module_booted must not prevent the app from starting."""
        _Provider = _make_provider("error_boot_provider")

        @module(providers=[_Provider], exports=[])
        class _ErrorBootModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[_Provider], exports=[])

            @classmethod
            async def on_module_booted(cls) -> None:
                raise RuntimeError("hook failed")

        app = Application(name="test-error-boot")
        app.add_module(_ErrorBootModule)

        # Must not raise — hook errors are caught and logged as warnings
        await app.start()
        try:
            from quadkit.app import AppState

            assert app._state == AppState.RUNNING  # noqa: SLF001
        finally:
            await app.stop()

    @pytest.mark.asyncio
    async def test_hook_error_does_not_crash_shutdown(self) -> None:
        """A RuntimeError raised in on_module_shutdown must not prevent the app from stopping."""
        _Provider = _make_provider("error_shutdown_provider")

        @module(providers=[_Provider], exports=[])
        class _ErrorShutdownModule(Module):
            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[_Provider], exports=[])

            @classmethod
            async def on_module_shutdown(cls) -> None:
                raise RuntimeError("shutdown hook failed")

        app = Application(name="test-error-shutdown")
        app.add_module(_ErrorShutdownModule)
        await app.start()

        # Must not raise — shutdown hook errors are caught and logged as warnings
        await app.stop()

        from quadkit.app import AppState

        assert app._state == AppState.STOPPED  # noqa: SLF001
