"""Orchestration saga primitives for long-running process coordination.

An *orchestration saga* coordinates a multi-step business transaction by
executing steps sequentially and running compensating actions in reverse
order when any step fails.  This model is suitable for distributed processes
where each step may mutate external state that must be undone on failure.

Typical usage::

    from quadkit.saga import AbstractSaga, SagaStep

    class OrderSaga(AbstractSaga[None]):
        def __init__(self, order_id: str, service: OrderService) -> None:
            super().__init__()
            self._order_id = order_id
            self.add_step(SagaStep(
                name="reserve_inventory",
                action=service.reserve_inventory,
                compensation=service.release_inventory,
            ))
            self.add_step(SagaStep(
                name="charge_payment",
                action=service.charge_payment,
                compensation=service.refund_payment,
            ))

        def get_id(self) -> str:
            return self._order_id

        def is_completed(self) -> bool:
            return self.state == SagaState.COMPLETED

    saga = OrderSaga(order_id="ord-1", service=svc)
    result = await saga.execute()
    if result.is_err():
        # All completed steps have already been compensated.
        ...

.. note::
    For durable saga execution across process restarts, inject a
    ``SagaStoreProtocol`` implementation.  Without a store the saga state
    is in-memory only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from typing import Any, Generic, TypeVar

from quadkit.contracts.exceptions import QuadkitError
from quadkit.contracts.workflow import SagaVersionMismatchError
from quadkit.contracts.workflow.protocols import SagaState, SagaStoreProtocol
from quadkit.contracts.workflow.steps import SagaStep
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

T = TypeVar("T")

_logger = get_logger(__name__)


class SagaError(QuadkitError):
    """Raised when a saga step fails after compensation has been attempted.

    Attributes:
        step_name: Name of the step that triggered the failure.
        cause: The original error returned by the step action.
    """

    _code: str = "QK_ERR_WF_019"

    def __init__(self, step_name: str, cause: Any) -> None:
        super().__init__(f"Saga step '{step_name}' failed: {cause}")
        self.step_name = step_name
        self.cause = cause


class AbstractSaga(ABC, Generic[T]):
    """Abstract base class for orchestration sagas.

    Subclasses declare their saga identity (``get_id``) and terminal
    condition (``is_completed``).  Steps are registered via ``add_step``
    and the full sequence is driven by ``execute``.

    Type Parameters:
        T: The saga state / context type (unused by the base class but
           carried for subclass typing convenience).

    Lifecycle:
        ``PENDING`` → ``RUNNING`` → ``COMPLETED``  (all steps succeed)
        ``PENDING`` → ``RUNNING`` → ``COMPENSATING`` → ``FAILED``
            (a step fails; already-completed steps are unwound)
    """

    def __init__(self, store: SagaStoreProtocol | None = None) -> None:
        self.state: SagaState = SagaState.PENDING
        self._store = store
        self._steps: list[SagaStep] = []
        self._completed_steps: list[SagaStep] = []
        self._compensated_steps: set[str] = set()

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    VERSION: int = 1  # Increment on breaking schema changes

    def get_version(self) -> int:
        """Return the current schema version for this saga class.

        Returns:
            The integer version declared on the class.
        """
        return self.VERSION

    def is_compatible_with(self, stored_version: int) -> bool:
        """Check if stored state version is compatible with this class.

        Override for custom migration logic (e.g. allow loading V1 in V2).

        Args:
            stored_version: Version number found in the persisted state.

        Returns:
            ``True`` when the stored version matches the class VERSION.
        """
        return stored_version == self.VERSION

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def get_id(self) -> str:
        """Return the stable identifier for this saga instance.

        Returns:
            A string that uniquely identifies this saga process.
        """

    @abstractmethod
    def is_completed(self) -> bool:
        """Return whether the saga has reached a terminal state.

        Returns:
            ``True`` when no further steps remain (success *or* fully
            compensated failure).
        """

    # ------------------------------------------------------------------
    # Step registration
    # ------------------------------------------------------------------

    def add_step(self, step: SagaStep) -> None:
        """Register a step to be executed as part of this saga.

        Steps are executed in the order they are added.

        Args:
            step: The step to append to the execution sequence.
        """
        self._steps.append(step)

    def was_compensated(self, step_name: str) -> bool:
        """Return whether *step_name* has been successfully compensated.

        Args:
            step_name: The :attr:`SagaStep.name` to check.

        Returns:
            ``True`` if the step's compensation action ran successfully.
        """
        return step_name in self._compensated_steps

    def mark_compensated(self, step_name: str) -> None:
        """Manually record *step_name* as compensated.

        Useful when compensation is performed externally (e.g., a separate
        process handles the rollback) and the saga state needs to be updated.

        Args:
            step_name: The :attr:`SagaStep.name` to mark as compensated.
        """
        self._compensated_steps.add(step_name)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self) -> Result[None, SagaError]:
        """Execute all registered steps in registration order.

        On first step failure, compensation is triggered for all
        previously completed steps (in reverse order) and an
        ``Err(SagaError(...))`` is returned.

        Returns:
            ``Ok(None)`` when all steps complete successfully.
            ``Err(SagaError)`` when any step fails (compensation already
            attempted before returning).
        """
        self.state = SagaState.RUNNING
        self._completed_steps = []
        await self._persist_state()

        for step in self._steps:
            _logger.debug("saga_step_started", saga_id=self.get_id(), step=step.name)

            step_result: Result[Any, Any] | None = None
            for attempt in range(max(step.max_retries, 1)):
                try:
                    step_result = await step.action()
                except Exception as exc:  # noqa: BLE001 — a raising step is a failed step; the saga contract compensates either way
                    step_result = Err(exc)
                if step_result.is_ok():
                    break
                if attempt < step.max_retries - 1:
                    _logger.debug(
                        "saga_step_retrying",
                        saga_id=self.get_id(),
                        step=step.name,
                        attempt=attempt + 1,
                        max_retries=step.max_retries,
                    )
                    await asyncio.sleep(step.retry_delay)

            assert step_result is not None  # loop guarantee  # noqa: S101

            if step_result.is_err():
                cause = step_result.unwrap_err()
                _logger.warning(
                    "saga_step_failed",
                    saga_id=self.get_id(),
                    step=step.name,
                    error=str(cause),
                )
                await self._run_compensation()
                return Err(SagaError(step.name, cause))

            _logger.debug("saga_step_completed", saga_id=self.get_id(), step=step.name)
            self._completed_steps.append(step)

        self.state = SagaState.COMPLETED
        await self._persist_state()
        _logger.info("saga_completed", saga_id=self.get_id())
        return Ok(None)

    async def compensate(self) -> None:
        """Manually trigger compensation for all completed steps.

        Useful when the calling code detects a failure condition outside
        the normal ``execute`` flow.
        """
        await self._run_compensation()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_compensation(self) -> None:
        """Execute compensating actions in reverse step order."""
        self.state = SagaState.COMPENSATING
        await self._persist_state()

        for step in reversed(self._completed_steps):
            _logger.debug(
                "saga_compensation_started", saga_id=self.get_id(), step=step.name
            )
            if step.compensation is None:
                _logger.debug(
                    "saga_compensation_skipped",
                    saga_id=self.get_id(),
                    step=step.name,
                )
                continue
            if not step.idempotent:
                _logger.warning(
                    "non_idempotent_compensation",
                    saga_id=self.get_id(),
                    step=step.name,
                    message=(
                        "Compensation not declared idempotent — "
                        "retry may cause data inconsistency"
                    ),
                )
            try:
                await step.compensation()
                self._compensated_steps.add(step.name)
                _logger.debug(
                    "saga_compensation_done", saga_id=self.get_id(), step=step.name
                )
            except Exception as exc:  # noqa: BLE001 — one failed compensation must not skip the rest
                _logger.error(
                    "saga_compensation_failed",
                    saga_id=self.get_id(),
                    step=step.name,
                    error=str(exc),
                )

        self.state = SagaState.FAILED
        await self._persist_state()

    async def _load_state(self) -> Result[Any, SagaVersionMismatchError]:
        """Load persisted state and validate version compatibility.

        Returns:
            ``Ok(stored)`` when the state is present and version-compatible.
            ``Err(SagaVersionMismatchError)`` when the stored version differs.
            ``Ok(None)`` when no persisted state exists.
        """
        if self._store is None:
            return Ok(None)
        # Untyped alias keeps the legacy-store branch statically reachable
        # (the store protocol already narrows to tuple | None).
        stored: Any = await self._store.load(self.get_id())
        if stored is None:
            return Ok(None)
        if isinstance(stored, tuple):
            _, data = stored
            stored_version = int(data.get("version", 1))
        else:
            # Defensive: protocol says tuple | None, but tolerate legacy
            # stores returning bare state objects.
            stored_version = int(getattr(stored, "version", 1))
        if not self.is_compatible_with(stored_version):
            return Err(
                SagaVersionMismatchError(
                    saga_id=self.get_id(),
                    expected_version=self.get_version(),
                    stored_version=stored_version,
                )
            )
        return Ok(stored)

    async def _persist_state(self) -> None:
        """Persist current state via the store if one is configured."""
        if self._store is None:
            return
        try:
            await self._store.save(
                self.get_id(), self.state, {"version": self.get_version()}
            )
        except Exception as exc:  # noqa: BLE001 — state metadata is advisory
            # ANY store error is logged and swallowed here (single guard
            # point) so callers can rely on _persist_state never raising.
            _logger.warning(
                "saga_store_persist_failed",
                saga_id=self.get_id(),
                state=self.state,
                error=str(exc),
            )


__all__ = ["AbstractSaga", "SagaError", "SagaState", "SagaStep"]
