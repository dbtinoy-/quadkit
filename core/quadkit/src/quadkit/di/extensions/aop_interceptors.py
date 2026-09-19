"""AOP (Aspect-Oriented Programming) interceptor pattern for Quadkit Framework.

Provides method-level interception via proxy objects.  Interceptors
operate at the Python method call level and are not coupled to HTTP.

Typical uses: audit logging, distributed tracing, caching decorators,
retry logic on domain service methods, metrics collection.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
import inspect
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast

from quadkit.primitives.registry import Registry

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

T = TypeVar("T")


class MethodInterceptorProtocol(Protocol):
    """Protocol for interceptor implementations."""

    async def intercept(
        self,
        invocation: MethodInvocation,
        next_interceptor: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Intercept a method invocation."""
        ...


class MethodInvocation:
    """Represents a method invocation that can be intercepted."""

    def __init__(
        self,
        target: Any,
        method_name: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        method: Callable[..., Any],
    ) -> None:
        self.target = target
        self.method_name = method_name
        self.args = args
        self.kwargs = kwargs
        self.method = method
        self.result: Any = None
        self.exception: Exception | None = None

    @property
    def signature(self) -> str:
        """Get the method signature."""
        return f"{self.target.__class__.__name__}.{self.method_name}"

    def proceed(self) -> Any:
        """Proceed with the method invocation."""
        return self.method(*self.args, **self.kwargs)


class InterceptorTimeoutError(RuntimeError):
    """Raised when a ``MethodInterceptorProtocol`` exceeds its configured timeout."""

    _code: str = "QK_ERR_DI_011"

    def __init__(
        self,
        interceptor: MethodInterceptorProtocol,
        method_signature: str,
        timeout_seconds: float | None,
    ) -> None:
        self.interceptor = interceptor
        self.method_signature = method_signature
        self.timeout_seconds = timeout_seconds
        interceptor_name = type(interceptor).__name__
        super().__init__(
            f"Interceptor '{interceptor_name}' timed out after {timeout_seconds}s "
            f"while processing '{method_signature}'."
        )


class AOPInterceptorChain:
    """Chain of AOP interceptors for proxy-based interception."""

    def __init__(self, interceptors: list[MethodInterceptorProtocol]) -> None:
        self.interceptors = interceptors
        self.current_index = 0

    async def proceed(self, invocation: MethodInvocation) -> Any:
        """Execute the next interceptor in the chain."""
        if self.current_index >= len(self.interceptors):
            result = invocation.method(*invocation.args, **invocation.kwargs)
            if inspect.isawaitable(result):
                return await result
            return result

        interceptor = self.interceptors[self.current_index]
        self.current_index += 1

        async def next_interceptor() -> Any:
            return await self.proceed(invocation)

        timeout_seconds: float | None = getattr(interceptor, "timeout_seconds", None)
        try:
            if timeout_seconds is not None:
                async with asyncio.timeout(timeout_seconds):
                    return await interceptor.intercept(invocation, next_interceptor)
            else:
                return await interceptor.intercept(invocation, next_interceptor)
        except TimeoutError as exc:
            raise InterceptorTimeoutError(
                interceptor=interceptor,
                method_signature=invocation.signature,
                timeout_seconds=timeout_seconds,
            ) from exc


class MethodInterceptorRegistry(Registry[str, list[MethodInterceptorProtocol]]):
    """Registry for managing interceptors."""

    def __init__(self) -> None:
        super().__init__(name="interceptors")
        self._global_interceptors: list[MethodInterceptorProtocol] = []

    def register_interceptor(
        self,
        interceptor: MethodInterceptorProtocol,
        method_pattern: str | None = None,
    ) -> None:
        """Register an interceptor for specific methods or globally."""
        if method_pattern is None:
            self._global_interceptors.append(interceptor)
        else:
            if method_pattern not in self._items:
                self._items[method_pattern] = []
            self._items[method_pattern].append(interceptor)

    def get_interceptors_for_method(
        self, method_signature: str
    ) -> list[MethodInterceptorProtocol]:
        """Get all interceptors that should be applied to a method."""
        interceptors = list(self._global_interceptors)
        for pattern, pattern_interceptors in self._items.items():
            if self._matches_pattern(method_signature, pattern):
                interceptors.extend(pattern_interceptors)
        return interceptors

    def _matches_pattern(self, method_signature: str, pattern: str) -> bool:
        """Check if a method signature matches a pattern."""
        return pattern in method_signature


class ProxyFactory:
    """Factory for creating proxy objects with interception."""

    def __init__(self, registry: MethodInterceptorRegistry) -> None:
        self.registry = registry
        self._proxy_cache: dict[int, Any] = {}

    def create_proxy(self, target: T, interface: type[T]) -> T:
        """Create a proxy for the target object."""
        target_id = id(target)
        if target_id not in self._proxy_cache:
            self._proxy_cache[target_id] = Proxy(target, interface, self.registry)
        return cast("T", self._proxy_cache[target_id])


class Proxy:
    """Proxy class that intercepts method calls."""

    def __init__(
        self,
        target: Any,
        interface: type,
        registry: MethodInterceptorRegistry,
    ) -> None:
        self._target = target
        self._interface = interface
        self._registry = registry
        self._method_cache: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        """Intercept attribute access with method caching."""
        if name in self._method_cache:
            return self._method_cache[name]

        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        method_signature = f"{self._interface.__name__}.{name}"
        interceptors = self._registry.get_interceptors_for_method(method_signature)

        meta = getattr(attr, "_quadkit_interceptors", None)
        if meta:
            for interceptor_cls in cast("list[type[MethodInterceptorProtocol]]", meta):
                interceptors.append(interceptor_cls())

        if not interceptors:
            self._method_cache[name] = attr
            return attr

        intercepted = self._create_intercepted_method(attr, name, interceptors)
        self._method_cache[name] = intercepted
        return intercepted

    def _create_intercepted_method(
        self,
        method: Callable[..., Any],
        method_name: str,
        interceptors: list[MethodInterceptorProtocol],
    ) -> Callable[..., Any]:
        """Create an intercepted version of a method."""

        async def intercepted_method(*args: Any, **kwargs: Any) -> Any:
            invocation = MethodInvocation(
                target=self._target,
                method_name=method_name,
                args=args,
                kwargs=kwargs,
                method=method,
            )
            chain = AOPInterceptorChain(interceptors)
            try:
                result = await chain.proceed(invocation)
                invocation.result = result
            except (
                RuntimeError,
                TypeError,
                ValueError,
                AttributeError,
                TimeoutError,
            ) as e:
                invocation.exception = e
                raise
            else:
                return result

        return intercepted_method


# Context var for registry, managed by DI
_current_registry: ContextVar[MethodInterceptorRegistry | None] = ContextVar(
    "interceptor_registry",
)


class MethodInterceptorRegistryManager:
    """Registry for managing interceptor state and instances."""

    def __init__(self) -> None:
        self._registry: MethodInterceptorRegistry | None = None

    def get_registry(self) -> MethodInterceptorRegistry:
        """Get or create the interceptor registry instance."""
        if self._registry is None:
            self._registry = MethodInterceptorRegistry()
        return self._registry

    def set_current_registry(self, registry: MethodInterceptorRegistry) -> None:
        """Set the current registry in context."""
        _current_registry.set(registry)

    def get_current_registry(self) -> MethodInterceptorRegistry | None:
        """Get the current registry from context, falling back to stored instance."""
        registry = _current_registry.get(None)
        if registry is None and self._registry:
            registry = self._registry
            _current_registry.set(registry)
        return registry


def get_interceptor_registry() -> MethodInterceptorRegistry:
    """Get the AOP interceptor registry from the current context."""
    registry = _current_registry.get(None)
    if registry is not None:
        return registry
    return MethodInterceptorRegistry()
