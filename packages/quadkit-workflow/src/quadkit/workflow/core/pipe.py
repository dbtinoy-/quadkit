"""Composable transformation pipe.

Provides a fluent, type-safe pipe for chaining transformation steps,
supporting both sync and async callables.

Example::

    from quadkit.workflow.core.pipe import TransformPipe

    result = await (
        TransformPipe[Request]()
        .pipe(validate)
        .pipe(transform)
        .pipe(persist)
        .execute(request)
    )
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    # imported only for type hints
    from collections.abc import Awaitable, Callable

T = TypeVar("T")
U = TypeVar("U")  # return type of next step


class TransformPipe(Generic[T]):
    """Composable transformation pipe.

    Each step in the pipe receives the output of the previous step
    and returns the (possibly transformed) value. Steps can be sync or
    async callables.

    The pipe is immutable — calling ``pipe`` returns a new
    ``TransformPipe`` instance with the added step.
    """

    __slots__ = ("_error_handler", "_steps")

    def __init__(
        self,
        steps: list[Callable[..., Any]] | None = None,
        error_handler: Callable[[Exception, Any], Any] | None = None,
    ) -> None:
        self._steps: list[Callable[..., Any]] = list(steps) if steps else []
        self._error_handler = error_handler

    def pipe(self, step: Callable[[T], U | Awaitable[U]]) -> TransformPipe[U]:
        """Add a transformation step to the pipe.

        The supplied *step* should accept the current value (of type
        ``T``) and return either a new value of type ``U`` or an awaitable
        producing ``U``.  The returned pipe has type ``TransformPipe[U]`` so
        that subsequent calls are type safe.

        Args:
            step: A callable (sync or async) that takes a value and
                returns the transformed value.

        Returns:
            A new ``TransformPipe`` with the step appended.
        """
        return TransformPipe([*self._steps, step], self._error_handler)

    def tap(self, side_effect: Callable[[T], Any]) -> TransformPipe[T]:
        """Add a side-effect step that observes but does not transform the value.

        The side-effect callable receives the current value. Its return
        value is ignored and the original value is forwarded unchanged.

        Args:
            side_effect: A callable (sync or async) for observation/logging.

        Returns:
            A new ``TransformPipe`` with the tap step appended.
        """

        async def _tap_step(value: Any, **kwargs: Any) -> Any:
            result = side_effect(value, **kwargs)
            if inspect.isawaitable(result):
                await result
            return value

        return TransformPipe([*self._steps, _tap_step], self._error_handler)

    def pipe_if(
        self,
        predicate: Callable[[T], bool],
        step: Callable[[T], U | Awaitable[U]],
    ) -> TransformPipe[U | T]:
        """Add a conditional transformation step.

        The step is only applied when *predicate(value)* returns ``True``.
        Otherwise the value passes through unchanged.

        Args:
            predicate: A callable that decides whether to apply *step*.
            step: The transformation to apply when the predicate holds.

        Returns:
            A new ``TransformPipe`` with the conditional step appended.
        """

        async def _conditional_step(value: Any, **kwargs: Any) -> Any:
            if predicate(value):
                result = step(value, **kwargs)
                if inspect.isawaitable(result):
                    return await result
                return result
            return value

        return TransformPipe([*self._steps, _conditional_step], self._error_handler)

    def catch(
        self,
        handler: Callable[[Exception, T], Any],
    ) -> TransformPipe[T]:
        """Set a raw exception recovery handler for the pipe.

        When any step raises and a handler is set, the handler receives
        ``(exception, last_value)`` and its return value becomes the pipe
        result, swallowing the exception.

        .. warning::
            ``catch()`` operates *outside* the ``Result`` pattern — it
            intercepts raw exceptions rather than returning
            ``Err(…)``.  Prefer designing pipe steps to return
            ``Result[T, E]`` and handling errors at the call-site via
            ``result.match()`` or ``result.and_then()`` (async) / ``result.and_then_sync()`` when possible.
            Use ``catch()`` only for coarse-grained last-resort recovery
            (e.g. logging and substituting a sentinel value) where
            propagating exceptions would crash the surrounding pipeline.

        Args:
            handler: A callable ``(exception, value) -> recovery_value``.

        Returns:
            A new ``TransformPipe`` with the error handler configured.
        """
        # copy list to preserve immutability
        return TransformPipe(list(self._steps), handler)

    async def execute(self, value: T, **kwargs: Any) -> T:
        """Execute the pipe by passing the value through all steps.

        Args:
            value: The initial input value.
            **kwargs: Additional keyword arguments forwarded to each step.

        Returns:
            The final transformed value.
        """
        for step in self._steps:
            try:
                result = step(value, **kwargs)
                if inspect.isawaitable(result):
                    value = await result
                else:
                    value = result
            except (
                Exception
            ) as exc:  # pipeline step can raise any exception; routed to error handler
                if self._error_handler is not None:
                    recovery = self._error_handler(exc, value)
                    if inspect.isawaitable(recovery):
                        value = await recovery
                    else:
                        value = recovery
                    break
                raise
        return value

    def __len__(self) -> int:
        """Return the number of steps in the pipe."""
        return len(self._steps)

    def __repr__(self) -> str:
        return f"TransformPipe(steps={len(self._steps)})"


__all__ = [
    "TransformPipe",
]
