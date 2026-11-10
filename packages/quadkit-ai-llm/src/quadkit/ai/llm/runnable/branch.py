"""RunnableBranch - route by predicate."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from quadkit.contracts.ai.runnable import RunnableProtocol
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Ok

logger = get_logger(__name__)


class RunnableBranch:
    """Route input to different runnables based on a predicate.

    Like LangChain's RunnableBranch, this evaluates predicates to select
    which branch to execute.
    """

    def __init__(
        self,
        branches: list[tuple[Callable[[Any], bool], RunnableProtocol]],
        default: RunnableProtocol | None = None,
    ) -> None:
        self.branches = branches
        self.default = default

    def invoke(self, input: Any) -> Any:
        """Synchronously route to matching branch.

        Args:
            input: Input to evaluate against predicates.

        Returns:
            Output from the first matching branch, or default if no match.
        """
        for predicate, runnable in self.branches:
            try:
                if predicate(input):
                    return runnable.invoke(input)
            except Exception as e:
                logger.warning("branch_predicate_error", error_type=type(e).__name__)
                continue

        if self.default is not None:
            return self.default.invoke(input)

        return Ok(input)

    async def ainvoke(self, input: Any) -> Any:
        """Asynchronously route to matching branch.

        Args:
            input: Input to evaluate against predicates.

        Returns:
            Output from the first matching branch, or default if no match.
        """
        for predicate, runnable in self.branches:
            try:
                result = (
                    predicate(input)
                    if not asyncio.iscoroutinefunction(predicate)
                    else await predicate(input)
                )
                if result:
                    return await runnable.ainvoke(input)
            except Exception as e:
                logger.warning("branch_predicate_error", error_type=type(e).__name__)
                continue

        if self.default is not None:
            return await self.default.ainvoke(input)

        return Ok(input)
