from __future__ import annotations

"""Dependency injector for class instantiation with DI."""

import sys
from typing import TYPE_CHECKING, Any, Union, cast, get_args, get_origin

from quadkit.contracts.exceptions import (
    CircularDependencyError,
    UnresolvableDependencyError,
)
from quadkit.di.markers import Inject, Named, OptionalDep, Qualifier
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.protocols import DIResolverProtocol, TypeHintResolverProtocol


class DependencyInjector:
    """Handles dependency injection for class instantiation.

    Inspects constructor type hints, resolves dependencies from the
    container, and creates instances with all dependencies injected.

    This implementation is async-only; synchronous helpers such as
    ``instantiate_sync`` and lazy proxies have been removed.  Use
    ``await container.resolve(...)`` in all code paths.
    """

    def __init__(
        self,
        type_hint_resolver: TypeHintResolverProtocol,
        resolver: DIResolverProtocol | None = None,
    ) -> None:
        self._type_hint_resolver = type_hint_resolver
        self._resolver: DIResolverProtocol | None = resolver
        self._logger = get_logger(__name__)

    def set_resolver(self, resolver: DIResolverProtocol) -> None:
        """Set the service resolver.

        Called by Container.__init__ to close the circular reference
        between injector and resolver.
        """
        self._resolver = resolver

    async def instantiate(self, cls: type, force_inject: bool = False) -> Any:
        """Instantiate a class with dependency injection.

        Args:
            cls: The class to instantiate.
            force_inject: If True, inject even without ``__quadkit_inject__`` marker.

        Returns:
            An instance of ``cls`` with dependencies resolved.

        This method is async; callers must ``await`` the result.
        """
        if not force_inject and not getattr(cls, "__quadkit_inject__", False):
            return cls()

        kwargs: dict[str, Any] = {}
        params = self._type_hint_resolver.get_injectable_parameters(cls)

        for param_name, injectable_param in params.items():
            param_type = injectable_param.type_hint

            # Skip unresolvable type annotations
            if param_type is Any:
                continue

            # Resolve from container
            if param_type is not None:
                # 0. Unwrap Optional/Union if it's basically Optional[T]
                unwrapped_type = self._unwrap_optional(param_type)

                try:
                    # Handle markers
                    qualifier = injectable_param.qualifier

                    # (lazy injection removed)

                    # 2. Determine key (type or name-based)
                    key: Any = unwrapped_type
                    if isinstance(qualifier, Named):
                        key = (unwrapped_type, qualifier.name)
                    elif isinstance(qualifier, Qualifier):
                        key = qualifier.value
                    elif isinstance(qualifier, Inject) and qualifier.name:
                        key = qualifier.name

                    try:
                        kwargs[param_name] = await self._resolve(key)
                    except (UnresolvableDependencyError, RuntimeError):
                        # 3. Handle OptionalDep or Default fallbacks
                        if isinstance(qualifier, OptionalDep) or (
                            isinstance(qualifier, Inject)
                            and qualifier.default is not None
                        ):
                            kwargs[param_name] = qualifier.default
                        elif injectable_param.has_default:
                            kwargs[param_name] = injectable_param.parameter.default
                        else:
                            raise
                except CircularDependencyError:
                    raise
                except (
                    TypeError,
                    ValueError,
                    AttributeError,
                    RuntimeError,
                    LookupError,
                    UnresolvableDependencyError,
                ) as err:
                    # Final check for OptionalDep/Default before giving up
                    qualifier = injectable_param.qualifier
                    if isinstance(qualifier, OptionalDep):
                        kwargs[param_name] = qualifier.default
                        continue
                    if injectable_param.has_default:
                        kwargs[param_name] = injectable_param.parameter.default
                        continue

                    self._logger.exception(
                        "dependency_resolution_failed",
                        class_name=cls.__name__,
                        param_name=param_name,
                        param_type=str(param_type),
                        error_type=type(err).__name__,
                        error=str(err),
                    )
                    raise UnresolvableDependencyError(
                        dependency=str(param_type)
                    ) from err
            # If no type hint but has default, use it. Otherwise error.
            elif injectable_param.has_default:
                kwargs[param_name] = injectable_param.parameter.default
            else:
                raise UnresolvableDependencyError(dependency=param_name)

        try:
            return cls(**kwargs)
        except TypeError as exc:
            raise UnresolvableDependencyError(
                f"Cannot instantiate {cls.__name__}: {exc}",
            ) from exc

    async def _resolve(self, dep_type: Any) -> Any:
        """Resolve a dependency asynchronously."""
        if self._resolver is None:
            raise RuntimeError(
                "Async dependency resolution requires a resolver. "
                "Call set_resolver() first.",
            )
        return await self._resolver.resolve(dep_type)

    def _unwrap_optional(self, t: type) -> type:
        """Unwrap Optional[T] (Union[T, None] or T | None) to T."""
        origin = get_origin(t)
        # Check for typing.Union or types.UnionType (| syntax)
        is_union = origin is Union
        if not is_union and sys.version_info >= (3, 10):
            import types

            is_union = origin is types.UnionType

        if is_union:
            args = get_args(t)
            # Filter out NoneType
            filtered = [arg for arg in args if arg is not type(None)]
            if len(filtered) == 1:
                return cast("type", filtered[0])
        return t


__all__ = ["DependencyInjector"]
