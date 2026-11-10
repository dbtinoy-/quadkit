"""RunnableLambda - wrap callables as runnables."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from quadkit.contracts.ai.exceptions import RunnableError
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err

logger = get_logger(__name__)


class RunnableLambda:
    """Wrap a function as a runnable.

    Accepts sync or async functions and wraps them to satisfy RunnableProtocol.
    Failures become Err(RunnableError(...)).

    Args:
        func: A sync or async function to wrap.
    """

    def __init__(self, func: Callable[[Any], Any]) -> None:
        self.func = func

    def invoke(self, input: Any) -> Any:
        """Synchronously invoke the wrapped function.

        Args:
            input: Input to the function.

        Returns:
            Function output or Err on failure.
        """
        try:
            if asyncio.iscoroutinefunction(self.func):
                raise TypeError("Use ainvoke for async functions")
            return self.func(input)
        except Exception as e:
            error_type = type(e).__name__
            logger.warning("runnable_lambda_error", error_type=error_type)
            return Err(
                RunnableError(
                    "Lambda execution failed",
                    details={"error_type": error_type},
                )
            )

    async def ainvoke(self, input: Any) -> Any:
        """Asynchronously invoke the wrapped function.

        Args:
            input: Input to the function.

        Returns:
            Function output or Err on failure.
        """
        try:
            if asyncio.iscoroutinefunction(self.func):
                return await self.func(input)
            return self.func(input)
        except Exception as e:
            error_type = type(e).__name__
            logger.warning("runnable_lambda_error", error_type=error_type)
            return Err(
                RunnableError(
                    "Lambda execution failed",
                    details={"error_type": error_type},
                )
            )
