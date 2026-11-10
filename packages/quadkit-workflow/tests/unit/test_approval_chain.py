"""Tests for ApprovalChain execution and fail-closed semantics (round 13)."""

from __future__ import annotations

from quadkit.workflow.approval import (
    ApprovalChain,
    ApprovalPolicy,
    ApprovalStatus,
    ApprovalStep,
)
import pytest


def _step(
    name: str,
    approved: bool = True,
    condition=None,
    raise_in_approver: Exception | None = None,
    raise_in_condition: Exception | None = None,
) -> ApprovalStep:
    async def approver() -> bool:
        if raise_in_approver is not None:
            raise raise_in_approver
        return approved

    async def cond() -> bool:
        if raise_in_condition is not None:
            raise raise_in_condition
        if condition is None:
            return True
        return condition

    return ApprovalStep(name=name, approver=approver, condition=cond if condition is not None else None)


class TestPolicyOutcome:
    @pytest.mark.asyncio
    async def test_all_policy_all_approved(self) -> None:
        chain = ApprovalChain(policy=ApprovalPolicy.ALL)
        chain.add_step(_step("a"))
        chain.add_step(_step("b"))
        approved, results = await chain.execute()
        assert approved is True
        assert results == {"a": ApprovalStatus.APPROVED, "b": ApprovalStatus.APPROVED}

    @pytest.mark.asyncio
    async def test_all_policy_one_rejected(self) -> None:
        chain = ApprovalChain(policy=ApprovalPolicy.ALL)
        chain.add_step(_step("a"))
        chain.add_step(_step("b", approved=False))
        approved, _ = await chain.execute()
        assert approved is False

    @pytest.mark.asyncio
    async def test_any_policy_one_approved(self) -> None:
        chain = ApprovalChain(policy=ApprovalPolicy.ANY)
        chain.add_step(_step("a", approved=False))
        chain.add_step(_step("b"))
        approved, _ = await chain.execute()
        assert approved is True

    @pytest.mark.asyncio
    async def test_any_policy_none_approved(self) -> None:
        chain = ApprovalChain(policy=ApprovalPolicy.ANY)
        chain.add_step(_step("a", approved=False))
        approved, _ = await chain.execute()
        assert approved is False

    @pytest.mark.asyncio
    async def test_majority_policy_two_of_three(self) -> None:
        chain = ApprovalChain(policy=ApprovalPolicy.MAJORITY)
        chain.add_step(_step("a"))
        chain.add_step(_step("b"))
        chain.add_step(_step("c", approved=False))
        approved, _ = await chain.execute()
        assert approved is True

    @pytest.mark.asyncio
    async def test_majority_policy_one_of_three(self) -> None:
        chain = ApprovalChain(policy=ApprovalPolicy.MAJORITY)
        chain.add_step(_step("a"))
        chain.add_step(_step("b", approved=False))
        chain.add_step(_step("c", approved=False))
        approved, _ = await chain.execute()
        assert approved is False

    @pytest.mark.asyncio
    async def test_empty_chain_is_vacuously_approved(self) -> None:
        approved, results = await ApprovalChain().execute()
        assert approved is True
        assert results == {}


class TestStepSkips:
    @pytest.mark.asyncio
    async def test_condition_false_marks_skipped_and_is_neutral(self) -> None:
        chain = ApprovalChain(policy=ApprovalPolicy.ALL)
        chain.add_step(_step("a", condition=False))
        chain.add_step(_step("b", approved=False))
        approved, results = await chain.execute()
        assert results["a"] == ApprovalStatus.SKIPPED
        # The skipped step is neutral — 'b' alone decides.
        assert approved is False

    @pytest.mark.asyncio
    async def test_all_steps_skipped_is_vacuously_approved(self) -> None:
        chain = ApprovalChain(policy=ApprovalPolicy.ANY)
        chain.add_step(_step("a", condition=False))
        approved, results = await chain.execute()
        assert approved is True
        assert results == {"a": ApprovalStatus.SKIPPED}


class TestSyncCallables:
    """The docstring example uses a sync lambda condition; both styles must
    work, since the type allows ``Callable[..., Awaitable[bool]]`` consumers
    that build conditions inline."""

    @pytest.mark.asyncio
    async def test_sync_condition_and_approver(self) -> None:
        chain = ApprovalChain()
        chain.add_step(
            ApprovalStep(name="amount", approver=lambda: True, condition=lambda: 50 > 10)
        )
        chain.add_step(
            ApprovalStep(name="never", approver=lambda: False, condition=lambda: False)
        )
        approved, results = await chain.execute()
        assert results == {
            "amount": ApprovalStatus.APPROVED,
            "never": ApprovalStatus.SKIPPED,
        }
        assert approved is True


class TestFailClosedSemantics:
    @pytest.mark.asyncio
    async def test_condition_error_still_runs_step(self) -> None:
        """A condition that raises must never silently skip an approver."""
        chain = ApprovalChain(policy=ApprovalPolicy.ALL)
        chain.add_step(_step("a", approved=False, raise_in_condition=RuntimeError("cond broken")))
        approved, results = await chain.execute()
        # Step ran despite the condition error and rejected.
        assert results["a"] == ApprovalStatus.REJECTED
        assert approved is False

    @pytest.mark.asyncio
    async def test_approver_error_counts_as_rejected_and_chain_continues(self) -> None:
        chain = ApprovalChain(policy=ApprovalPolicy.ALL)
        chain.add_step(_step("a", raise_in_approver=RuntimeError("approver down")))
        chain.add_step(_step("b"))
        approved, results = await chain.execute()
        assert results["a"] == ApprovalStatus.REJECTED
        assert results["b"] == ApprovalStatus.APPROVED
        assert approved is False

    @pytest.mark.asyncio
    async def test_approver_error_with_any_policy(self) -> None:
        """A broken approver can be the ANY-policy winner: it is rejected,
        and a healthy approver still approves the chain."""
        chain = ApprovalChain(policy=ApprovalPolicy.ANY)
        chain.add_step(_step("a", raise_in_approver=RuntimeError("approver down")))
        chain.add_step(_step("b"))
        approved, _ = await chain.execute()
        assert approved is True
