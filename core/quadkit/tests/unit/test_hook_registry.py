from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.hooks import HookRegistry


class TestHookRegistryActions:
    @pytest.mark.asyncio
    async def test_action_handler_is_called(self) -> None:
        registry = HookRegistry()
        handler = AsyncMock()
        registry.register_action("init", handler)
        await registry.call_action("init", context="test")
        handler.assert_awaited_once_with(context="test")

    @pytest.mark.asyncio
    async def test_action_handlers_called_in_priority_order(self) -> None:
        registry = HookRegistry()
        order: list[int] = []

        async def h1(**kwargs: object) -> None:
            order.append(1)

        async def h2(**kwargs: object) -> None:
            order.append(2)

        registry.register_action("init", h2, priority=200)
        registry.register_action("init", h1, priority=100)
        await registry.call_action("init")
        assert order == [1, 2]

    @pytest.mark.asyncio
    async def test_action_error_is_isolated(self) -> None:
        registry = HookRegistry()
        called: list[bool] = []

        async def bad(**kwargs: object) -> None:
            raise ValueError("boom")

        async def good(**kwargs: object) -> None:
            called.append(True)

        registry.register_action("init", bad, priority=100)
        registry.register_action("init", good, priority=200)
        await registry.call_action("init")  # must not raise
        assert called == [True]

    @pytest.mark.asyncio
    async def test_no_handlers_is_noop(self) -> None:
        registry = HookRegistry()
        await registry.call_action("nonexistent")  # must not raise

    def test_unregister_action_returns_true(self) -> None:
        registry = HookRegistry()
        handler = AsyncMock()
        registry.register_action("init", handler)
        assert registry.unregister_action("init", handler) is True

    def test_unregister_nonexistent_returns_false(self) -> None:
        registry = HookRegistry()
        assert registry.unregister_action("nonexistent", AsyncMock()) is False

    def test_has_action_false_when_empty(self) -> None:
        registry = HookRegistry()
        assert registry.has_action("init") is False

    def test_has_action_true_after_register(self) -> None:
        registry = HookRegistry()
        registry.register_action("init", AsyncMock())
        assert registry.has_action("init") is True

    def test_clear_specific_hook(self) -> None:
        registry = HookRegistry()
        registry.register_action("init", AsyncMock())
        registry.register_action("shutdown", AsyncMock())
        registry.clear("init")
        assert registry.has_action("init") is False
        assert registry.has_action("shutdown") is True

    def test_clear_all(self) -> None:
        registry = HookRegistry()
        registry.register_action("init", AsyncMock())
        registry.register_filter("transform", AsyncMock())
        registry.clear()
        assert registry.has_action("init") is False
        assert registry.has_filter("transform") is False


class TestHookRegistryFilters:
    @pytest.mark.asyncio
    async def test_filter_transforms_value(self) -> None:
        registry = HookRegistry()

        async def double(value: int, **kwargs: object) -> int:
            return value * 2

        registry.register_filter("transform", double)
        result = await registry.apply_filter("transform", 5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_filter_chains_in_priority_order(self) -> None:
        registry = HookRegistry()

        async def add1(value: int, **kwargs: object) -> int:
            return value + 1

        async def mul2(value: int, **kwargs: object) -> int:
            return value * 2

        registry.register_filter("transform", add1, priority=100)  # runs first
        registry.register_filter("transform", mul2, priority=200)  # runs second
        result = await registry.apply_filter("transform", 3)
        assert result == 8  # (3 + 1) * 2

    @pytest.mark.asyncio
    async def test_filter_error_propagates(self) -> None:
        registry = HookRegistry()

        async def bad(value: int, **kwargs: object) -> int:
            raise ValueError("filter error")

        registry.register_filter("transform", bad)
        with pytest.raises(ValueError, match="filter error"):
            await registry.apply_filter("transform", 5)

    @pytest.mark.asyncio
    async def test_no_filter_handlers_returns_value_unchanged(self) -> None:
        registry = HookRegistry()
        result = await registry.apply_filter("nonexistent", "hello")
        assert result == "hello"

    def test_has_filter_false_when_empty(self) -> None:
        registry = HookRegistry()
        assert registry.has_filter("transform") is False

    def test_has_filter_true_after_register(self) -> None:
        registry = HookRegistry()
        registry.register_filter("transform", AsyncMock())
        assert registry.has_filter("transform") is True


class TestHookEntry:
    def test_hook_entry_is_frozen(self) -> None:
        from quadkit.hooks.types import HookEntry

        entry = HookEntry(priority=100, handler=lambda: None)
        with pytest.raises((AttributeError, TypeError)):
            entry.priority = 200  # type: ignore[misc]

    def test_hook_entry_has_slots(self) -> None:
        from quadkit.hooks.types import HookEntry

        assert HookEntry.__slots__ == ("priority", "handler", "once")

    def test_hook_entry_once_defaults_false(self) -> None:
        from quadkit.hooks.types import HookEntry

        entry = HookEntry(priority=50, handler=lambda: None)
        assert entry.once is False


class TestOnceHandlers:
    @pytest.mark.asyncio
    async def test_once_action_fires_exactly_once(self) -> None:
        registry = HookRegistry()
        call_count = 0

        async def handler(**kwargs: object) -> None:
            nonlocal call_count
            call_count += 1

        registry.register_action("init", handler, once=True)
        await registry.call_action("init")
        await registry.call_action("init")
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_once_action_removed_after_fire(self) -> None:
        registry = HookRegistry()
        registry.register_action("init", AsyncMock(), once=True)
        await registry.call_action("init")
        assert registry.has_action("init") is False

    @pytest.mark.asyncio
    async def test_once_action_with_error_still_removed(self) -> None:
        registry = HookRegistry()

        async def bad(**kwargs: object) -> None:
            raise ValueError("boom")

        registry.register_action("init", bad, once=True)
        await registry.call_action("init")  # must not raise
        assert registry.has_action("init") is False

    @pytest.mark.asyncio
    async def test_once_action_mixed_with_regular(self) -> None:
        registry = HookRegistry()
        once_calls = 0
        regular_calls = 0

        async def once_handler(**kwargs: object) -> None:
            nonlocal once_calls
            once_calls += 1

        async def regular_handler(**kwargs: object) -> None:
            nonlocal regular_calls
            regular_calls += 1

        registry.register_action("init", once_handler, once=True)
        registry.register_action("init", regular_handler)

        await registry.call_action("init")
        await registry.call_action("init")

        assert once_calls == 1
        assert regular_calls == 2

    @pytest.mark.asyncio
    async def test_once_filter_fires_exactly_once(self) -> None:
        registry = HookRegistry()

        async def double(value: int, **kwargs: object) -> int:
            return value * 2

        registry.register_filter("transform", double, once=True)
        result1 = await registry.apply_filter("transform", 5)
        result2 = await registry.apply_filter("transform", 5)
        assert result1 == 10
        assert result2 == 5  # no-op second time

    @pytest.mark.asyncio
    async def test_once_filter_with_error_still_removed(self) -> None:
        registry = HookRegistry()

        async def bad(value: int, **kwargs: object) -> int:
            raise ValueError("filter error")

        registry.register_filter("transform", bad, once=True)
        with pytest.raises(ValueError, match="filter error"):
            await registry.apply_filter("transform", 5)
        # Second call should not invoke the handler — it was removed
        result = await registry.apply_filter("transform", 5)
        assert result == 5


class TestDecoratorAPI:
    @pytest.mark.asyncio
    async def test_action_decorator_registers_and_calls(self) -> None:
        registry = HookRegistry()
        called = False

        @registry.action("startup")
        async def handler(**kwargs: object) -> None:
            nonlocal called
            called = True

        await registry.call_action("startup")
        assert called is True

    @pytest.mark.asyncio
    async def test_filter_decorator_registers_and_transforms(self) -> None:
        registry = HookRegistry()

        @registry.filter("sanitize")
        async def strip_spaces(value: str, **kwargs: object) -> str:
            return value.strip()

        result = await registry.apply_filter("sanitize", "  hello  ")
        assert result == "hello"

    def test_decorator_returns_handler_unchanged(self) -> None:
        registry = HookRegistry()

        async def my_handler(**kwargs: object) -> None:
            pass

        returned = registry.action("init")(my_handler)
        assert returned is my_handler

    @pytest.mark.asyncio
    async def test_decorator_with_priority_and_once(self) -> None:
        from quadkit.contracts.core.hooks import HookPriority

        registry = HookRegistry()
        call_count = 0

        @registry.action("init", priority=HookPriority.EARLY, once=True)
        async def handler(**kwargs: object) -> None:
            nonlocal call_count
            call_count += 1

        await registry.call_action("init")
        await registry.call_action("init")
        assert call_count == 1


class TestHookPriorityIntegration:
    @pytest.mark.asyncio
    async def test_hook_priority_enum_as_register_arg(self) -> None:
        from quadkit.contracts.core.hooks import HookPriority

        registry = HookRegistry()
        order: list[str] = []

        async def late(**kwargs: object) -> None:
            order.append("late")

        async def early(**kwargs: object) -> None:
            order.append("early")

        registry.register_action("go", late, priority=HookPriority.LATE)
        registry.register_action("go", early, priority=HookPriority.EARLY)

        await registry.call_action("go")
        assert order == ["early", "late"]


class TestProtocolCompliance:
    def test_hook_registry_satisfies_protocol(self) -> None:
        from quadkit.contracts.core.hooks import HookRegistryProtocol

        registry = HookRegistry()
        assert isinstance(registry, HookRegistryProtocol)

    def test_hook_priority_importable_from_quadkit(self) -> None:
        import quadkit

        assert hasattr(quadkit, "HookPriority")
        from quadkit import HookPriority
        from quadkit.contracts.core.hooks import HookPriority as HookPriorityContract

        assert HookPriority is HookPriorityContract

    def test_hook_registry_protocol_importable_from_quadkit(self) -> None:
        from quadkit import HookRegistryProtocol
        from quadkit.contracts.core.hooks import (
            HookRegistryProtocol as HookRegistryProtocolContract,
        )

        assert HookRegistryProtocol is HookRegistryProtocolContract


class TestAmbientHooks:
    """Ambient hook registry mirrors the clock/identity ambient pattern."""

    def test_current_returns_default_registry(self) -> None:
        from quadkit.hooks.ambient import current

        assert isinstance(current(), HookRegistry)

    def test_use_overrides_registry_within_block(self) -> None:
        from quadkit.hooks.ambient import current, use

        replacement = HookRegistry("scoped")
        with use(replacement):
            assert current() is replacement
        assert current() is not replacement

    def test_install_sets_process_registry(self) -> None:
        from quadkit.hooks.ambient import current, install

        installed = HookRegistry("installed")
        install(installed)
        try:
            assert current() is installed
        finally:
            install(HookRegistry("default"))

    @pytest.mark.asyncio
    async def test_fire_invokes_registered_action(self) -> None:
        from quadkit.hooks.ambient import fire, use

        registry = HookRegistry("ambient-fire")
        handler = AsyncMock()
        registry.register_action("ambient.test", handler)

        with use(registry):
            await fire("ambient.test", value=7)

        handler.assert_awaited_once()
        assert handler.call_args.kwargs["value"] == 7

    @pytest.mark.asyncio
    async def test_fire_without_handlers_is_noop(self) -> None:
        from quadkit.hooks.ambient import fire, use

        with use(HookRegistry("ambient-noop")):
            await fire("ambient.none")

    @pytest.mark.asyncio
    async def test_fire_isolates_handler_errors(self) -> None:
        from quadkit.hooks.ambient import fire, use

        registry = HookRegistry("ambient-error")

        async def bad(**kwargs: object) -> None:
            raise RuntimeError("boom")

        calls: list[str] = []

        async def good(**kwargs: object) -> None:
            calls.append("good")

        registry.register_action("ambient.isolated", bad)
        registry.register_action("ambient.isolated", good)

        with use(registry):
            await fire("ambient.isolated")

        assert calls == ["good"]
