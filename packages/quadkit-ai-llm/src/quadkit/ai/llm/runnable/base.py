"""RunnableMixin with pipe operator."""

from __future__ import annotations

from typing import Any

from quadkit.ai.llm.runnable.sequence import RunnableSequence
from quadkit.contracts.ai.runnable import RunnableProtocol


class RunnableMixin(RunnableProtocol):
    """Mixin that adds pipe operator to runnables.

    Provides the ``|`` operator that composes runnables into RunnableSequence.
    Analogous to LangChain's RunnableBinding.
    """

    def invoke(self, input: Any) -> Any:
        """Process input synchronously. Override in subclass."""
        raise NotImplementedError

    async def ainvoke(self, input: Any) -> Any:
        """Process input asynchronously. Override in subclass."""
        raise NotImplementedError

    def __or__(self, other: RunnableProtocol) -> RunnableSequence:
        """Compose this runnable with another using pipe operator.

        Args:
            other: The runnable to compose with.

        Returns:
            RunnableSequence that chains self followed by other.
        """
        from quadkit.ai.llm.runnable.sequence import RunnableSequence

        return RunnableSequence(self, other)

    def __ror__(self, other: RunnableProtocol) -> RunnableSequence:
        """Reverse pipe for cases where left operand isn't a runnable.

        Args:
            other: The runnable on the left side.

        Returns:
            RunnableSequence that chains other followed by self.
        """
        from quadkit.ai.llm.runnable.sequence import RunnableSequence

        return RunnableSequence(other, self)
