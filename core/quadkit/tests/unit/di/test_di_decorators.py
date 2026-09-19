"""Tests for DI decorators: @injectable, @singleton, @scoped, @transient, @inject, @provider."""

import pytest

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.decorators import (
    INJECT_ATTR,
    INJECTABLE_ATTR,
    inject,
    injectable,
    provider,
    scoped,
    singleton,
    transient,
)
from quadkit.di.provider import Provider


class TestInjectableDecorator:
    """Tests for the @injectable decorator."""

    def test_injectable_default_scope_is_transient(self) -> None:
        """@injectable without arguments creates transient service."""

        @injectable
        class TransientService:
            pass

        metadata = getattr(TransientService, INJECTABLE_ATTR)
        assert metadata["scope"] == ServiceScope.TRANSIENT
        assert metadata["name"] is None

    def test_injectable_with_explicit_scope(self) -> None:
        """@injectable with explicit scope parameter."""

        @injectable(scope=ServiceScope.SINGLETON)
        class SingletonService:
            pass

        metadata = getattr(SingletonService, INJECTABLE_ATTR)
        assert metadata["scope"] == ServiceScope.SINGLETON

    def test_injectable_with_name(self) -> None:
        """@injectable with custom name."""

        @injectable(name="custom_service")
        class NamedService:
            pass

        metadata = getattr(NamedService, INJECTABLE_ATTR)
        assert metadata["name"] == "custom_service"

    def test_injectable_with_scope_and_name(self) -> None:
        """@injectable with both scope and name."""

        @injectable(scope=ServiceScope.SCOPED, name="scoped_service")
        class ScopedNamedService:
            pass

        metadata = getattr(ScopedNamedService, INJECTABLE_ATTR)
        assert metadata["scope"] == ServiceScope.SCOPED
        assert metadata["name"] == "scoped_service"

    def test_injectable_can_be_used_without_parens(self) -> None:
        """@injectable can be applied without parentheses."""

        @injectable
        class MinimalService:
            pass

        metadata = getattr(MinimalService, INJECTABLE_ATTR)
        assert metadata["scope"] == ServiceScope.TRANSIENT


class TestSingletonDecorator:
    """Tests for the @singleton decorator."""

    def test_singleton_sets_singleton_scope(self) -> None:
        """@singleton decorator sets SINGLETON scope."""

        @singleton
        class MySingleton:
            pass

        metadata = getattr(MySingleton, INJECTABLE_ATTR)
        assert metadata["scope"] == ServiceScope.SINGLETON


class TestScopedDecorator:
    """Tests for the @scoped decorator."""

    def test_scoped_sets_scoped_scope(self) -> None:
        """@scoped decorator sets SCOPED scope."""

        @scoped
        class MyScoped:
            pass

        metadata = getattr(MyScoped, INJECTABLE_ATTR)
        assert metadata["scope"] == ServiceScope.SCOPED


class TestTransientDecorator:
    """Tests for the @transient decorator."""

    def test_transient_sets_transient_scope(self) -> None:
        """@transient decorator sets TRANSIENT scope."""

        @transient
        class MyTransient:
            pass

        metadata = getattr(MyTransient, INJECTABLE_ATTR)
        assert metadata["scope"] == ServiceScope.TRANSIENT


class TestInjectDecorator:
    """Tests for the @inject decorator."""

    def test_inject_on_class_marks_it(self) -> None:
        """@inject on a class marks it for constructor injection."""

        @inject
        class MyClass:
            pass

        assert getattr(MyClass, INJECT_ATTR, False) is True

    @pytest.mark.asyncio
    async def test_inject_on_async_function_raises_for_sync(self) -> None:
        """@inject on sync function raises TypeError."""

        def sync_func() -> None:
            pass

        with pytest.raises(
            TypeError, match="@inject decorator requires async functions"
        ):
            inject(sync_func)

    def test_inject_on_async_function_returns_wrapper(self) -> None:
        """@inject on async function returns wrapped function."""

        @inject
        async def async_func() -> None:
            pass

        # The wrapper exists and is a coroutine function
        assert hasattr(async_func, "__wrapped__")


class TestProviderDecorator:
    """Tests for the @provider decorator."""

    def test_provider_sets_name(self) -> None:
        """@provider decorator can set custom name."""

        @provider(name="custom_provider")
        class MyProvider(Provider):
            pass

        # The decorator modifies the __init__ to set name
        instance = MyProvider()
        assert instance.name == "custom_provider"

    def test_provider_sets_priority(self) -> None:
        """@provider decorator can set priority."""

        @provider(priority=ProviderPriority.CRITICAL)
        class CriticalProvider(Provider):
            pass

        instance = CriticalProvider()
        assert instance.priority == ProviderPriority.CRITICAL

    def test_provider_sets_dependencies(self) -> None:
        """@provider decorator can set dependencies."""

        @provider(dependencies=("dep1", "dep2"))
        class DependentProvider(Provider):
            pass

        instance = DependentProvider()
        assert instance.dependencies == ("dep1", "dep2")

    def test_provider_with_all_options(self) -> None:
        """@provider decorator with name, priority, and dependencies."""

        @provider(
            name="full_provider",
            priority=ProviderPriority.DOMAIN,
            dependencies=("dep1",),
        )
        class FullProvider(Provider):
            pass

        instance = FullProvider()
        assert instance.name == "full_provider"
        assert instance.priority == ProviderPriority.DOMAIN
        assert instance.dependencies == ("dep1",)


class TestDecoratorChaining:
    """Tests for decorator combinations and chaining."""

    def test_can_combine_injectable_and_inject(self) -> None:
        """Class can be both @injectable and @inject."""

        @injectable
        @inject
        class CombinedService:
            pass

        # Both attributes should be set
        assert hasattr(CombinedService, INJECTABLE_ATTR)
        assert getattr(CombinedService, INJECT_ATTR, False) is True
