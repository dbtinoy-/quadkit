"""First-class base class for class-based scheduled and background tasks."""

from __future__ import annotations

import inspect
from typing import Any


class ScheduledTask:
    """Base class for class-based tasks executed by ``TaskWorker``.

    Subclasses define an ``async def execute(self, ...)`` method declaring
    typed DI dependencies directly as parameters::

        @scheduled(cron="0 3 * * *", name="calculate-affinities")
        class AffinityCalculationTask(ScheduledTask):
            async def execute(
                self,
                db: DatabaseProviderProtocol,
                cache: CacheBackendProtocol,
            ) -> None:
                ...

    ``ScheduledTask`` validates ``execute`` at class creation time via
    ``__init_subclass__`` rather than declaring an untyped ``**kwargs``
    method signature, allowing subclasses to declare strict typed DI
    parameters without Liskov ``# type: ignore[override]`` pragmas.
    """

    def __init_subclass__(cls, *, abstract: bool = False, **kwargs: Any) -> None:
        """Validate concrete subclasses define an async ``execute`` coroutine."""
        super().__init_subclass__(**kwargs)
        if abstract or inspect.isabstract(cls):
            return

        execute_fn = getattr(cls, "execute", None)
        if execute_fn is None or not callable(execute_fn):
            raise TypeError(
                f"{cls.__name__} must define an async 'execute(self, ...)' method"
            )
        if not inspect.iscoroutinefunction(execute_fn):
            raise TypeError(f"{cls.__name__}.execute must be an async coroutine method")


__all__ = ["ScheduledTask"]
