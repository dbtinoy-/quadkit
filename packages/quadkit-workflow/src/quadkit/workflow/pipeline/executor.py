"""In-process business process pipeline execution.

.. note::
    **Boundary with quadkit-tasks workflows:**

    This module provides synchronous in-process pipeline orchestration for
    multi-step business processes (validation → enrichment → persistence).

    For queue-backed background job chaining, use
    ``quadkit.tasks.workflows`` instead.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit import serialization as json
from quadkit.contracts.exceptions import PipelineExecutionError
from quadkit.logging import safe_error_type
from quadkit.primitives.pipeline import (
    PipelineContext,
    StepExecutionResult,
    StepStatus,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache import CacheBackendProtocol
    from quadkit.workflow.pipeline.steps import PipelineStep


def _logger() -> Any:
    from quadkit.logging import get_logger

    return get_logger(__name__)


class Pipeline:
    """Declarative pipeline for composing business workflows."""

    def __init__(
        self,
        name: str,
        steps: list[PipelineStep],
        checkpoint_store: CacheBackendProtocol | None = None,
    ) -> None:
        self.name = name
        self.steps = steps
        self._checkpoint_store = checkpoint_store
        self._validate_pipeline()

    def add_step(self, step: PipelineStep) -> None:
        """Append a step to this pipeline.

        Args:
            step: The PipelineStep to append. Validates pipeline structure
                after addition.

        Raises:
            ValueError: If the new step creates duplicate names or broken deps.
        """
        self.steps.append(step)
        self._validate_pipeline()

    def _validate_pipeline(self) -> None:
        """Validate pipeline structure and dependencies."""
        step_names = {step.name for step in self.steps}

        if len(step_names) != len(self.steps):
            raise ValueError("Duplicate step names are not allowed.")

        for step in self.steps:
            for dep in step.dependencies:
                if dep not in step_names:
                    raise ValueError("Pipeline contains an unknown step dependency.")

        self._check_circular_dependencies()

    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies using topological sort."""
        graph = {step.name: step.dependencies for step in self.steps}

        visiting = set()
        visited = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("Circular dependency detected.")
            if node in visited:
                return

            visiting.add(node)
            for dep in graph.get(node, []):
                visit(dep)
            visiting.remove(node)
            visited.add(node)

        for step_name in graph:
            if step_name not in visited:
                visit(step_name)

    def _get_execution_order(self) -> list[PipelineStep]:
        """Get steps in dependency order using topological sort."""
        indegree = {step.name: 0 for step in self.steps}
        adj: dict[str, list[PipelineStep]] = {step.name: [] for step in self.steps}

        for step in self.steps:
            for dep_name in step.dependencies:
                if dep_name in adj:
                    adj[dep_name].append(step)
                    indegree[step.name] += 1

        queue = [step for step in self.steps if indegree[step.name] == 0]
        result: list[PipelineStep] = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for dependent in adj.get(current.name, []):
                indegree[dependent.name] -= 1
                if indegree[dependent.name] == 0:
                    queue.append(dependent)

        if len(result) != len(self.steps):
            msg = "Pipeline has circular dependencies or unreachable steps"
            raise ValueError(msg)

        return result

    def to_dot(self) -> str:
        """Return a Graphviz DOT representation of the pipeline execution graph.

        Nodes represent pipeline steps; directed edges represent declared
        dependencies (``dep → step``).  The output can be rendered with
        ``dot -Tpng`` or pasted into an online Graphviz viewer.

        Returns:
            A string containing valid Graphviz DOT source for the pipeline.

        Example::

            dot_src = pipeline.to_dot()
            # dot -Tsvg -o pipeline.svg <<< "$(python -c '...')"
        """
        safe_name = self.name.replace('"', '\\"')
        lines: list[str] = [
            f'digraph "{safe_name}" {{',
            "    rankdir=LR;",
            '    node [shape=box, style=filled, fillcolor="#dae8fc"];',
        ]
        for step in self.steps:
            safe_step = step.name.replace('"', '\\"')
            lines.append(f'    "{safe_step}";')

        for step in self.steps:
            safe_step = step.name.replace('"', '\\"')
            for dep in step.dependencies:
                safe_dep = dep.replace('"', '\\"')
                lines.append(f'    "{safe_dep}" -> "{safe_step}";')

        lines.append("}")
        return "\n".join(lines)

    async def execute(
        self,
        initial_context: PipelineContext | None = None,
        fail_fast: bool = True,
    ) -> Result[PipelineContext, Exception]:
        """Execute the pipeline."""
        context = initial_context or PipelineContext(self.name)
        context.start_time = asyncio.get_running_loop().time()

        # Restore previously checkpointed step results when a store is available.
        checkpoint_key = f"pipeline:checkpoint:{self.name}"
        completed_step_names: set[str] = set()
        if self._checkpoint_store is not None:
            try:
                result = await self._checkpoint_store.get(checkpoint_key)
                if result.is_ok():
                    raw = result.unwrap()
                    if raw is not None:
                        payload: dict[str, Any] = json.loads(raw)
                        for step_name, result_value in payload.items():
                            context.set_step_result(step_name, result_value)
                            completed_step_names.add(step_name)
                        _logger().debug(
                            "pipeline.checkpoint_restored",
                            restored_step_count=len(completed_step_names),
                        )
            except Exception as exc:  # noqa: BLE001 — best-effort restore
                _logger().warning(
                    "pipeline.checkpoint_restore_failed",
                    error_type=safe_error_type(exc),
                )

        try:
            execution_order = self._get_execution_order()
            step_results: list[StepExecutionResult[Any]] = []

            for step in execution_order:
                # Skip steps already completed in a previous run (checkpoint resume).
                if step.name in completed_step_names:
                    step_results.append(
                        StepExecutionResult(
                            step_name=step.name,
                            status=StepStatus.SKIPPED,
                            skipped_reason="Resumed from checkpoint",
                        ),
                    )
                    continue

                skip_result = await step.should_skip(context)

                if skip_result.is_err():
                    step_results.append(
                        StepExecutionResult(
                            step_name=step.name,
                            status=StepStatus.FAILED,
                            error=Exception(
                                f"Pipeline step failed ({safe_error_type(skip_result.unwrap_err())})."
                            ),
                        ),
                    )
                    if fail_fast:
                        break
                    continue

                if skip_result.unwrap_or(False):
                    step_results.append(
                        StepExecutionResult(
                            step_name=step.name,
                            status=StepStatus.SKIPPED,
                            skipped_reason="Condition not met",
                        ),
                    )
                    continue

                start_time = asyncio.get_running_loop().time()
                step_results.append(
                    StepExecutionResult(
                        step_name=step.name,
                        status=StepStatus.RUNNING,
                    ),
                )

                try:
                    step_result: Result[Any, Exception]
                    if step.resilience is not None:
                        raw = await step.resilience.execute(step.execute, context)
                        step_result = raw if isinstance(raw, Result) else Ok(raw)
                    elif step.timeout is not None:
                        try:
                            step_value = await asyncio.wait_for(
                                step.execute(context), timeout=step.timeout
                            )
                            step_result = Ok(step_value)
                        except TimeoutError as exc:
                            step_result = Err(exc)
                    else:
                        step_result = await step.execute(context)
                    duration = asyncio.get_running_loop().time() - start_time

                    if step_result.is_ok():
                        step_value = step_result.unwrap()
                        context.set_step_result(step.name, step_value)
                        completed_step_names.add(step.name)
                        step_results[-1] = StepExecutionResult(
                            step_name=step.name,
                            status=StepStatus.COMPLETED,
                            result=step_value,
                            duration=duration,
                        )
                        # Persist checkpoint so the pipeline can resume from here
                        # on restart without re-running successful steps.
                        if self._checkpoint_store is not None:
                            try:
                                checkpoint_data = {
                                    n: context.get_step_result(n)
                                    for n in completed_step_names
                                }
                                await self._checkpoint_store.set(
                                    checkpoint_key,
                                    json.dumps_str(checkpoint_data),
                                )
                            except Exception as exc:  # noqa: BLE001
                                # Best-effort save — a checkpoint-store error
                                # must not fail the pipeline itself.
                                _logger().warning(
                                    "pipeline.checkpoint_save_failed",
                                    error_type=safe_error_type(exc),
                                )
                    else:
                        error_result = await step.on_error(
                            context,
                            step_result.unwrap_err(),
                        )
                        if error_result.is_ok():
                            context.set_step_result(
                                step.name,
                                error_result.unwrap(),
                            )
                            step_results[-1] = StepExecutionResult(
                                step_name=step.name,
                                status=StepStatus.COMPLETED,
                                result=error_result.unwrap(),
                                duration=duration,
                            )
                        else:
                            step_results[-1] = StepExecutionResult(
                                step_name=step.name,
                                status=StepStatus.FAILED,
                                error=Exception(
                                    f"Pipeline step failed ({safe_error_type(step_result.unwrap_err())})."
                                ),
                                duration=duration,
                            )
                            if fail_fast:
                                break

                except Exception as e:  # noqa: BLE001 — step-failure boundary
                    # ANY step error (KeyError, SDK errors, ...) -> failed
                    # step result so fail_fast / continue semantics apply.
                    _logger().warning(
                        "pipeline_step_failed",
                        error_type=safe_error_type(e),
                    )
                    duration = asyncio.get_running_loop().time() - start_time
                    step_results[-1] = StepExecutionResult(
                        step_name=step.name,
                        status=StepStatus.FAILED,
                        error=Exception(
                            f"Pipeline step failed ({safe_error_type(e)})."
                        ),
                        duration=duration,
                    )
                    if fail_fast:
                        break

                raw_cleanup = await step.cleanup(context)
                cleanup_result = (
                    raw_cleanup if isinstance(raw_cleanup, Result) else Ok(raw_cleanup)
                )
                if cleanup_result.is_err():
                    _logger().warning(
                        "pipeline_step_cleanup_failed",
                        error_type=safe_error_type(cleanup_result.unwrap_err()),
                    )

            context.end_time = asyncio.get_running_loop().time()
            context.add_metadata("step_results", step_results)
            context.add_metadata(
                "total_duration",
                context.end_time - context.start_time,
            )

            failed_steps = list(
                filter(lambda r: r.status == StepStatus.FAILED, step_results),
            )
            if failed_steps:
                first_failure = failed_steps[0]
                return Err(
                    PipelineExecutionError(
                        "pipeline",
                        first_failure.error or Exception("Pipeline step failed."),
                    ),
                )

            # Clear checkpoint after successful completion — next run starts fresh.
            if self._checkpoint_store is not None:
                try:
                    await self._checkpoint_store.delete(checkpoint_key)
                except Exception as exc:  # noqa: BLE001 — best-effort clear
                    _logger().warning(
                        "pipeline.checkpoint_clear_failed",
                        error_type=safe_error_type(exc),
                    )

            return Ok(context)
        except Exception as e:  # noqa: BLE001 — pipeline-failure boundary
            # ANY unexpected error becomes Err(PipelineExecutionError)
            # instead of escaping raw. CancelledError (BaseException) is
            # deliberately not caught.
            _logger().warning(
                "pipeline_execution_failed",
                error_type=safe_error_type(e),
            )
            return Err(
                PipelineExecutionError(
                    "pipeline",
                    Exception("Pipeline execution failed."),
                )
            )


__all__ = ["Pipeline"]
