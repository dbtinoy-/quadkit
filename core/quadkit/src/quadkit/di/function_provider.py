"""Function-based provider — compact alternative to Provider subclasses.

Enables declaring providers as simple factory functions whose return type
annotation determines the contract type and whose parameters are resolved
from the DI container::

    from quadkit.di import provide

    @provide
    def cache_backend(config: AppConfig) -> CacheBackendProtocol:
        return RedisCacheBackend(config.redis_url)

    @provide(scope="singleton")
    def payment_gateway(config: BillingConfig) -> PaymentGateway:
        return StripeGateway(config.api_key)

The decorated function becomes a :class:`Provider` subclass that can be
used in module ``providers=`` lists just like any other provider.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, get_type_hints, overload

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.contracts.exceptions.container import DependencyError
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class FunctionProvider(Provider):
    """Provider that wraps a factory function.

    The function's return type annotation determines the contract type
    registered in the container.  Parameters are resolved from the
    container during ``boot()``.
    """

    def __init__(
        self,
        factory: Callable[..., Any],
        contract_type: type,
        scope: ServiceScope = ServiceScope.SINGLETON,
        provider_name: str | None = None,
    ) -> None:
        """Initialize the function provider.

        Args:
            factory: The factory function to wrap.
            contract_type: The type to register the return value as.
            scope: Service scope for registration.
            provider_name: Optional provider name.
        """
        resolved_name = provider_name or factory.__name__
        super().__init__(name=resolved_name)
        self._factory = factory
        self._contract_type = contract_type
        self._scope = scope

    async def register(self, container: Any) -> None:
        """Register a placeholder — actual binding happens in boot()."""

    async def boot(self, container: Any) -> None:
        """Resolve factory parameters from the container and register the result."""
        hints = get_type_hints(self._factory)
        hints.pop("return", None)
        sig = inspect.signature(self._factory)

        kwargs: dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            param_type = hints.get(param_name)
            if param_type is not None:
                try:
                    kwargs[param_name] = await container.resolve(param_type)
                except DependencyError:
                    if param.default is not inspect.Parameter.empty:
                        kwargs[param_name] = param.default
                    else:
                        raise
                except (TypeError, AttributeError) as e:
                    logger.debug(
                        "function_provider.resolution_error",
                        param=param_name,
                        error=str(e),
                    )
                    if param.default is not inspect.Parameter.empty:
                        kwargs[param_name] = param.default
                    else:
                        raise
            elif param.default is not inspect.Parameter.empty:
                kwargs[param_name] = param.default

        result = self._factory(**kwargs)
        if inspect.isawaitable(result):
            result = await result

        if self._scope == ServiceScope.SINGLETON:
            container.singleton(self._contract_type, result)
        elif self._scope == ServiceScope.SCOPED:
            container.scoped(self._contract_type, lambda: result)
        else:
            container.transient(self._contract_type, lambda: result)


@overload
def provide(func: Callable[..., Any]) -> type[FunctionProvider]: ...


@overload
def provide(
    *,
    scope: ServiceScope | str = ServiceScope.SINGLETON,
    name: str | None = None,
) -> Callable[[Callable[..., Any]], type[FunctionProvider]]: ...


def provide(
    func: Callable[..., Any] | None = None,
    *,
    scope: ServiceScope | str = ServiceScope.SINGLETON,
    name: str | None = None,
) -> type[FunctionProvider] | Callable[[Callable[..., Any]], type[FunctionProvider]]:
    """Decorator to create a Provider from a factory function.

    The function's return type annotation determines the contract type
    registered in the container.  Parameters are resolved from the
    container during boot.

    Can be used bare or with arguments::

        @provide
        def cache(config: AppConfig) -> CacheBackendProtocol:
            return RedisCacheBackend(config.redis_url)

        @provide(scope="singleton", name="billing_gateway")
        def gateway(config: BillingConfig) -> PaymentGateway:
            return StripeGateway(config.api_key)

    Args:
        func: The factory function (when used as bare decorator).
        scope: Service scope — ``"singleton"``, ``"scoped"``, or ``"transient"``.
        name: Optional provider name.

    Returns:
        A Provider subclass (not instance) that can be used in module
        ``providers=`` lists.
    """
    if isinstance(scope, str):
        scope = ServiceScope(scope)

    def decorator(factory: Callable[..., Any]) -> type[FunctionProvider]:
        hints = get_type_hints(factory)
        return_type = hints.get("return")
        if return_type is None:
            raise TypeError(
                f"@provide decorated function '{factory.__name__}' must have "
                f"a return type annotation to determine the contract type.",
            )

        captured_factory = factory
        captured_type = return_type
        captured_scope = scope
        captured_name = name

        # Create a unique Provider subclass per decorated function
        cls = type(
            f"_FunctionProvider_{factory.__name__}",
            (FunctionProvider,),
            {},
        )

        def __init__(self: Any) -> None:  # noqa: N807
            FunctionProvider.__init__(
                self,
                factory=captured_factory,
                contract_type=captured_type,
                scope=captured_scope,
                provider_name=captured_name,
            )

        cls.__init__ = __init__  # type: ignore[misc]
        cls.__qualname__ = f"provide.{factory.__name__}"
        cls.__module__ = factory.__module__

        return cls

    if func is not None:
        return decorator(func)
    return decorator


__all__ = ["FunctionProvider", "provide"]
