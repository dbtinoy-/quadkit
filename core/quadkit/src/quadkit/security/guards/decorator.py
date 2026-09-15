"""Decorator applying a guard chain to async functions.

Provides :func:`use_guards`, which wires a sequence of guards into a
`GuardChainImpl` and checks them before every invocation of the decorated
async function.
"""

from __future__ import annotations

from collections.abc import Callable
import functools
import inspect
from typing import TYPE_CHECKING, Any, TypeVar

from quadkit.security.guards.chain import GuardChainImpl

if TYPE_CHECKING:
    from quadkit.contracts.web import GuardProtocol

F = TypeVar("F", bound=Callable[..., Any])


def use_guards(*guards: GuardProtocol) -> Callable[[F], F]:
    """Decorator to apply guards to an async method or function.

    Guards are checked before the decorated function is called. If any
    guard denies access, a :class:`~quadkit.contracts.exceptions.middleware.MiddlewareGuardError`
    is raised.

    The decorated function must be async and accept a ``context`` parameter
    (either as a positional argument or keyword argument) that will be
    passed to the guards.

    Example::

        from quadkit.security.guards import use_guards

        class AdminGuard:
            async def can_activate(self, context: dict[str, Any]) -> bool:
                return context.get("user", {}).get("is_admin", False)

        class UserService:
            @use_guards(AdminGuard())
            async def delete_user(self, user_id: str, context: dict[str, Any]) -> None:
                await self._delete(user_id)

    Args:
        *guards: GuardProtocol instances to apply.

    Returns:
        A decorator that wraps the async function with guard checks.

    Raises:
        TypeError: If the decorated function is not async.
    """
    chain = GuardChainImpl(list(guards))

    def decorator(func: F) -> F:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"@use_guards can only be applied to async functions, "
                f"got {type(func).__name__}"
            )

        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        has_context_param = "context" in param_names

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            context: dict[str, Any] | None = None
            if has_context_param:
                if "context" in kwargs:
                    context = kwargs.get("context")
                else:
                    context_idx = param_names.index("context")
                    if context_idx < len(args):
                        context = args[context_idx]

            if context is None:
                context = {}

            await chain.check_or_raise(context)
            return await func(*args, **kwargs)

        return async_wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["use_guards"]
