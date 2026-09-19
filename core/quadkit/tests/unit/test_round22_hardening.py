"""Round-22 hardening pins for core/quadkit.

Covers:
- AbstractSaga: a step action that RAISES (instead of returning Err)
  still triggers compensation and returns Err(SagaError) — the old
  code let the exception escape with completed steps uncompensated
- AbstractSaga: a compensation raising a foreign error type no longer
  aborts the remaining compensations
- Scope.dispose: a disposable raising a foreign error type no longer
  skips disposing the remaining resources
- ConfigWatcher._poll: a loader raising a foreign error type no longer
  kills the watch loop
- ContainerBuilder validation: a pathological registration is
  collected into ContainerBuildError, not raised raw
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core import Err as ResultErr
from quadkit.contracts.core import Ok as ResultOk
from quadkit.contracts.workflow.steps import SagaStep
from quadkit.saga.base import AbstractSaga, SagaError, SagaState


class _TestSaga(AbstractSaga[dict[str, Any]]):
    """Minimal concrete saga for boundary testing."""

    def __init__(self) -> None:
        super().__init__()
        self._id = "saga-round22"

    def get_id(self) -> str:
        return self._id

    def is_completed(self) -> bool:
        return self.state in (SagaState.COMPLETED, SagaState.FAILED)


class TestSagaRaisingStep:
    @pytest.mark.asyncio
    async def test_raising_step_compensates_and_returns_err(self) -> None:
        """A step action that raises must be treated as a failed step:
        compensation runs for completed steps and Err(SagaError) is
        returned (the old code let the exception escape raw, leaving
        completed steps uncompensated and the saga stuck in RUNNING)."""
        saga = _TestSaga()
        compensated: list[str] = []

        async def ok_action() -> Any:
            return ResultOk("done")

        async def comp1() -> None:
            compensated.append("step1")

        async def raising_action() -> Any:
            raise KeyError("boom")

        saga.add_step(SagaStep(name="step1", action=ok_action, compensation=comp1, max_retries=1))
        saga.add_step(SagaStep(name="step2", action=raising_action, max_retries=1))

        result = await saga.execute()

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, SagaError)
        assert error.step_name == "step2"
        assert compensated == ["step1"]
        assert saga.state is SagaState.FAILED
        assert saga.was_compensated("step1")

    @pytest.mark.asyncio
    async def test_raising_step_retries_then_compensates(self) -> None:
        """Retry semantics apply to raised failures as well."""
        saga = _TestSaga()
        attempts = 0

        async def flaky() -> Any:
            nonlocal attempts
            attempts += 1
            raise ValueError("transient")

        async def action_ok() -> Any:
            return ResultOk("x")

        saga.add_step(SagaStep(name="a", action=action_ok, max_retries=1))
        saga.add_step(SagaStep(name="b", action=flaky, max_retries=2, retry_delay=0))

        result = await saga.execute()

        assert result.is_err()
        assert attempts == 2  # retried once before failing


class TestSagaCompensationBoundary:
    @pytest.mark.asyncio
    async def test_foreign_compensation_error_does_not_skip_rest(self) -> None:
        """A compensation raising outside the old narrow tuple must not
        abort the remaining compensations (old code escaped raw and
        skipped the rest of the unwind)."""
        saga = _TestSaga()
        order: list[str] = []

        def comp(tag: str, fail: bool) -> Any:
            async def _comp() -> None:
                order.append(tag)
                if fail:
                    raise MemoryError("disk full")

            return _comp

        async def ok_action() -> Any:
            return ResultOk("done")

        async def failing_action() -> Any:
            return ResultErr(SagaError("step3", ValueError("stop")))

        saga.add_step(SagaStep(name="s1", action=ok_action, compensation=comp("s1", False), max_retries=1))
        saga.add_step(SagaStep(name="s2", action=ok_action, compensation=comp("s2", True), max_retries=1))
        saga.add_step(SagaStep(name="s3", action=failing_action, max_retries=1))

        result = await saga.execute()

        assert result.is_err()
        # s2's compensation raised MemoryError — s1 must still run.
        assert order == ["s2", "s1"]
        assert saga.state is SagaState.FAILED
        assert saga.was_compensated("s1")
        assert not saga.was_compensated("s2")


class TestScopeDisposeBoundary:
    @pytest.mark.asyncio
    async def test_foreign_dispose_error_disposes_rest(self) -> None:
        """A disposable whose close() raises a foreign error type must
        not skip disposing the remaining resources (old narrow tuple
        escaped raw and aborted the loop)."""
        from quadkit.di.container.scope import Scope

        scope = Scope(MagicMock())
        disposed: list[str] = []

        class _Good:
            def close(self) -> None:
                disposed.append("good")

        class _Bad:
            def close(self) -> None:
                disposed.append("bad")
                raise KeyError("broken disposable state")

        scope._disposables = [_Good(), _Bad(), _Good()]  # noqa: SLF001

        with pytest.raises(ExceptionGroup) as exc_info:
            await scope.dispose()

        assert disposed == ["good", "bad", "good"]  # all attempted
        assert len(exc_info.value.exceptions) == 1
        assert scope._disposables == []  # noqa: SLF001


class TestConfigWatcherPollBoundary:
    @pytest.mark.asyncio
    async def test_foreign_loader_error_keeps_loop_alive(self) -> None:
        """A loader raising outside the old tuple must be logged and
        back off, not kill the watch loop."""
        from quadkit.config.lib.watcher import ConfigWatcher

        calls = 0

        async def bad_loader() -> dict[str, Any]:
            nonlocal calls
            calls += 1
            raise MemoryError("loader exploded")

        watcher = ConfigWatcher(loader=bad_loader, interval=0.01)
        # Drive _poll directly: before the fix a MemoryError escaped.
        await watcher._poll()  # noqa: SLF001
        assert calls == 1
        # The watcher must still be able to poll again after the failure.
        await watcher._poll()  # noqa: SLF001
        assert calls == 2


class TestBuilderValidationBoundary:
    @pytest.mark.asyncio
    async def test_pathological_registration_collected_not_raised(self) -> None:
        """A registration whose implementation access raises a foreign
        error type during validation must be collected into
        ContainerBuildError, not raised raw (old tuple escaped
        KeyError)."""
        from quadkit.contracts import ServiceScope
        from quadkit.di.builder import ContainerBuilder

        builder = ContainerBuilder.__new__(ContainerBuilder)

        class _PoisonRegistration:
            scope = ServiceScope.TRANSIENT
            interface = object

            def __init__(self) -> None:
                self._accesses = 0

            @property
            def implementation(self) -> Any:
                # First access (registration) succeeds; the second
                # (validation) raises a type outside the old tuple.
                self._accesses += 1
                if self._accesses >= 2:
                    raise KeyError("poisoned registration")
                return lambda: None  # noqa: E731

        builder._registrations = [_PoisonRegistration()]  # type: ignore[list-item]
        builder._modules = []
        builder._providers = []
        builder._validation_enabled = True

        from quadkit.contracts.exceptions import ContainerBuildError

        with pytest.raises(ContainerBuildError, match="Failed to validate"):
            await builder.build()
