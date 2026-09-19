"""Tests for application lifecycle helpers and ASGI lifespan handling."""

from __future__ import annotations

import asyncio
import signal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.app.asgi_lifespan import handle_lifespan
from quadkit.app.base import Application, AppState
from quadkit.app.runner import (
    run_application,
    start_application,
    stop_application,
)


class TestStartStopHelpers:
    async def test_start_application_delegates(self) -> None:
        app = Application(name="runner-app")
        app.start = AsyncMock()  # type: ignore[method-assign]
        await start_application(app)
        app.start.assert_awaited_once()  # type: ignore[attr-defined]

    async def test_stop_application_delegates(self) -> None:
        app = Application(name="runner-app")
        app.stop = AsyncMock()  # type: ignore[method-assign]
        await stop_application(app)
        app.stop.assert_awaited_once()  # type: ignore[attr-defined]


class TestRunApplication:
    async def test_starts_waits_and_stops_on_signal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app = Application(name="run-app")

        async def fake_start() -> None:
            app._state = AppState.RUNNING  # noqa: SLF001

        async def fake_stop() -> None:
            app._state = AppState.STOPPED  # noqa: SLF001

        app.start = fake_start  # type: ignore[method-assign]
        app.stop = fake_stop  # type: ignore[method-assign]

        # Capture the registered signal callbacks instead of sending real
        # signals, so the test is deterministic across platforms.
        callbacks: dict[int, Any] = {}

        class _FakeLoop:
            def add_signal_handler(self, sig: int, callback: Any) -> None:
                callbacks[sig] = callback

        import asyncio as asyncio_module

        fake_loop = _FakeLoop()

        def fake_get_running_loop() -> _FakeLoop:
            return fake_loop

        monkeypatch.setattr(asyncio_module, "get_running_loop", fake_get_running_loop)

        task = asyncio.create_task(run_application(app))
        await asyncio.sleep(0.05)
        assert app.state is AppState.RUNNING  # started, now waiting for signal
        assert signal.SIGINT in callbacks
        assert signal.SIGTERM in callbacks

        callbacks[signal.SIGINT]()  # fire the SIGINT handler
        await asyncio.wait_for(task, timeout=5.0)  # clean exit
        assert app.state is AppState.STOPPED

    async def test_keyboard_interrupt_is_swallowed(self) -> None:
        app = Application(name="ki-app")
        app.stop = AsyncMock()  # type: ignore[method-assign]

        async def raising_start() -> None:
            app._state = AppState.RUNNING  # noqa: SLF001
            raise KeyboardInterrupt

        app.start = raising_start  # type: ignore[method-assign]
        await run_application(app)  # must not raise
        app.stop.assert_awaited_once()  # type: ignore[attr-defined]

    async def test_system_exit_is_swallowed(self) -> None:
        app = Application(name="se-app")
        app.stop = AsyncMock()  # type: ignore[method-assign]

        async def raising_start() -> None:
            raise SystemExit(13)

        app.start = raising_start  # type: ignore[method-assign]
        await run_application(app)  # must not raise
        app.stop.assert_awaited_once()  # type: ignore[attr-defined]


class TestLifespan:
    async def _drive(
        self,
        app: Application,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        sent: list[dict[str, str]] = []

        async def receive() -> dict[str, Any]:
            return messages.pop(0)

        async def send(message: dict[str, str]) -> None:
            sent.append(message)

        await handle_lifespan(app, receive, send)
        return sent

    async def test_startup_then_shutdown(self) -> None:
        app = Application(name="ls-app")
        sent = await self._drive(
            app,
            [
                {"type": "lifespan.startup"},
                {"type": "lifespan.shutdown"},
            ],
        )
        assert sent == [
            {"type": "lifespan.startup.complete"},
            {"type": "lifespan.shutdown.complete"},
        ]
        assert app.state is AppState.STOPPED

    async def test_startup_already_started_skips_start(self) -> None:
        app = Application(name="ls-app")
        app.start = AsyncMock()  # type: ignore[method-assign]
        app._state = AppState.RUNNING  # noqa: SLF001
        sent = await self._drive(
            app,
            [
                {"type": "lifespan.startup"},
                {"type": "lifespan.shutdown"},
            ],
        )
        app.start.assert_not_awaited()  # type: ignore[attr-defined]
        assert sent == [
            {"type": "lifespan.startup.complete"},
            {"type": "lifespan.shutdown.complete"},
        ]

    async def test_startup_failure_reports_and_raises(self) -> None:
        app = Application(name="ls-app")

        async def bad_start() -> None:
            raise RuntimeError("startup boom")

        app.start = bad_start  # type: ignore[method-assign]
        sent: list[dict[str, str]] = []

        async def receive() -> dict[str, Any]:
            return {"type": "lifespan.startup"}

        async def send(message: dict[str, str]) -> None:
            sent.append(message)

        with pytest.raises(RuntimeError, match="startup boom"):
            await handle_lifespan(app, receive, send)
        assert sent == [{"type": "lifespan.startup.failed"}]

    async def test_shutdown_failure_reports_and_raises(self) -> None:
        app = Application(name="ls-app")
        await app.start()

        async def bad_stop() -> None:
            raise OSError("stop boom")

        app.stop = bad_stop  # type: ignore[method-assign]
        sent: list[dict[str, str]] = []

        async def receive() -> dict[str, Any]:
            return {"type": "lifespan.shutdown"}

        async def send(message: dict[str, str]) -> None:
            sent.append(message)

        with pytest.raises(OSError, match="stop boom"):
            await handle_lifespan(app, receive, send)
        assert sent == [{"type": "lifespan.shutdown.failed"}]
