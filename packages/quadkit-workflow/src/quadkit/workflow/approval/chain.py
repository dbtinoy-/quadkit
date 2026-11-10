"""ApprovalChain — sequential multi-step approval orchestration."""

from __future__ import annotations

from collections.abc import Callable
import inspect

from quadkit.logging import get_logger, safe_error_type
from quadkit.workflow.approval.models import (
    ApprovalPolicy,
    ApprovalStatus,
    ApprovalStep,
)

logger = get_logger(__name__)


async def _evaluate_callable(callable_: Callable[[], object]) -> object:
    """Invoke a sync or async callable and await it when needed."""
    result = callable_()
    if inspect.isawaitable(result):
        result = await result
    return result


__all__ = ["ApprovalChain"]


class ApprovalChain:
    """Orchestrates a sequence of :class:`~quadkit.workflow.approval.ApprovalStep`
    objects under a configurable :class:`~quadkit.workflow.approval.ApprovalPolicy`.

    Each step is executed in registration order.  Steps whose *condition*
    returns ``False`` are skipped.  The final outcome is computed from the
    collected per-step statuses according to the active policy.

    Example::

        from quadkit.workflow.approval import ApprovalChain, ApprovalStep, ApprovalPolicy

        chain = ApprovalChain(policy=ApprovalPolicy.ALL)
        chain.add_step(ApprovalStep(
            name="manager_review",
            approver=manager_service.approve,
        ))
        chain.add_step(ApprovalStep(
            name="finance_review",
            approver=finance_service.approve,
            condition=lambda: request.amount > 10_000,
        ))

        approved, results = await chain.execute()
        if approved:
            await order_service.confirm(request_id)

    Args:
        policy: Determines the approval outcome based on individual step
            results.  Defaults to :attr:`~ApprovalPolicy.ALL`.
    """

    def __init__(self, policy: ApprovalPolicy = ApprovalPolicy.ALL) -> None:
        self._policy = policy
        self._steps: list[ApprovalStep] = []

    # ------------------------------------------------------------------
    # Step registration
    # ------------------------------------------------------------------

    def add_step(self, step: ApprovalStep) -> None:
        """Append *step* to the chain.

        Args:
            step: The approval step to add.
        """
        self._steps.append(step)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self) -> tuple[bool, dict[str, ApprovalStatus]]:
        """Run all steps in registration order and compute the final outcome.

        Steps whose *condition* returns ``False`` receive status
        :attr:`~ApprovalStatus.SKIPPED` and do not influence the policy
        outcome.

        Both *condition* and *approver* may be sync or async callables.
        Failure semantics are fail-closed for an approval gate: a step whose
        *condition* raises still RUNS (an error must never silently skip an
        approver), and a step whose *approver* raises is counted as
        :attr:`~ApprovalStatus.REJECTED` (a broken approver can never count
        as approval).  Either failure is logged, and the chain continues.

        Returns:
            A 2-tuple of:
            - ``bool``: ``True`` when the chain is approved per the policy.
            - ``dict[str, ApprovalStatus]``: Per-step status keyed by step name.
        """
        results: dict[str, ApprovalStatus] = {}

        for step in self._steps:
            if step.condition is not None:
                try:
                    should_run = await _evaluate_callable(step.condition)
                except Exception as exc:  # noqa: BLE001 — fail closed: run the step
                    logger.warning(
                        "approval_step.condition_error",
                        error_type=safe_error_type(exc),
                    )
                    should_run = True
                if not should_run:
                    results[step.name] = ApprovalStatus.SKIPPED
                    logger.debug("approval_step.skipped")
                    continue

            logger.debug("approval_step.started")
            try:
                approved = await _evaluate_callable(step.approver)
            except Exception as exc:  # noqa: BLE001 — fail closed: count as rejected
                logger.warning(
                    "approval_step.approver_error",
                    error_type=safe_error_type(exc),
                )
                approved = False
            status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            results[step.name] = status
            logger.info(
                "approval_step.completed",
                status=status,
            )

        outcome = self._evaluate_policy(results)
        logger.info(
            "approval_chain.completed",
            policy=self._policy,
            approved=outcome,
            step_count=len(results),
        )
        return outcome, results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate_policy(self, results: dict[str, ApprovalStatus]) -> bool:
        """Apply the configured policy to determine the final outcome.

        Only :attr:`~ApprovalStatus.APPROVED` and
        :attr:`~ApprovalStatus.REJECTED` statuses are counted; skipped steps
        are neutral.

        Args:
            results: Per-step status map produced by :meth:`execute`.

        Returns:
            ``True`` when the policy is satisfied; ``False`` otherwise.
        """
        non_skipped = {
            name: status
            for name, status in results.items()
            if status != ApprovalStatus.SKIPPED
        }
        if not non_skipped:
            # No runnable steps — treat as approved (vacuously true).
            return True

        approved_count = sum(
            1 for s in non_skipped.values() if s == ApprovalStatus.APPROVED
        )
        total = len(non_skipped)

        if self._policy == ApprovalPolicy.ALL:
            return approved_count == total
        if self._policy == ApprovalPolicy.ANY:
            return approved_count >= 1
        if self._policy == ApprovalPolicy.MAJORITY:
            return approved_count > total / 2
        raise AssertionError("unreachable: all ApprovalPolicy members handled")
