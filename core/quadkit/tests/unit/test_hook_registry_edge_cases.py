"""Filter chaining and edge-case handler tests."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.hooks import HookPriority
from quadkit.hooks import HookRegistry



class TestFilterChainingComplex:
    """Tests for complex filter chaining scenarios."""

    @pytest.mark.asyncio
    async def test_filter_chain_with_none_value(self) -> None:
        registry = HookRegistry()

        async def add_suffix(value: str | None, **_: object) -> str | None:
            return f"{value}_processed" if value is not None else None

        registry.register_filter("process", add_suffix)
        result = await registry.apply_filter("process", None)
        assert result is None

    @pytest.mark.asyncio
    async def test_filter_chain_with_complex_objects(self) -> None:
        registry = HookRegistry()

        def add_timestamp(value: dict[str, object], **_: object) -> dict[str, object]:
            value["timestamp"] = "2024-01-01"
            return value

        registry.register_filter("enrich", add_timestamp)
        result = await registry.apply_filter("enrich", {"id": 123})

        assert result["id"] == 123
        assert result["timestamp"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_filter_can_return_different_type(self) -> None:
        registry = HookRegistry()

        async def int_to_string(value: int, **_: object) -> str:
            return str(value * 2)

        registry.register_filter("convert", int_to_string)
        result = await registry.apply_filter("convert", 21)
        assert result == "42"
        assert isinstance(result, str)


class TestEdgeCaseHandlers:
    """Tests for edge case handlers."""

    @pytest.mark.asyncio
    async def test_handler_with_no_arguments(self) -> None:
        registry = HookRegistry()

        def no_args() -> None:
            pass

        registry.register_action("test", no_args)
        await registry.call_action("test")  # Should not raise

    @pytest.mark.asyncio
    async def test_handler_with_wildcard_kwargs(self) -> None:
        registry = HookRegistry()
        received: dict[str, object] = {}

        def capture_all(**kwargs: object) -> None:
            received.update(kwargs)

        registry.register_action("test", capture_all)
        await registry.call_action("test", a=1, b="two", c=[1, 2, 3])

        assert received == {"a": 1, "b": "two", "c": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_action_handler_returning_value_is_ignored(self) -> None:
        registry = HookRegistry()

        def returns_value() -> str:
            return "should be ignored"

        def records_call() -> None:
            pass

        registry.register_action("test", returns_value)
        registry.register_action("test", records_call)

        await registry.call_action("test")  # Should not raise, return value ignored


class TestHookEntryIdentity:
    """Tests for HookEntry identity handling."""

    def test_multiple_registrations_same_handler_different_entries(self) -> None:
        registry = HookRegistry()

        def handler() -> None:
            pass

        registry.register_action("test", handler)
        registry.register_action("test", handler)

        entries = registry._actions.get("test", [])
        assert len(entries) == 2
        assert entries[0].handler is entries[1].handler

    def test_unregister_only_removes_specific_entry(self) -> None:
        registry = HookRegistry()

        def handler1() -> None:
            pass

        def handler2() -> None:
            pass

        registry.register_action("test", handler1)
        registry.register_action("test", handler2)

        registry.unregister_action("test", handler1)

        entries = registry._actions.get("test", [])
        assert len(entries) == 1
        assert entries[0].handler is handler2
