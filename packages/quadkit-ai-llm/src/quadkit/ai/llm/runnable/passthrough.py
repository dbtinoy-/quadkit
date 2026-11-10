"""RunnablePassthrough - returns input with assigned keys."""

from __future__ import annotations

from typing import Any


class RunnablePassthrough:
    """Pass input through with optional key assignment.

    Returns the input unchanged but can assign it to a key in the output dict.
    Useful for combining with RunnableParallel.
    """

    def __init__(self, name: str | None = None) -> None:
        self.name = name

    def invoke(self, input: Any) -> Any:
        """Return input, optionally wrapped in dict with named key.

        Args:
            input: Input to pass through.

        Returns:
            Input as-is, or dict with named key if name is set.
        """
        if self.name is not None:
            return {self.name: input}
        return input

    async def ainvoke(self, input: Any) -> Any:
        """Return input, optionally wrapped in dict with named key.

        Args:
            input: Input to pass through.

        Returns:
            Input as-is, or dict with named key if name is set.
        """
        if self.name is not None:
            return {self.name: input}
        return input
