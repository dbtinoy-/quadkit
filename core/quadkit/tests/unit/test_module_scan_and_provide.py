"""Tests for module scan= parameter and function-based @provide decorator."""

import pytest

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.module import ModuleMetadata, module
from quadkit.di.module.decorator import _create_scan_provider
from quadkit.di.provider import Provider


# ---------------------------------------------------------------------------
# Fixtures — fake injectables for scan= testing
# ---------------------------------------------------------------------------


class _FakeServiceA:
    pass


class _FakeServiceB:
    pass


# ---------------------------------------------------------------------------
# scan= parameter tests
# ---------------------------------------------------------------------------


class TestModuleScanParameter:
    """Tests for the scan= parameter on @module."""

    def test_scan_stored_in_metadata(self) -> None:
        """scan= paths are stored in ModuleMetadata."""

        @module(scan=["my_app.domain"])
        class MyModule:
            pass

        meta: ModuleMetadata = MyModule.__quadkit_module__
        assert meta.scan == ["my_app.domain"]

    def test_scan_multiple_packages(self) -> None:
        """Multiple scan packages are stored."""

        @module(scan=["my_app.domain", "my_app.infra"])
        class MyModule:
            pass

        meta: ModuleMetadata = MyModule.__quadkit_module__
        assert meta.scan == ["my_app.domain", "my_app.infra"]

    def test_scan_empty_by_default(self) -> None:
        """scan defaults to empty list."""

        @module
        class MyModule:
            pass

        meta: ModuleMetadata = MyModule.__quadkit_module__
        assert meta.scan == []

    def test_scan_in_repr(self) -> None:
        """scan paths appear in metadata __repr__."""

        @module(scan=["my_app.domain"])
        class MyModule:
            pass

        meta: ModuleMetadata = MyModule.__quadkit_module__
        assert "scan=" in repr(meta)
        assert "my_app.domain" in repr(meta)

    def test_create_scan_provider_generates_provider_class(self) -> None:
        """_create_scan_provider returns a Provider subclass."""
        injectables = [
            (_FakeServiceA, ServiceScope.SINGLETON),
            (_FakeServiceB, ServiceScope.TRANSIENT),
        ]
        provider_cls = _create_scan_provider("test_module", injectables)

        assert isinstance(provider_cls, type)
        assert issubclass(provider_cls, Provider)

    def test_create_scan_provider_instantiable(self) -> None:
        """Generated scan provider can be instantiated."""
        injectables = [(_FakeServiceA, ServiceScope.SINGLETON)]
        provider_cls = _create_scan_provider("test_module", injectables)

        instance = provider_cls()
        assert instance.name == "_scan_test_module"

    def test_scan_provider_registers_injectables(self) -> None:
        """Generated scan provider registers injectables correctly."""
        injectables = [
            (_FakeServiceA, ServiceScope.SINGLETON),
            (_FakeServiceB, ServiceScope.TRANSIENT),
        ]
        provider_cls = _create_scan_provider("test_module", injectables)

        instance = provider_cls()
        assert instance._injectables == injectables

    def test_scan_with_nonexistent_package_no_error(self) -> None:
        """scan= with a package that doesn't exist doesn't crash the decorator."""

        @module(scan=["nonexistent.package.that.does.not.exist"])
        class MyModule:
            pass

        meta: ModuleMetadata = MyModule.__quadkit_module__
        assert meta.scan == ["nonexistent.package.that.does.not.exist"]
        # No auto-generated provider since nothing was found
        assert len(meta.providers) == 0

    def test_scan_combined_with_explicit_providers(self) -> None:
        """scan= merges with explicitly declared providers."""

        class ExplicitProvider(Provider):
            name = "explicit"

        # Use a nonexistent scan path to avoid side effects
        @module(
            providers=[ExplicitProvider],
            scan=["nonexistent.package.xyz"],
        )
        class MyModule:
            pass

        meta: ModuleMetadata = MyModule.__quadkit_module__
        assert ExplicitProvider in meta.providers


# ---------------------------------------------------------------------------
# @provide decorator tests
# ---------------------------------------------------------------------------


class TestProvideDecorator:
    """Tests for the function-based @provide decorator."""

    def test_bare_provide_creates_provider_class(self) -> None:
        """@provide without args creates a Provider subclass."""
        from quadkit.di.function_provider import FunctionProvider, provide

        @provide
        def my_service() -> _FakeServiceA:
            return _FakeServiceA()

        assert isinstance(my_service, type)
        assert issubclass(my_service, FunctionProvider)

    def test_provide_with_args(self) -> None:
        """@provide(scope=...) creates a Provider subclass."""
        from quadkit.di.function_provider import FunctionProvider, provide

        @provide(scope="singleton", name="my_svc")
        def my_service() -> _FakeServiceA:
            return _FakeServiceA()

        assert isinstance(my_service, type)
        assert issubclass(my_service, FunctionProvider)

    def test_provide_instantiable(self) -> None:
        """Provider from @provide can be instantiated."""
        from quadkit.di.function_provider import provide

        @provide
        def my_service() -> _FakeServiceA:
            return _FakeServiceA()

        instance = my_service()
        assert instance.name == "my_service"

    def test_provide_custom_name(self) -> None:
        """@provide(name=...) sets the provider name."""
        from quadkit.di.function_provider import provide

        @provide(name="custom_name")
        def my_service() -> _FakeServiceA:
            return _FakeServiceA()

        instance = my_service()
        assert instance.name == "custom_name"

    def test_provide_stores_contract_type(self) -> None:
        """Provider captures the return type as contract type."""
        from quadkit.di.function_provider import provide

        @provide
        def my_service() -> _FakeServiceA:
            return _FakeServiceA()

        instance = my_service()
        assert instance._contract_type is _FakeServiceA

    def test_provide_stores_scope(self) -> None:
        """Provider captures the scope."""
        from quadkit.di.function_provider import provide

        @provide(scope="transient")
        def my_service() -> _FakeServiceA:
            return _FakeServiceA()

        instance = my_service()
        assert instance._scope == ServiceScope.TRANSIENT

    def test_provide_requires_return_annotation(self) -> None:
        """@provide raises TypeError if no return type annotation."""
        from quadkit.di.function_provider import provide

        with pytest.raises(TypeError, match="return type annotation"):

            @provide
            def my_service():
                return _FakeServiceA()

    def test_provide_in_module_providers(self) -> None:
        """@provide decorated function can be used in module providers=."""
        from quadkit.di.function_provider import provide

        @provide
        def my_service() -> _FakeServiceA:
            return _FakeServiceA()

        @module(providers=[my_service])
        class MyModule:
            pass

        meta: ModuleMetadata = MyModule.__quadkit_module__
        assert my_service in meta.providers

    @pytest.mark.asyncio
    async def test_provide_boot_calls_factory(self) -> None:
        """Provider boot() calls the factory and registers the result."""
        from unittest.mock import MagicMock

        from quadkit.di.function_provider import provide

        call_count = 0

        @provide
        def my_service() -> _FakeServiceA:
            nonlocal call_count
            call_count += 1
            return _FakeServiceA()

        instance = my_service()

        # Create a mock container
        container = MagicMock()
        container.resolve = MagicMock(side_effect=Exception("not needed"))

        await instance.boot(container)

        assert call_count == 1
        container.singleton.assert_called_once()
        registered_type, registered_value = container.singleton.call_args[0]
        assert registered_type is _FakeServiceA
        assert isinstance(registered_value, _FakeServiceA)

    @pytest.mark.asyncio
    async def test_provide_boot_resolves_parameters(self) -> None:
        """Provider boot() resolves factory parameters from the container."""
        from unittest.mock import AsyncMock, MagicMock

        from quadkit.di.function_provider import provide

        config_instance = _FakeServiceB()

        @provide
        def my_service(config: _FakeServiceB) -> _FakeServiceA:
            assert config is config_instance
            return _FakeServiceA()

        instance = my_service()

        container = MagicMock()
        container.resolve = AsyncMock(return_value=config_instance)

        await instance.boot(container)

        container.resolve.assert_awaited_once_with(_FakeServiceB)
        container.singleton.assert_called_once()

    @pytest.mark.asyncio
    async def test_provide_async_factory(self) -> None:
        """@provide works with async factory functions."""
        from unittest.mock import MagicMock

        from quadkit.di.function_provider import provide

        @provide
        async def my_service() -> _FakeServiceA:
            return _FakeServiceA()

        instance = my_service()
        container = MagicMock()

        await instance.boot(container)

        container.singleton.assert_called_once()
        registered_type, registered_value = container.singleton.call_args[0]
        assert registered_type is _FakeServiceA
        assert isinstance(registered_value, _FakeServiceA)
