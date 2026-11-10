"""Read-only async resolution shared by root containers and request scopes."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, overload, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class AsyncResolverProtocol(Protocol):
    """Resolve services without requiring registration or synchronous helpers.

    A request scope must not need root-only mutation methods merely to resolve
    a response factory. Rich root resolvers satisfy this protocol structurally.
    """

    @overload
    async def resolve(self, service_type: type[T]) -> T: ...

    @overload
    async def resolve(self, service_type: Any) -> Any: ...

    async def resolve(self, service_type: Any) -> Any: ...

    @overload
    async def resolve_optional(self, service_type: type[T]) -> T | None: ...

    @overload
    async def resolve_optional(self, service_type: Any) -> Any | None: ...

    async def resolve_optional(self, service_type: Any) -> Any | None: ...


__all__ = ["AsyncResolverProtocol"]
