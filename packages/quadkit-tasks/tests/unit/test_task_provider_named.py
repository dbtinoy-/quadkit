"""Tests for multi-backend Named DI support in TaskProvider (TR2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.tasks.backends.memory import MemoryTaskQueue
from quadkit.tasks.config import NamedTaskConfig, TaskConfig
from quadkit.tasks.di.provider import TaskProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider() -> TaskProvider:
    """Return a TaskProvider wrapping an in-memory queue."""
    return TaskProvider(queue=MemoryTaskQueue(), worker_count=1, enable_scheduler=False)


def _make_mock_container() -> MagicMock:
    """Return a mock container whose singleton() records all calls."""
    container = MagicMock()
    container.singleton = MagicMock()
    return container


# ---------------------------------------------------------------------------
# 1. Single-backend path — _queue_services stays empty
# ---------------------------------------------------------------------------


class TestSingleBackendPath:
    """TaskProvider with backends=[] must use the single-backend path."""

    @pytest.mark.asyncio
    async def test_empty_backends_leaves_queue_services_empty(self) -> None:
        """When config.backends is empty, _queue_services remains []."""
        provider = _make_provider()
        config = TaskConfig(backends=[])
        provider._config = config

        container = _make_mock_container()
        await provider.register(container)

        assert provider._queue_services == []

    @pytest.mark.asyncio
    async def test_no_config_leaves_queue_services_empty(self) -> None:
        """When _config is None (direct __init__ construction), _queue_services stays []."""
        provider = _make_provider()
        assert provider._config is None

        container = _make_mock_container()
        await provider.register(container)

        assert provider._queue_services == []

    @pytest.mark.asyncio
    async def test_single_backend_registers_unnamed_queue_protocol(self) -> None:
        """Single-backend path registers TaskQueueProtocol without a name kwarg."""
        from quadkit.contracts.infra.tasks import TaskQueueProtocol

        provider = _make_provider()
        provider._config = TaskConfig(backends=[])
        container = _make_mock_container()

        await provider.register(container)

        # Collect all singleton() calls and look for a TaskQueueProtocol binding
        # that does NOT carry a name= kwarg.
        calls_with_tqp = [
            c
            for c in container.singleton.call_args_list
            if c.args and c.args[0] is TaskQueueProtocol
        ]
        # At least one call to bind TaskQueueProtocol, and none with name= set.
        assert calls_with_tqp, "Expected TaskQueueProtocol singleton registration"
        for c in calls_with_tqp:
            assert c.kwargs.get("name") is None, (
                "Single-backend path must not use named bindings"
            )


# ---------------------------------------------------------------------------
# 2. _register_multi_backend populates _queue_services and calls named singletons
# ---------------------------------------------------------------------------


class TestMultiBackendRegistration:
    """_register_multi_backend() must wire up every named backend correctly."""

    @pytest.mark.asyncio
    async def test_queue_services_populated_for_each_backend(self) -> None:
        """_queue_services contains one entry per NamedTaskConfig."""
        provider = _make_provider()
        provider._config = TaskConfig(
            backends=[
                NamedTaskConfig(name="primary", primary=True, type="memory"),
                NamedTaskConfig(name="notifications", type="memory"),
            ]
        )
        container = _make_mock_container()

        await provider.register(container)

        assert len(provider._queue_services) == 2
        names = [n for n, _ in provider._queue_services]
        assert names == ["primary", "notifications"]

    @pytest.mark.asyncio
    async def test_named_singleton_registered_for_each_backend(self) -> None:
        """container.singleton() is called with name= for every named backend."""

        provider = _make_provider()
        provider._config = TaskConfig(
            backends=[
                NamedTaskConfig(name="alpha", type="memory"),
                NamedTaskConfig(name="beta", type="memory"),
            ]
        )
        container = _make_mock_container()

        await provider.register(container)

        named_calls = {
            c.kwargs["name"]
            for c in container.singleton.call_args_list
            if c.kwargs.get("name") is not None
        }
        assert "alpha" in named_calls
        assert "beta" in named_calls


# ---------------------------------------------------------------------------
# 3. Primary backend gets both named AND unnamed binding
# ---------------------------------------------------------------------------


class TestPrimaryBackendBinding:
    """The primary backend must also receive the unnamed TaskQueueProtocol binding."""

    @pytest.mark.asyncio
    async def test_explicit_primary_flag_gets_unnamed_binding(self) -> None:
        """Backend with primary=True gets an unnamed TaskQueueProtocol binding."""
        from quadkit.contracts.infra.tasks import TaskQueueProtocol

        provider = _make_provider()
        provider._config = TaskConfig(
            backends=[
                NamedTaskConfig(name="secondary", type="memory"),
                NamedTaskConfig(name="main", primary=True, type="memory"),
            ]
        )
        container = _make_mock_container()

        await provider.register(container)

        # Count TaskQueueProtocol singletons without a name= kwarg.
        unnamed_tqp = [
            c
            for c in container.singleton.call_args_list
            if c.args
            and c.args[0] is TaskQueueProtocol
            and c.kwargs.get("name") is None
        ]
        assert len(unnamed_tqp) >= 1, (
            "Primary backend must produce an unnamed TaskQueueProtocol binding"
        )

    @pytest.mark.asyncio
    async def test_first_entry_by_identity_gets_unnamed_binding(self) -> None:
        """When no primary=True flag, the first entry (by identity) gets unnamed binding."""
        from quadkit.contracts.infra.tasks import TaskQueueProtocol

        provider = _make_provider()
        provider._config = TaskConfig(
            backends=[
                NamedTaskConfig(name="first", type="memory"),
                NamedTaskConfig(name="second", type="memory"),
            ]
        )
        container = _make_mock_container()

        await provider.register(container)

        unnamed_tqp = [
            c
            for c in container.singleton.call_args_list
            if c.args
            and c.args[0] is TaskQueueProtocol
            and c.kwargs.get("name") is None
        ]
        assert len(unnamed_tqp) >= 1, (
            "First backend entry must produce an unnamed TaskQueueProtocol binding"
        )
        # Second backend must NOT produce a second unnamed binding.
        assert len(unnamed_tqp) == 1, (
            "Only the primary/first backend should have an unnamed binding"
        )


# ---------------------------------------------------------------------------
# 4. health_check() aggregates worst status across all queues
# ---------------------------------------------------------------------------


class TestMultiBackendHealthCheck:
    """health_check() must return the worst individual status."""

    @pytest.mark.asyncio
    async def test_all_healthy_returns_healthy(self) -> None:
        """When every queue returns HEALTHY, overall status is HEALTHY."""
        provider = _make_provider()

        healthy_queue = AsyncMock()
        healthy_queue.get_task_count = AsyncMock(return_value=0)
        provider._queue_services = [("q1", healthy_queue), ("q2", healthy_queue)]

        result = await provider.health_check()

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_one_unhealthy_returns_unhealthy(self) -> None:
        """When any queue raises, overall status is UNHEALTHY."""
        provider = _make_provider()

        healthy_queue = AsyncMock()
        healthy_queue.get_task_count = AsyncMock(return_value=0)

        broken_queue = AsyncMock()
        broken_queue.get_task_count = AsyncMock(side_effect=ConnectionError("down"))

        provider._queue_services = [("ok", healthy_queue), ("broken", broken_queue)]

        result = await provider.health_check()

        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_empty_queue_services_uses_single_backend_path(self) -> None:
        """When _queue_services is empty, the single-backend path runs."""
        provider = _make_provider()
        assert provider._queue_services == []

        # MemoryTaskQueue.get_task_count() is real and returns 0.
        result = await provider.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert result.component == "tasks"


# ---------------------------------------------------------------------------
# 5. shutdown() iterates _queue_services in reversed (LIFO) order
# ---------------------------------------------------------------------------


class TestMultiBackendShutdown:
    """shutdown() must close named queues in LIFO order before the primary queue."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_queues_in_lifo_order(self) -> None:
        """Named queues are closed in reverse registration order."""
        primary_queue = AsyncMock(spec=["close"])
        primary_queue.close = AsyncMock()

        provider = TaskProvider(
            queue=primary_queue, worker_count=1, enable_scheduler=False
        )

        closed_order: list[str] = []

        async def make_close(name: str):  # noqa: ANN202
            async def _close():
                closed_order.append(name)

            return _close

        q_alpha = MagicMock()
        q_alpha.close = AsyncMock(side_effect=lambda: closed_order.append("alpha"))
        q_beta = MagicMock()
        q_beta.close = AsyncMock(side_effect=lambda: closed_order.append("beta"))
        q_gamma = MagicMock()
        q_gamma.close = AsyncMock(side_effect=lambda: closed_order.append("gamma"))

        provider._queue_services = [
            ("alpha", q_alpha),
            ("beta", q_beta),
            ("gamma", q_gamma),
        ]

        await provider.shutdown()

        # Named queues closed in LIFO order (gamma → beta → alpha).
        assert closed_order[:3] == ["gamma", "beta", "alpha"], (
            f"Expected LIFO order [gamma, beta, alpha], got {closed_order}"
        )
        # Primary queue also closed.
        primary_queue.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_tolerates_close_errors(self) -> None:
        """Errors during named queue close are suppressed; shutdown completes."""
        primary_queue = AsyncMock(spec=["close"])
        primary_queue.close = AsyncMock()

        provider = TaskProvider(
            queue=primary_queue, worker_count=1, enable_scheduler=False
        )

        failing_queue = MagicMock()
        failing_queue.close = AsyncMock(side_effect=RuntimeError("boom"))
        provider._queue_services = [("failing", failing_queue)]

        # Must not raise.
        await provider.shutdown()

        primary_queue.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_boot_wires_hook_registry_into_named_backends() -> None:
    """boot() should attach the optional hook registry to every named queue."""
    from quadkit.contracts.core import HookRegistryProtocol
    from quadkit.hooks.registry import HookRegistry

    hooks = HookRegistry("tasks-tests")

    primary_queue = MagicMock()
    primary_queue.set_hook_registry = MagicMock()
    primary_queue.close = AsyncMock()
    primary_queue.get_task_count = AsyncMock(return_value=0)

    named_queue = MagicMock()
    named_queue.set_hook_registry = MagicMock()
    named_queue.connect = AsyncMock()
    named_queue.close = AsyncMock()
    named_queue.get_task_count = AsyncMock(return_value=0)

    provider = TaskProvider(
        queue=primary_queue,
        worker_count=1,
        enable_scheduler=False,
    )
    provider._queue_services = [("notifications", named_queue)]

    class _ContainerStub:
        async def resolve_optional(self, contract: type[object]) -> object | None:
            if contract is HookRegistryProtocol:
                return hooks
            return None

        async def resolve(self, contract: type[object]) -> object | None:
            return None

    with patch("quadkit.tasks.di.provider.WorkerPool.start", new=AsyncMock()):
        await provider.boot(_ContainerStub())

    primary_queue.set_hook_registry.assert_called_once_with(hooks)
    named_queue.set_hook_registry.assert_called_once_with(hooks)
