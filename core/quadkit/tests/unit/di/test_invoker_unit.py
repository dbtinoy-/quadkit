import pytest
from unittest.mock import AsyncMock, MagicMock
from quadkit.di.resolution.invoker import FunctionInvoker
from quadkit.contracts.core.di import ContainerResolverProtocol

@pytest.mark.asyncio
async def test_invoker_basic_injection():
    resolver = MagicMock(spec=ContainerResolverProtocol)
    resolver.resolve = AsyncMock(return_value="injected")
    
    invoker = FunctionInvoker(resolver)
    
    def my_func(injected: str):
        return injected
    
    result = await invoker.call(my_func)
    assert result == "injected"
    resolver.resolve.assert_called_once_with(str)

@pytest.mark.asyncio
async def test_invoker_with_args():
    resolver = MagicMock(spec=ContainerResolverProtocol)
    invoker = FunctionInvoker(resolver)
    
    def my_func(a: int, b: str):
        return f"{a}-{b}"
    
    result = await invoker.call(my_func, 1, b="2")
    assert result == "1-2"
    resolver.resolve.assert_not_called()

@pytest.mark.asyncio
async def test_invoker_async_func():
    resolver = MagicMock(spec=ContainerResolverProtocol)
    invoker = FunctionInvoker(resolver)
    
    async def my_func():
        return "async"
    
    result = await invoker.call(my_func)
    assert result == "async"
