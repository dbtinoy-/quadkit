"""Pipeline step types for building pipeline workflows."""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.exceptions import PipelineExecutionError
from quadkit.logging import safe_error_type
from quadkit.primitives.pipeline import PipelineContext
from quadkit.primitives.pipeline import PipelineStep as PipelineStep
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def _logger() -> Any:
    from quadkit.logging import get_logger

    return get_logger(__name__)


class FunctionStep(PipelineStep):
    """Pipeline step that executes a function."""

    def __init__(
        self,
        name: str,
        func: Callable[
            [PipelineContext],
            Result[Any, Exception] | Awaitable[Result[Any, Exception]],
        ],
        dependencies: list[str] | None = None,
        skip_condition: (
            Callable[
                [PipelineContext],
                Result[bool, Exception] | Awaitable[Result[bool, Exception]],
            ]
            | None
        ) = None,
        error_handler: (
            Callable[
                [PipelineContext, Exception],
                Result[Any, Exception] | Awaitable[Result[Any, Exception]],
            ]
            | None
        ) = None,
        cleanup_func: (
            Callable[
                [PipelineContext],
                Result[None, Exception] | Awaitable[Result[None, Exception]],
            ]
            | None
        ) = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(name, dependencies, timeout=timeout)
        self.func = func
        self.skip_condition = skip_condition
        self.error_handler = error_handler
        self.cleanup_func = cleanup_func

    async def execute(self, context: PipelineContext) -> Result[Any, Exception]:
        """Execute the function, honoring optional per-step timeout."""

        async def _run() -> Result[Any, Exception]:
            if inspect.iscoroutinefunction(self.func):
                value: Result[Any, Exception] = await self.func(context)
                return value
            return self.func(context)  # type: ignore[return-value]

        try:
            if self.timeout is not None:
                result = await asyncio.wait_for(_run(), timeout=self.timeout)
            else:
                result = await _run()
            return result
        except TimeoutError as exc:
            _logger().warning(
                "pipeline_step_timeout",
                error_type=safe_error_type(exc),
            )
            return Err(Exception("Pipeline step timed out."))
        except Exception as exc:  # noqa: BLE001 — step-failure boundary
            # ANY step error becomes Err(...) so the pipeline can apply its
            # fail-fast / continue semantics uniformly.
            _logger().warning(
                "pipeline_step_failed",
                error_type=safe_error_type(exc),
            )
            return Err(Exception(f"Pipeline step failed ({safe_error_type(exc)})."))

    async def should_skip(self, context: PipelineContext) -> Result[bool, Exception]:
        """Check skip condition."""
        if self.skip_condition:
            try:
                if inspect.iscoroutinefunction(self.skip_condition):
                    result = await self.skip_condition(context)
                else:
                    result = self.skip_condition(context)
                # Normalize plain bool to Ok(bool) — skip_condition may return bool or Result
                return result if isinstance(result, Result) else Ok(bool(result))
            except Exception as exc:  # noqa: BLE001 — skip-condition boundary
                _logger().warning(
                    "pipeline_skip_condition_failed",
                    error_type=safe_error_type(exc),
                )
                return Err(
                    Exception(
                        f"Pipeline skip condition failed ({safe_error_type(exc)})."
                    )
                )
        return await super().should_skip(context)

    async def on_error(
        self,
        context: PipelineContext,
        error: Exception,
    ) -> Result[Any, Exception]:
        """Handle errors."""
        if self.error_handler:
            try:
                if inspect.iscoroutinefunction(self.error_handler):
                    return cast(
                        "Result[Any, Exception]",
                        await self.error_handler(context, error),
                    )
                return cast(
                    "Result[Any, Exception]",
                    self.error_handler(context, error),
                )
            except Exception as exc:  # noqa: BLE001 — error-handler boundary
                # An error handler that itself fails returns a safe Err value.
                _logger().warning(
                    "pipeline_error_handler_failed",
                    error_type=safe_error_type(exc),
                )
                return Err(
                    Exception(
                        f"Pipeline error handler failed ({safe_error_type(exc)})."
                    )
                )
        outcome: Result[Any, Exception] = await super().on_error(context, error)
        return outcome

    async def cleanup(self, context: PipelineContext) -> Result[None, Exception]:
        """Cleanup resources."""
        if self.cleanup_func:
            try:
                if inspect.iscoroutinefunction(self.cleanup_func):
                    return cast(
                        "Result[None, Exception]",
                        await self.cleanup_func(context),
                    )
                return cast("Result[None, Exception]", self.cleanup_func(context))
            except Exception as exc:  # noqa: BLE001 — cleanup boundary
                _logger().warning(
                    "pipeline_step_cleanup_failed",
                    error_type=safe_error_type(exc),
                )
                return Err(
                    Exception(f"Pipeline step cleanup failed ({safe_error_type(exc)}).")
                )
        return await super().cleanup(context)


class ConditionalStep(PipelineStep):
    """Pipeline step that executes conditionally based on a predicate."""

    def __init__(
        self,
        name: str,
        condition: Callable[
            [PipelineContext],
            Result[bool, Exception] | Awaitable[Result[bool, Exception]],
        ],
        true_step: PipelineStep,
        false_step: PipelineStep | None = None,
        dependencies: list[str] | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(name, dependencies, timeout=timeout)
        self.condition = condition
        self.true_step = true_step
        self.false_step = false_step

    async def execute(self, context: PipelineContext) -> Result[Any, Exception]:
        """Execute the appropriate step based on condition."""

        async def _inner() -> Result[Any, Exception]:
            try:
                if inspect.iscoroutinefunction(self.condition):
                    condition_result = cast(
                        "Result[bool, Exception]",
                        await self.condition(context),
                    )
                else:
                    condition_result = cast(
                        "Result[bool, Exception]",
                        self.condition(context),
                    )
            except Exception as exc:  # noqa: BLE001 — condition boundary
                _logger().warning(
                    "pipeline_condition_failed",
                    error_type=safe_error_type(exc),
                )
                return Err(
                    Exception(f"Pipeline condition failed ({safe_error_type(exc)}).")
                )

            if condition_result.is_err():
                return Err(
                    Exception(
                        "Pipeline condition failed "
                        f"({safe_error_type(condition_result.unwrap_err())})."
                    )
                )

            try:
                if condition_result.unwrap():
                    branch_result = await self.true_step.execute(context)
                elif self.false_step:
                    branch_result = await self.false_step.execute(context)
                else:
                    return Ok(None)
            except Exception as exc:  # noqa: BLE001 — branch-failure boundary
                _logger().warning(
                    "pipeline_conditional_branch_failed",
                    error_type=safe_error_type(exc),
                )
                return Err(
                    Exception(f"Conditional branch failed ({safe_error_type(exc)}).")
                )
            if branch_result.is_err():
                return Err(
                    Exception(
                        "Conditional branch failed "
                        f"({safe_error_type(branch_result.unwrap_err())})."
                    )
                )
            return branch_result

        if self.timeout is not None:
            try:
                return await asyncio.wait_for(_inner(), timeout=self.timeout)
            except TimeoutError as exc:
                _logger().warning(
                    "pipeline_condition_timeout",
                    error_type=safe_error_type(exc),
                )
                return Err(Exception("Pipeline condition timed out."))
        return await _inner()

    async def should_skip(self, context: PipelineContext) -> Result[bool, Exception]:
        """Conditional steps should not be skipped."""
        del context
        return Ok(False)


class ParallelStep(PipelineStep):
    """Pipeline step that executes multiple steps in parallel."""

    def __init__(
        self,
        name: str,
        steps: list[PipelineStep],
        dependencies: list[str] | None = None,
        *,
        fail_fast: bool = True,
        timeout: float | None = None,
    ) -> None:
        super().__init__(name, dependencies, timeout=timeout)
        self.steps = steps
        self.fail_fast = fail_fast

    async def execute(self, context: PipelineContext) -> Result[list[Any], Exception]:
        """Execute all steps in parallel."""

        async def _inner() -> Result[list[Any], Exception]:
            async def execute_step(step: PipelineStep) -> Result[Any, Exception]:
                return await step.execute(context)

            tasks = [asyncio.create_task(execute_step(step)) for step in self.steps]

            if not tasks:
                return Ok([])

            if self.fail_fast:
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                any_failed = False
                for task in done:
                    res: Result[Any, Exception] | Exception
                    try:
                        res = task.result()
                    except Exception as exc:  # noqa: BLE001 — step raised, didn't Err
                        res = exc
                    if isinstance(res, Exception) or (
                        isinstance(res, Result) and res.is_err()
                    ):
                        any_failed = True
                        break

                if any_failed:
                    for task in pending:
                        task.cancel()
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_results: list[Any] = []
            errors: list[Exception] = []

            for result in results:
                if isinstance(result, Exception):
                    _logger().warning(
                        "pipeline_parallel_step_failed",
                        error_type=safe_error_type(result),
                    )
                    errors.append(
                        Exception(
                            f"Parallel pipeline step failed ({safe_error_type(result)})."
                        )
                    )
                    if self.fail_fast:
                        break
                else:
                    res = cast("Result[Any, Exception]", result)
                    if res.is_err():
                        errors.append(
                            Exception(
                                "Parallel pipeline step failed "
                                f"({safe_error_type(res.unwrap_err())})."
                            )
                        )
                        if self.fail_fast:
                            break
                    else:
                        successful_results.append(res.unwrap())

            if errors:
                return Err(
                    PipelineExecutionError(
                        "parallel",
                        Exception("Parallel pipeline execution failed."),
                    )
                )

            return Ok(successful_results)

        if self.timeout is not None:
            try:
                return await asyncio.wait_for(_inner(), timeout=self.timeout)
            except TimeoutError as exc:
                _logger().warning(
                    "pipeline_parallel_timeout",
                    error_type=safe_error_type(exc),
                )
                return Err(Exception("Parallel pipeline execution timed out."))
        return await _inner()


__all__ = [
    "ConditionalStep",
    "FunctionStep",
    "ParallelStep",
    "PipelineStep",
]
