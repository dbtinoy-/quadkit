"""Tests for RunnableBranch."""
from __future__ import annotations

import pytest

from quadkit.ai.llm.runnable.lambda_ import RunnableLambda


class TestRunnableBranch:
    """Tests for RunnableBranch."""

    def test_branch_routes_to_first_match(self) -> None:
        """Branch should route to first matching predicate."""
        from quadkit.ai.llm.runnable.branch import RunnableBranch

        branch = RunnableBranch(
            branches=[
                (lambda x: x > 10, RunnableLambda(lambda x: f"big:{x}")),
                (lambda x: x > 5, RunnableLambda(lambda x: f"medium:{x}")),
            ],
            default=RunnableLambda(lambda x: f"small:{x}"),
        )

        assert branch.invoke(15) == "big:15"
        assert branch.invoke(7) == "medium:7"
        assert branch.invoke(3) == "small:3"

    @pytest.mark.asyncio
    async def test_branch_ainvoke(self) -> None:
        """Branch should work with ainvoke."""
        from quadkit.ai.llm.runnable.branch import RunnableBranch

        branch = RunnableBranch(
            branches=[
                (lambda x: x > 10, RunnableLambda(lambda x: f"big:{x}")),
            ],
            default=RunnableLambda(lambda x: f"small:{x}"),
        )

        assert await branch.ainvoke(15) == "big:15"
        assert await branch.ainvoke(3) == "small:3"

    def test_branch_no_match_uses_default(self) -> None:
        """Branch should use default when no predicate matches."""
        from quadkit.ai.llm.runnable.branch import RunnableBranch

        branch = RunnableBranch(
            branches=[
                (lambda x: x > 100, RunnableLambda(lambda _: "big")),
            ],
            default=RunnableLambda(lambda _: "default"),
        )

        assert branch.invoke(5) == "default"

    @pytest.mark.asyncio
    async def test_predicate_error_logs_only_exception_type(self, capsys) -> None:
        """Predicate failures are safely ignored without logging their text."""
        from quadkit.ai.llm.runnable.branch import RunnableBranch

        secret = "RUNNABLE_BRANCH_SECRET_SENTINEL"

        def fail_predicate(_: object) -> bool:
            raise RuntimeError(secret)

        branch = RunnableBranch(
            branches=[(fail_predicate, RunnableLambda(lambda _: "matched"))],
            default=RunnableLambda(lambda _: "default"),
        )
        result = await branch.ainvoke("input")

        assert result == "default"
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err
