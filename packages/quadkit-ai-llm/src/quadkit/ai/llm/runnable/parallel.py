"""RunnableParallel - run multiple runnables concurrently."""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.contracts.ai.runnable import RunnableProtocol


class RunnableParallel:
    """Run multiple runnables concurrently.

    Each runnable receives the same input and results are returned as a dict.
    """

    def __init__(self, **runnables: RunnableProtocol) -> None:
        self.runnables = runnables

    def invoke(self, input: Any) -> dict[str, Any]:
        """Synchronously invoke all runnables.

        Args:
            input: Input to pass to all runnables.

        Returns:
            Dict mapping names to outputs.
        """
        return {
            name: runnable.invoke(input) for name, runnable in self.runnables.items()
        }

    async def ainvoke(self, input: Any) -> dict[str, Any]:
        """Asynchronously invoke all runnables concurrently.

        Args:
            input: Input to pass to all runnables.

        Returns:
            Dict mapping names to outputs.
        """
        results = await asyncio.gather(
            *(runnable.ainvoke(input) for runnable in self.runnables.values())
        )
        return dict(zip(self.runnables.keys(), results, strict=True))
