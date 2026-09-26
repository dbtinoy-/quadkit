"""Unit-test fixtures for quadkit-tasks compute pool tests (no real spawns)."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from compute_fakes import (  # noqa: E402
    ExecutorHolder,
    FakeExecutor,
    FakeMultiprocessing,
    noop_start_monitoring,
)

import quadkit.tasks.concurrency.compute as compute_mod


@pytest.fixture
def fake_executor(monkeypatch: pytest.MonkeyPatch) -> ExecutorHolder:
    """Patch compute module: fake executor, cpu_count=4, no psutil, no monitor."""
    holder = ExecutorHolder()

    def factory(**kwargs: Any) -> FakeExecutor:
        holder.executor = FakeExecutor()
        return holder.executor

    monkeypatch.setattr(compute_mod, "ProcessPoolExecutor", factory)
    monkeypatch.setattr(compute_mod, "multiprocessing", FakeMultiprocessing())
    monkeypatch.setattr(compute_mod, "HAS_PSUTIL", False)
    monkeypatch.setattr(compute_mod, "psutil", None)
    monkeypatch.setattr(
        compute_mod.ComputePool, "_start_monitoring", noop_start_monitoring
    )
    return holder
