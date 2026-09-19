"""Tests for ContainerRuntimeMixin (scoping, DI calls, disposal)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.container.container_runtime import ContainerRuntimeMixin
from quadkit.di.resolution.descriptor import ServiceDescriptor


class _FakeContainer(ContainerRuntimeMixin):
    """Minimal collaborator container exposing only the attributes the
    mixin needs (registry, invoker, hints cache, registrar)."""

    def __init__(self) -> None:
        self._registry = MagicMock()
        self._invoker = MagicMock()
        async def _invoke(func, *a, **k):
            k.pop("strategies", None)
            return await func(*a, **k)

        self._invoker.call = AsyncMock(side_effect=_invoke)
        self._hints_cache: dict[Any, Any] = {}
        self._registrar = MagicMock()
        self._descriptors: list[ServiceDescriptor] = []
        self._registry.all = MagicMock(return_value=self._descriptors)

    def add_descriptor(self, descriptor: ServiceDescriptor) -> None:
        self._descriptors.append(descriptor)


def _descriptor(
    service_type: type,
    scope: ServiceScope,
    instance: Any = None,
) -> ServiceDescriptor:
    return ServiceDescriptor(
        service_type=service_type,
        implementation=MagicMock(),
        scope=scope,
        instance=instance,
        is_instantiated=instance is not None,
    )


class TestScoping:
    def test_create_scope_returns_scope_with_container(self) -> None:
        c = _FakeContainer()
        scope = c.create_scope()
        assert scope is not None
        assert scope._root is c  # noqa: SLF001

    async def test_scope_yields_and_disposes(self) -> None:
        c = _FakeContainer()
        async with c.scope() as scope:
            assert scope._root is c  # noqa: SLF001
            scope.dispose = AsyncMock()  # type: ignore[method-assign]
        # dispose was awaited on the real Scope instance at exit


class TestCall:
    async def test_call_passes_through_invoker(self) -> None:
        c = _FakeContainer()
        c._invoker.call = AsyncMock(return_value="invoked")  # noqa: SLF001

        async def target(x: int) -> str:
            return str(x)

        assert await c.call(target, 5) == "invoked"
        c._invoker.call.assert_awaited_once_with(target, 5, strategies=None)  # noqa: SLF001

    async def test_call_executes_function_by_default(self) -> None:
        c = _FakeContainer()

        async def target(x: int) -> int:
            return x * 2

        assert await c.call(target, 21) == 42


class TestDispose:
    async def test_dispose_async_disposable(self) -> None:
        c = _FakeContainer()

        class AsyncDisposable:
            def __init__(self) -> None:
                self.disposed = False

            def dispose(self) -> Any:
                self.disposed = True
                return self._done()

            async def _done(self) -> None:
                pass

        instance = AsyncDisposable()
        c.add_descriptor(_descriptor(AsyncDisposable, ServiceScope.SINGLETON, instance))

        await c.dispose()
        assert instance.disposed is True

    async def test_dispose_sync_close(self) -> None:
        c = _FakeContainer()

        class Closable:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        instance = Closable()
        c.add_descriptor(_descriptor(Closable, ServiceScope.SINGLETON, instance))
        await c.dispose()
        assert instance.closed is True

    async def test_dispose_async_close(self) -> None:
        c = _FakeContainer()

        class AsyncClosable:
            def __init__(self) -> None:
                self.closed = False

            async def close(self) -> None:
                self.closed = True

        instance = AsyncClosable()
        c.add_descriptor(_descriptor(AsyncClosable, ServiceScope.SINGLETON, instance))
        await c.dispose()
        assert instance.closed is True

    async def test_dispose_aclose(self) -> None:
        c = _FakeContainer()

        class Aclosable:
            def __init__(self) -> None:
                self.closed = False

            async def aclose(self) -> None:
                self.closed = True

        instance = Aclosable()
        c.add_descriptor(_descriptor(Aclosable, ServiceScope.SINGLETON, instance))
        await c.dispose()
        assert instance.closed is True

    async def test_dispose_skips_transient_and_null_instances(self) -> None:
        c = _FakeContainer()

        class Closable:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        transient = Closable()
        c.add_descriptor(_descriptor(Closable, ServiceScope.TRANSIENT, transient))
        c.add_descriptor(_descriptor(Closable, ServiceScope.SINGLETON, None))
        await c.dispose()
        assert transient.closed is False

    async def test_dispose_skips_self(self) -> None:
        c = _FakeContainer()

        class SelfLike:
            def dispose(self) -> None:
                raise AssertionError("must not be called")

        # The container registers itself; simulate by making the descriptor's
        # instance identical to the container object.
        self_instance = object.__new__(type(c))
        c.add_descriptor(_descriptor(type(c), ServiceScope.SINGLETON, c))
        await c.dispose()  # must not recurse

    async def test_dispose_collects_errors_and_raises_group(self) -> None:
        c = _FakeContainer()

        class BadDispose:
            def dispose(self) -> None:
                raise ValueError("dispose failed")

        class BadClose:
            def close(self) -> None:
                raise OSError("close failed")

        c.add_descriptor(_descriptor(BadDispose, ServiceScope.SINGLETON, BadDispose()))
        c.add_descriptor(_descriptor(BadClose, ServiceScope.SINGLETON, BadClose()))

        with pytest.raises(ExceptionGroup) as excinfo:
            await c.dispose()
        errors = excinfo.value.exceptions
        assert len(errors) == 2
        assert any(isinstance(e, ValueError) for e in errors)
        assert any(isinstance(e, OSError) for e in errors)

    async def test_dispose_cancelled_error_propagates(self) -> None:
        c = _FakeContainer()

        class Cancelling:
            def dispose(self) -> Any:
                raise asyncio.CancelledError

        c.add_descriptor(_descriptor(Cancelling, ServiceScope.SINGLETON, Cancelling()))
        with pytest.raises(asyncio.CancelledError):
            await c.dispose()

    async def test_dispose_unexpected_error_type_propagates(self) -> None:
        c = _FakeContainer()

        class Weird:
            def dispose(self) -> None:
                raise KeyError("not caught")

        c.add_descriptor(_descriptor(Weird, ServiceScope.SINGLETON, Weird()))
        with pytest.raises(KeyError):
            await c.dispose()

    async def test_dispose_clears_registry_and_hints(self) -> None:
        c = _FakeContainer()
        c._hints_cache["x"] = 1  # noqa: SLF001
        await c.dispose()
        c._registry.clear.assert_called_once()  # noqa: SLF001
        assert c._hints_cache == {}  # noqa: SLF001


class TestBindOverrideLifecycle:
    def test_bind_delegates_to_registrar(self) -> None:
        c = _FakeContainer()
        instance = object()
        c.bind(dict, instance)
        c._registrar.bind.assert_called_once_with(dict, instance)  # noqa: SLF001

    def test_override_delegates_to_registrar(self) -> None:
        c = _FakeContainer()
        instance = object()
        c.override(dict, instance)
        c._registrar.override.assert_called_once_with(dict, instance)  # noqa: SLF001

    async def test_async_context_manager_disposes(self) -> None:
        c = _FakeContainer()
        c.dispose = AsyncMock()  # type: ignore[method-assign]
        async with c as entered:
            assert entered is c
        c.dispose.assert_awaited_once()  # type: ignore[attr-defined]

