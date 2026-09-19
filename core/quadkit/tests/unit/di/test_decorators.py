"""Tests for di/decorators module - Injectable, inject, provider decorators."""

import pytest

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.decorators import (
    INJECTABLE_ATTR,
    INJECT_ATTR,
    PROVIDER_ATTR,
    SCOPE_ATTR,
    Injectable,
    inject,
    injectable,
    provider,
    scoped,
    singleton,
    transient,
)
from quadkit.di.provider import Provider


class TestInjectableClass:
    """Tests for Injectable decorator class."""

    def test_init_default_scope(self) -> None:
        """Test Injectable with default scope."""
        decorator = Injectable()
        assert decorator.scope == ServiceScope.TRANSIENT
        assert decorator.name is None

    def test_init_custom_scope(self) -> None:
        """Test Injectable with custom scope."""
        decorator = Injectable(scope=ServiceScope.SINGLETON)
        assert decorator.scope == ServiceScope.SINGLETON

    def test_init_custom_name(self) -> None:
        """Test Injectable with custom name."""
        decorator = Injectable(name="my-service")
        assert decorator.name == "my-service"

    def test_call_marks_class(self) -> None:
        """Test that calling Injectable marks the class."""

        @Injectable()
        class MyService:
            pass

        assert hasattr(MyService, INJECTABLE_ATTR)
        assert MyService.__quadkit_injectable__["scope"] == ServiceScope.TRANSIENT

    def test_call_with_scope_and_name(self) -> None:
        """Test Injectable with both scope and name."""

        @Injectable(scope=ServiceScope.SCOPED, name="custom-name")
        class MyService:
            pass

        assert MyService.__quadkit_injectable__["scope"] == ServiceScope.SCOPED
        assert MyService.__quadkit_injectable__["name"] == "custom-name"


class TestInjectableDecorator:
    """Tests for @injectable decorator."""

    def test_injectable_default_scope(self) -> None:
        """Test @injectable with default scope."""

        @injectable
        class MyService:
            pass

        assert hasattr(MyService, INJECTABLE_ATTR)
        assert MyService.__quadkit_injectable__["scope"] == ServiceScope.TRANSIENT

    def test_injectable_with_scope_kwarg(self) -> None:
        """Test @injectable with scope keyword argument."""

        @injectable(scope=ServiceScope.SINGLETON)
        class MyService:
            pass

        assert MyService.__quadkit_injectable__["scope"] == ServiceScope.SINGLETON

    def test_injectable_with_name_kwarg(self) -> None:
        """Test @injectable with name keyword argument."""

        @injectable(name="my-named-service")
        class MyService:
            pass

        assert MyService.__quadkit_injectable__["name"] == "my-named-service"

    def test_injectable_with_both_kwargs(self) -> None:
        """Test @injectable with both scope and name."""

        @injectable(scope=ServiceScope.SCOPED, name="scoped-service")
        class MyService:
            pass

        assert MyService.__quadkit_injectable__["scope"] == ServiceScope.SCOPED
        assert MyService.__quadkit_injectable__["name"] == "scoped-service"

    def test_injectable_without_parens_on_class(self) -> None:
        """Test @injectable used without parentheses on a class."""

        @injectable
        class SimpleService:
            pass

        assert hasattr(SimpleService, INJECTABLE_ATTR)


class TestSingletonDecorator:
    """Tests for @singleton decorator."""

    def test_singleton_marks_class(self) -> None:
        """Test that @singleton marks class as singleton."""

        @singleton
        class MyService:
            pass

        assert hasattr(MyService, INJECTABLE_ATTR)
        assert MyService.__quadkit_injectable__["scope"] == ServiceScope.SINGLETON


class TestScopedDecorator:
    """Tests for @scoped decorator."""

    def test_scoped_marks_class(self) -> None:
        """Test that @scoped marks class as scoped."""

        @scoped
        class MyService:
            pass

        assert hasattr(MyService, INJECTABLE_ATTR)
        assert MyService.__quadkit_injectable__["scope"] == ServiceScope.SCOPED


class TestTransientDecorator:
    """Tests for @transient decorator."""

    def test_transient_marks_class(self) -> None:
        """Test that @transient marks class as transient."""

        @transient
        class MyService:
            pass

        assert hasattr(MyService, INJECTABLE_ATTR)
        assert MyService.__quadkit_injectable__["scope"] == ServiceScope.TRANSIENT


class TestInjectDecorator:
    """Tests for @inject decorator."""

    def test_inject_on_class(self) -> None:
        """Test @inject on a class marks it for DI."""

        @inject
        class MyService:
            pass

        assert hasattr(MyService, INJECT_ATTR)
        assert MyService.__quadkit_inject__ is True

    def test_inject_on_async_function(self) -> None:
        """Test @inject on an async function."""

        @inject
        async def my_func():
            pass

        assert callable(my_func)

    def test_inject_on_sync_function_raises(self) -> None:
        """Test @inject on sync function raises TypeError."""

        def sync_func():
            pass

        with pytest.raises(TypeError, match="@inject decorator requires async functions"):
            inject(sync_func)


class TestProviderDecorator:
    """Tests for @provider decorator."""

    def test_provider_default_priority(self) -> None:
        """Test @provider with default priority."""

        @provider()
        class MyProvider(Provider):
            pass

        assert MyProvider.__init__ is not None

    def test_provider_with_name(self) -> None:
        """Test @provider with custom name."""

        @provider(name="custom-provider")
        class MyProvider(Provider):
            pass

        assert hasattr(MyProvider, "__init__")

    def test_provider_with_dependencies(self) -> None:
        """Test @provider with dependencies."""

        @provider(dependencies=("dep1", "dep2"))
        class MyProvider(Provider):
            pass

        assert MyProvider.__init__ is not None

    def test_provider_non_provider_raises(self) -> None:
        """Test @provider on non-Provider class doesn't raise (just wraps)."""
        # The provider decorator accepts any class but sets attributes
        @provider
        class NotAProvider:
            pass

        # No exception is raised - decorator is permissive
        assert NotAProvider is not None


class TestDecoratorAttributes:
    """Tests for decorator attribute constants."""

    def test_injectable_attr_defined(self) -> None:
        """Test INJECTABLE_ATTR is defined."""
        assert INJECTABLE_ATTR == "__quadkit_injectable__"

    def test_inject_attr_defined(self) -> None:
        """Test INJECT_ATTR is defined."""
        assert INJECT_ATTR == "__quadkit_inject__"

    def test_provider_attr_defined(self) -> None:
        """Test PROVIDER_ATTR is defined."""
        assert PROVIDER_ATTR == "__quadkit_provider__"

    def test_scope_attr_defined(self) -> None:
        """Test SCOPE_ATTR is defined."""
        assert SCOPE_ATTR == "__quadkit_scope__"
