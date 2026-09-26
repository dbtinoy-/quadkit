"""Shared fakes for ComputePool/Compute unit tests (no real process spawns)."""

from __future__ import annotations

import concurrent.futures
import threading
from typing import Any


class FakeExecutor:
    """Stand-in for ProcessPoolExecutor that runs callables inline."""

    def __init__(self) -> None:
        self.submitted: list[tuple] = []
        self.shutdown_called = False

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> concurrent.futures.Future:
        self.submitted.append((fn, args, kwargs))
        fut: concurrent.futures.Future = concurrent.futures.Future()
        try:
            fut.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001
            fut.set_exception(exc)
        return fut

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_called = True


class ExecutorHolder:
    """Holds the executor instance created by the pool under test."""

    def __init__(self) -> None:
        self.executor: FakeExecutor | None = None


class FakeMultiprocessing:
    """Fake multiprocessing module with a fixed cpu_count for determinism."""

    def cpu_count(self) -> int:
        return 4

    def get_context(self, method: str) -> object:
        return object()


def noop_start_monitoring(self: Any) -> None:
    """Replace the monitor thread so tests can introspect worker state safely."""
    self._monitor_thread = threading.Thread(daemon=True)