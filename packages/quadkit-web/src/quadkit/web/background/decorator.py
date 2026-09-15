from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


def background(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator to run a function as a background task."""

    async def wrapper(*args: Any, **kwargs: Any) -> None:
        if asyncio.iscoroutinefunction(func):
            await func(*args, **kwargs)
        else:
            func(*args, **kwargs)

    return wrapper
