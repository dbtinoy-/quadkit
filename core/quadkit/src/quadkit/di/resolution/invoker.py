"""Function invocation with dependency injection."""

from __future__ import annotations

import inspect
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    get_args,
    get_origin,
    get_type_hints,
)

from quadkit.contracts.exceptions import UnresolvableDependencyError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.contracts.core.di import ContainerResolverProtocol
    from quadkit.di.extensions.strategies import ResolutionStrategy
    from quadkit.di.resolution.type_hints import BoundedCache


class FunctionInvoker:
    """Invokes functions by resolving their parameters from a container.

    Decouples reflection-based call logic from the main Container class.
    """

    def __init__(
        self,
        resolver: ContainerResolverProtocol,
        hints_cache: BoundedCache | None = None,
    ) -> None:
        self._resolver = resolver
        self._hints_cache = hints_cache

    async def call(
        self,
        func: Callable[..., Awaitable[Any] | Any],
        *args: Any,
        strategies: list[ResolutionStrategy] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Call a function with automatic dependency injection."""
        if self._hints_cache is not None and func in self._hints_cache:
            sig, hints = self._hints_cache[func]
        else:
            sig = inspect.signature(func)
            hints = get_type_hints(func, include_extras=True)
            if self._hints_cache is not None:
                self._hints_cache[func] = (sig, hints)

        bound = sig.bind_partial(*args, **kwargs)
        provided = set(bound.arguments.keys())
        resolved_kwargs = dict(kwargs)
        strategies = strategies or []

        for name, param in sig.parameters.items():
            if name in provided:
                continue
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            param_type = hints.get(name)
            has_default = param.default is not inspect.Parameter.empty

            # Unwrap Annotated[T, ...] to get the base type
            base_type = param_type
            if param_type is not None and get_origin(param_type) is Annotated:
                ann_args = get_args(param_type)
                if ann_args:
                    base_type = ann_args[0]

            # Try strategies first (web params, etc.)
            if param_type is not None:
                for strategy in strategies:
                    found, value = await strategy.resolve(
                        name,
                        base_type,
                        param.default,
                    )
                    if found:
                        resolved_kwargs[name] = value
                        break

                if name in resolved_kwargs:
                    continue

            # Try container resolution
            if base_type is not None:
                try:
                    resolved_kwargs[name] = await self._resolver.resolve(base_type)
                    continue
                except (UnresolvableDependencyError, RuntimeError):
                    pass

            # Fall back to default
            if has_default:
                continue

            raise UnresolvableDependencyError(
                f"Cannot resolve parameter {name!r} "
                f"(type: {param_type}) for {func.__qualname__}. "
                f"Not provided, not in container, no default value.",
            )

        from quadkit.di.resolution.context import current_resolver_var

        token = current_resolver_var.set(self._resolver)
        try:
            result = func(*args, **resolved_kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        finally:
            current_resolver_var.reset(token)


__all__ = ["FunctionInvoker"]
