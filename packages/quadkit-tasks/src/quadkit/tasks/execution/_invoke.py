"""Shared handler invocation helpers."""

from __future__ import annotations

import inspect
from typing import Any


async def invoke_handler(handler: Any, /, *args: Any, **kwargs: Any) -> Any:
    """Invoke a task handler and await awaitable return values.

    Supports:
    - plain synchronous callables
    - ``async def`` handlers
    - callable wrapper objects whose ``__call__`` returns a coroutine

    Args:
        handler: Callable task handler.
        *args: Positional arguments for the handler.
        **kwargs: Keyword arguments for the handler.

    Returns:
        The handler's resolved return value.
    """
    result = handler(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


__all__ = ["invoke_handler"]
