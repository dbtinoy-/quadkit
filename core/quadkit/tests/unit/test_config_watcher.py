"""Tests for the poll-based ConfigWatcher."""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.config.lib.watcher import ConfigWatcher


async def _stable_loader() -> dict[str, Any]:
    return {"a": 1}


class TestLifecycle:
    async def test_start_establishes_baseline(self) -> None:
        watcher = ConfigWatcher(loader=_stable_loader, interval=0.02)
        assert watcher.last_config is None
        await watcher.start()
        try:
            assert watcher.is_running is True
            assert watcher.last_config == {"a": 1}
        finally:
            await watcher.stop()

    async def test_start_is_reentrant(self) -> None:
        watcher = ConfigWatcher(loader=_stable_loader, interval=0.02)
        await watcher.start()
        try:
            first_task = watcher._task  # noqa: SLF001
            await watcher.start()
            assert watcher._task is first_task  # noqa: SLF001
        finally:
            await watcher.stop()

    async def test_stop_cancels_task(self) -> None:
        watcher = ConfigWatcher(loader=_stable_loader, interval=0.02)
        await watcher.start()
        await watcher.stop()
        assert watcher.is_running is False
        assert watcher._task is None  # noqa: SLF001

    async def test_stop_when_not_running_is_safe(self) -> None:
        watcher = ConfigWatcher(loader=_stable_loader, interval=0.02)
        await watcher.stop()  # must not raise


class TestChangeDetection:
    async def test_listener_invoked_on_change(self) -> None:
        state = {"version": 1}

        async def loader() -> dict[str, Any]:
            return {"v": state["version"]}

        seen: list[tuple[dict, dict]] = []

        async def on_change(old: dict[str, Any], new: dict[str, Any]) -> None:
            seen.append((old, new))

        watcher = ConfigWatcher(loader=loader, interval=0.01)
        watcher.add_listener(on_change)
        await watcher.start()
        try:
            assert watcher.last_config == {"v": 1}
            assert seen == []  # baseline does not fire listeners
            state["version"] = 2
            await asyncio.sleep(0.08)
            assert seen == [({"v": 1}, {"v": 2})]
            assert watcher.last_config == {"v": 2}
        finally:
            await watcher.stop()

    async def test_no_callback_when_unchanged(self) -> None:
        calls: list[int] = []

        async def on_change(old: dict[str, Any], new: dict[str, Any]) -> None:
            calls.append(1)

        watcher = ConfigWatcher(loader=_stable_loader, interval=0.01)
        watcher.add_listener(on_change)
        await watcher.start()
        try:
            await asyncio.sleep(0.06)
            assert calls == []
        finally:
            await watcher.stop()

    async def test_key_order_does_not_trigger_change(self) -> None:
        configs = [
            {"a": 1, "b": 2},
            {"b": 2, "a": 1},
        ]
        index = 0

        async def loader() -> dict[str, Any]:
            nonlocal index
            cfg = configs[min(index, 1)]
            index += 1
            return cfg

        calls: list[int] = []

        async def on_change(old: dict[str, Any], new: dict[str, Any]) -> None:
            calls.append(1)

        watcher = ConfigWatcher(loader=loader, interval=0.01)
        watcher.add_listener(on_change)
        await watcher.start()
        try:
            await asyncio.sleep(0.08)
            assert calls == []  # same content, different key order
        finally:
            await watcher.stop()

    async def test_listener_error_keeps_old_config(self) -> None:
        state = {"version": 1}

        async def loader() -> dict[str, Any]:
            return {"v": state["version"]}

        async def failing_listener(old: dict[str, Any], new: dict[str, Any]) -> None:
            raise RuntimeError("reject new config")

        watcher = ConfigWatcher(loader=loader, interval=0.01)
        watcher.add_listener(failing_listener)
        await watcher.start()
        try:
            state["version"] = 2
            await asyncio.sleep(0.08)
            # Listener rejected the swap — old config is retained.
            assert watcher.last_config == {"v": 1}
        finally:
            await watcher.stop()

    async def test_multiple_listeners_all_invoked(self) -> None:
        state = {"version": 1}

        async def loader() -> dict[str, Any]:
            return {"v": state["version"]}

        first: list[int] = []
        second: list[int] = []

        async def listener_a(old: dict[str, Any], new: dict[str, Any]) -> None:
            first.append(1)

        async def listener_b(old: dict[str, Any], new: dict[str, Any]) -> None:
            second.append(1)

        watcher = ConfigWatcher(loader=loader, interval=0.01)
        watcher.add_listener(listener_a)
        watcher.add_listener(listener_b)
        await watcher.start()
        try:
            state["version"] = 2
            await asyncio.sleep(0.08)
            assert first == [1]
            assert second == [1]
        finally:
            await watcher.stop()

    async def test_removed_listener_not_invoked(self) -> None:
        state = {"version": 1}

        async def loader() -> dict[str, Any]:
            return {"v": state["version"]}

        calls: list[int] = []

        async def on_change(old: dict[str, Any], new: dict[str, Any]) -> None:
            calls.append(1)

        watcher = ConfigWatcher(loader=loader, interval=0.01)
        watcher.add_listener(on_change)
        watcher.remove_listener(on_change)
        await watcher.start()
        try:
            state["version"] = 2
            await asyncio.sleep(0.08)
            assert calls == []
        finally:
            await watcher.stop()


class TestLoaderErrors:
    async def test_loader_error_backs_off_interval(self) -> None:
        attempts = 0

        async def failing_loader() -> dict[str, Any]:
            nonlocal attempts
            attempts += 1
            raise ConnectionError("source unavailable")

        watcher = ConfigWatcher(loader=failing_loader, interval=0.01)
        await watcher.start()
        try:
            # Baseline poll fails during start -> interval already doubled.
            assert attempts >= 1
            await asyncio.sleep(0.08)
            assert attempts >= 2
            # Interval doubled again (or capped) after the loop poll failed.
            assert watcher._current_interval >= 0.02  # noqa: SLF001
        finally:
            await watcher.stop()

    async def test_interval_resets_after_success(self) -> None:
        attempts = 0

        async def flaky_loader() -> dict[str, Any]:
            nonlocal attempts
            attempts += 1
            if attempts % 3 == 0:
                raise ConnectionError("blip")
            return {"n": attempts}

        watcher = ConfigWatcher(loader=flaky_loader, interval=0.01)
        await watcher.start()
        try:
            await asyncio.sleep(0.1)
            # After a successful poll following a failure the interval resets.
            assert watcher._current_interval == 0.01  # noqa: SLF001
        finally:
            await watcher.stop()

    async def test_baseline_failure_no_state(self) -> None:
        async def failing_loader() -> dict[str, Any]:
            raise RuntimeError("no config")

        watcher = ConfigWatcher(loader=failing_loader, interval=0.01)
        await watcher.start()
        try:
            assert watcher.last_config is None
        finally:
            await watcher.stop()


class TestHash:
    def test_hash_is_stable_and_order_insensitive(self) -> None:
        h1 = ConfigWatcher._hash({"a": 1, "b": 2})  # noqa: SLF001
        h2 = ConfigWatcher._hash({"b": 2, "a": 1})  # noqa: SLF001
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex

    def test_hash_differs_on_content_change(self) -> None:
        assert ConfigWatcher._hash({"a": 1}) != ConfigWatcher._hash({"a": 2})  # noqa: SLF001

    def test_hash_handles_non_serializable_values(self) -> None:
        # default=str — exotic objects still hash deterministically.
        class Weird:
            def __str__(self) -> str:
                return "weird"

        h = ConfigWatcher._hash({"w": Weird()})  # noqa: SLF001
        assert ConfigWatcher._hash({"w": Weird()}) == h  # noqa: SLF001

    def test_max_interval_cap(self) -> None:
        watcher = ConfigWatcher(loader=_stable_loader, interval=1.0)
        watcher._current_interval = 9.0  # noqa: SLF001
        # Simulate a failed poll: doubling caps at max_interval.
        watcher._current_interval = min(
            watcher._current_interval * 2, watcher._max_interval  # noqa: SLF001
        )
        assert watcher._current_interval == 10.0  # noqa: SLF001
