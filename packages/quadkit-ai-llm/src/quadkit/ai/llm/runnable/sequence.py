"""RunnableSequence - chains runnables in sequence."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.ai.runnable import RunnableProtocol
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err

logger = get_logger(__name__)


class RunnableSequence:
    """Chain multiple runnables in sequence.

    The output of each runnable becomes the input to the next.
    Short-circuits on Err results.
    """

    def __init__(self, first: RunnableProtocol, second: RunnableProtocol) -> None:
        self.first = first
        self.second = second

    def invoke(self, input: Any) -> Any:
        """Synchronously invoke the chain.

        Args:
            input: Input to the first runnable.

        Returns:
            Output from the last runnable, or Err if any step fails.
        """
        result = self.first.invoke(input)
        if isinstance(result, Err):
            return result
        return self.second.invoke(result)

    async def ainvoke(self, input: Any) -> Any:
        """Asynchronously invoke the chain.

        Args:
            input: Input to the first runnable.

        Returns:
            Output from the last runnable, or Err if any step fails.
        """
        result = await self.first.ainvoke(input)
        if isinstance(result, Err):
            return result
        return await self.second.ainvoke(result)


class RunnableList:
    """Chain multiple runnables from a list.

    More flexible than pairwise RunnableSequence.
    """

    def __init__(self, steps: list[RunnableProtocol]) -> None:
        self.steps = steps

    def invoke(self, input: Any) -> Any:
        """Synchronously invoke each step in order.

        Args:
            input: Input to the first runnable.

        Returns:
            Output from the last runnable.
        """
        result = input
        for step in self.steps:
            result = step.invoke(result)
        return result

    async def ainvoke(self, input: Any) -> Any:
        """Asynchronously invoke each step in order.

        Args:
            input: Input to the first runnable.

        Returns:
            Output from the last runnable.
        """
        result = input
        for step in self.steps:
            result = await step.ainvoke(result)
        return result
