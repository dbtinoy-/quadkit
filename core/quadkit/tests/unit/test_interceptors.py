from typing import Any

import pytest

from quadkit.di.container import Container


class AddOneInterceptor:
    async def intercept(self, invocation: Any, next_handler: Any) -> Any:
        # call next then add one to result
        result = await next_handler()
        return result + 1


class MultiplyInterceptor:
    async def intercept(self, invocation: Any, next_handler: Any) -> Any:
        result = await next_handler()
        return result * 2


class MyService:
    async def compute(self, x: int) -> int:
        return x


@pytest.mark.asyncio
async def test_interceptors_are_applied_to_resolved_instance():
    container = Container()
    # register the service so it can be resolved
    container.transient(MyService, MyService)

    # register interceptors: global then type-specific
    container.interceptor_registry.add_global(AddOneInterceptor())
    container.interceptor_registry.add_for_type(MyService, MultiplyInterceptor())

    svc = await container.resolve(MyService)
    # global AddOne is outermost, type-specific Multiply runs first
    # computation = (3 * 2) + 1 == 7
    assert await svc.compute(3) == 7

    # subsequent calls still work and order remains consistent.  For x=0 the
    # inner Multiply returns 0 then outer AddOne adds one.
    assert await svc.compute(0) == 1


@pytest.mark.asyncio
async def test_no_interceptors_returns_raw_instance():
    container = Container()
    container.transient(MyService, MyService)
    svc = await container.resolve(MyService)
    assert isinstance(svc, MyService)
    assert await svc.compute(5) == 5
