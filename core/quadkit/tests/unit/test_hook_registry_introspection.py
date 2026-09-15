"""Registry introspection, unregistration, sync handlers, priorities."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.hooks import HookPriority
from quadkit.hooks import HookRegistry



class TestHookRegistryIntrospection:
    """Tests for introspection methods."""

    def test_action_names_returns_registered_hook_names(self) -> None:
        registry = HookRegistry()
        registry.register_action("init", lambda **_: None)
        registry.register_action("init", lambda **_: None)  # same hook
        registry.register_action("shutdown", lambda **_: None)

        names = registry.action_names()
        assert "init" in names
        assert "shutdown" in names
        assert len(names) == 2

    def test_filter_names_returns_registered_hook_names(self) -> None:
        registry = HookRegistry()
        registry.register_filter("sanitize", lambda x, **_: x)
        registry.register_filter("transform", lambda x, **_: x)

        names = registry.filter_names()
        assert "sanitize" in names
        assert "transform" in names

    def test_action_names_excludes_empty_hooks(self) -> None:
        registry = HookRegistry()
        registry.register_action("empty", lambda **_: None)
        entry = next(iter(registry._actions["empty"]))
        registry.unregister_action("empty", entry.handler)

        names = registry.action_names()
        assert "empty" not in names

    def test_filter_names_excludes_empty_hooks(self) -> None:
        registry = HookRegistry()
        registry.register_filter("empty", lambda x, **_: x)
        entry = next(iter(registry._filters["empty"]))
        registry.unregister_filter("empty", entry.handler)

        names = registry.filter_names()
        assert "empty" not in names


class TestHookRegistryUnregistration:
    """Tests for unregistration methods."""

    def test_unregister_filter_returns_true_when_found(self) -> None:
        registry = HookRegistry()

        def handler(value: int, **_: object) -> int:
            return value

        registry.register_filter("transform", handler)
        result = registry.unregister_filter("transform", handler)
        assert result is True

    def test_unregister_filter_returns_false_when_not_found(self) -> None:
        registry = HookRegistry()

        def handler(value: int, **_: object) -> int:
            return value

        registry.register_filter("transform", handler)
        result = registry.unregister_filter("transform", lambda x, **_: x)
        assert result is False

    def test_unregister_filter_removes_from_list(self) -> None:
        registry = HookRegistry()

        def h1(value: int, **_: object) -> int:
            return value

        def h2(value: int, **_: object) -> int:
            return value

        registry.register_filter("transform", h1)
        registry.register_filter("transform", h2)

        registry.unregister_filter("transform", h1)
        entries = registry._filters.get("transform", [])
        assert len(entries) == 1
        assert entries[0].handler is h2

    def test_unregister_filter_nonexistent_hook_returns_false(self) -> None:
        registry = HookRegistry()
        result = registry.unregister_filter("nonexistent", lambda x, **_: x)
        assert result is False


class TestSyncHandlers:
    """Tests for synchronous (non-async) handlers."""

    @pytest.mark.asyncio
    async def test_sync_action_handler_is_called(self) -> None:
        registry = HookRegistry()
        called = False

        def handler(**_: object) -> None:
            nonlocal called
            called = True

        registry.register_action("init", handler)
        await registry.call_action("init")
        assert called is True

    @pytest.mark.asyncio
    async def test_sync_filter_handler_transforms_value(self) -> None:
        registry = HookRegistry()

        def double(value: int, **_: object) -> int:
            return value * 2

        registry.register_filter("transform", double)
        result = await registry.apply_filter("transform", 5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_mixed_sync_and_async_handlers(self) -> None:
        registry = HookRegistry()
        results: list[int] = []

        def sync_add10(value: int, **_: object) -> int:
            return value + 10

        async def async_mul2(value: int, **_: object) -> int:
            return value * 2

        registry.register_filter("transform", sync_add10, priority=100)
        registry.register_filter("transform", async_mul2, priority=200)

        result = await registry.apply_filter("transform", 3)
        assert result == 26  # (3 + 10) * 2


class TestComplexPriorityScenarios:
    """Tests for complex priority ordering scenarios."""

    @pytest.mark.asyncio
    async def test_many_handlers_priority_ordering(self) -> None:
        registry = HookRegistry()
        order: list[int] = []

        handlers = [
            (lambda **_: order.append(10), 10),
            (lambda **_: order.append(300), 300),
            (lambda **_: order.append(50), 50),
            (lambda **_: order.append(200), 200),
            (lambda **_: order.append(0), 0),
            (lambda **_: order.append(150), 150),
            (lambda **_: order.append(100), 100),
            (lambda **_: order.append(250), 250),
        ]

        for handler, priority in handlers:
            registry.register_action("test", handler, priority=priority)

        await registry.call_action("test")

        expected = [0, 10, 50, 100, 150, 200, 250, 300]
        assert order == expected

    @pytest.mark.asyncio
    async def test_same_priority_maintains_insertion_order(self) -> None:
        registry = HookRegistry()
        order: list[str] = []

        def make_handler(name: str):
            def handler(**_: object) -> None:
                order.append(name)
            return handler

        registry.register_action("test", make_handler("a"), priority=100)
        registry.register_action("test", make_handler("b"), priority=100)
        registry.register_action("test", make_handler("c"), priority=100)

        await registry.call_action("test")
        assert order == ["a", "b", "c"]


class TestConcurrentAccess:
    """Tests for thread-safety under concurrent access."""

    def test_concurrent_registration_is_thread_safe(self) -> None:
        import threading

        registry = HookRegistry()
        errors: list[Exception] = []

        def register_handlers() -> None:
            try:
                for i in range(50):
                    registry.register_action("concurrent", lambda **_: None, priority=i)
                    registry.register_filter("concurrent", lambda x, **_: x, priority=i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_handlers) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert registry.has_action("concurrent")

    @pytest.mark.asyncio
    async def test_read_during_write(self) -> None:
        import asyncio

        registry = HookRegistry()
        errors: list[Exception] = []

        async def reader() -> None:
            for _ in range(100):
                try:
                    _ = registry.has_action("test")
                    _ = registry.has_filter("test")
                    _ = registry.action_names()
                except Exception as e:
                    errors.append(e)
                await asyncio.sleep(0)

        async def writer() -> None:
            for i in range(100):
                try:
                    registry.register_action("test", lambda **_: None, priority=i)
                    registry.register_filter("test", lambda x, **_: x, priority=i)
                except Exception as e:
                    errors.append(e)
                await asyncio.sleep(0)

        await asyncio.gather(reader(), writer())

        assert len(errors) == 0  # No exceptions should be raised


