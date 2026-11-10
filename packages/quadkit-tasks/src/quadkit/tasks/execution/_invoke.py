"""Single-source handler invocation for task execution paths.

Tasks may be registered as ``async def`` coroutines, synchronous callables,
class-based tasks defining ``execute(self, ...)``, or wrappers returned by
``@task`` / ``@scheduled``. Every execution path routes through
:func:`invoke_handler` so behaviour stays identical across the worker,
registry, and middleware pipeline.
"""

from __future__ import annotations

import inspect
from typing import Any


async def invoke_handler(handler: Any, /, *args: Any, **kwargs: Any) -> Any:
    """Call *handler* and await the result if it is awaitable.

    Supports plain functions, ``@task`` / ``@scheduled`` wrappers, and
    class-based tasks defining ``execute(self, ...)`` (instantiated per
    invocation and dispatched via ``instance.execute(*args, **kwargs)``).
    """
    target = handler if inspect.isclass(handler) else getattr(handler, "_func", handler)
    if inspect.isclass(target) and callable(getattr(target, "execute", None)):
        cls_target: Any = target
        instance = cls_target()
        outcome = instance.execute(*args, **kwargs)
    else:
        outcome = handler(*args, **kwargs)

    if inspect.isawaitable(outcome):
        return await outcome
    return outcome


__all__ = ["invoke_handler"]
