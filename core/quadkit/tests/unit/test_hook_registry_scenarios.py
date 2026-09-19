"""Repr, decorator-priority, empty/noop, isolation scenarios."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.hooks import HookPriority
from quadkit.hooks import HookRegistry



class TestReprAndDebugging:
    """Tests for __repr__ output."""

    def test_repr_shows_name(self) -> None:
        registry = HookRegistry("my-app")
        assert "my-app" in repr(registry)

    def test_repr_shows_actions(self) -> None:
        registry = HookRegistry()
        registry.register_action("init", lambda **_: None)
        registry.register_action("init", lambda **_: None)  # 2 handlers

        r = repr(registry)
        assert "init" in r
        assert "2 handlers" in r

    def test_repr_shows_filters(self) -> None:
        registry = HookRegistry()
        registry.register_filter("sanitize", lambda x, **_: x)

        r = repr(registry)
        assert "sanitize" in r

    def test_repr_shows_both_actions_and_filters(self) -> None:
        registry = HookRegistry()
        registry.register_action("action_hook", lambda **_: None)
        registry.register_filter("filter_hook", lambda x, **_: x)

        r = repr(registry)
        assert "actions=" in r
        assert "filters=" in r


class TestDecoratorWithNonDefaultPriority:
    """Tests for decorator with custom priority values."""

    @pytest.mark.asyncio
    async def test_decorator_with_explicit_priority(self) -> None:
        registry = HookRegistry()
        order: list[str] = []

        @registry.action("test", priority=HookPriority.LATE)
        async def late(**_: object) -> None:
            order.append("late")

        @registry.action("test", priority=HookPriority.EARLY)
        async def early(**_: object) -> None:
            order.append("early")

        @registry.action("test", priority=HookPriority.NORMAL)
        async def normal(**_: object) -> None:
            order.append("normal")

        await registry.call_action("test")
        assert order == ["early", "normal", "late"]

    def test_decorator_with_once_flag(self) -> None:
        registry = HookRegistry()
        call_count = 0

        @registry.action("test", once=True)
        async def once_handler(**_: object) -> None:
            nonlocal call_count
            call_count += 1

        assert registry.has_action("test")

        import asyncio
        asyncio.run(registry.call_action("test"))
        asyncio.run(registry.call_action("test"))

        assert call_count == 1


class TestEmptyAndNoopScenarios:
    """Tests for edge cases with empty hooks."""

    @pytest.mark.asyncio
    async def test_call_action_with_no_kwargs(self) -> None:
        registry = HookRegistry()
        called = False

        def handler(**kwargs: object) -> None:
            nonlocal called
            called = True
            assert kwargs == {}

        registry.register_action("test", handler)
        await registry.call_action("test")
        assert called is True

    @pytest.mark.asyncio
    async def test_apply_filter_passes_kwargs(self) -> None:
        registry = HookRegistry()
        received_kwargs: dict[str, object] = {}

        def capture_kwargs(value: int, **kwargs: object) -> int:
            received_kwargs.update(kwargs)
            return value

        registry.register_filter("test", capture_kwargs)
        result = await registry.apply_filter("test", 0, user_id="user123", tenant="acme")

        assert result == 0
        assert received_kwargs == {"user_id": "user123", "tenant": "acme"}

    @pytest.mark.asyncio
    async def test_call_action_passes_all_kwargs(self) -> None:
        registry = HookRegistry()
        received_kwargs: dict[str, object] = {}

        def capture_kwargs(**kwargs: object) -> None:
            received_kwargs.update(kwargs)

        registry.register_action("test", capture_kwargs)
        await registry.call_action("test", user_id="user123", request_id="req-456")

        assert received_kwargs == {"user_id": "user123", "request_id": "req-456"}


class TestMultipleHooksIsolation:
    """Tests for multiple independent hook collections."""

    @pytest.mark.asyncio
    async def test_multiple_registries_are_independent(self) -> None:
        registry_a = HookRegistry("a")
        registry_b = HookRegistry("b")

        results_a: list[str] = []
        results_b: list[str] = []

        registry_a.register_action("test", lambda **_: results_a.append("a"))
        registry_b.register_action("test", lambda **_: results_b.append("b"))

        await registry_a.call_action("test")
        await registry_b.call_action("test")

        assert results_a == ["a"]
        assert results_b == ["b"]

    @pytest.mark.asyncio
    async def test_clear_one_registry_does_not_affect_other(self) -> None:
        registry_a = HookRegistry("a")
        registry_b = HookRegistry("b")

        registry_a.register_action("test", lambda **_: None)
        registry_b.register_action("test", lambda **_: None)

        registry_a.clear("test")

        assert registry_a.has_action("test") is False
        assert registry_b.has_action("test") is True


