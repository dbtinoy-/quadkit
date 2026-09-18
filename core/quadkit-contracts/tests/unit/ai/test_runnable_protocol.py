"""Tests for Runnable composition contracts (G-01 parity)."""
from __future__ import annotations

import pytest

from quadkit.contracts.ai.exceptions import AIError, RunnableError


def test_runnable_error_subclasses_ai_error():
    """RunnableError must inherit from AIError."""
    assert issubclass(RunnableError, AIError)


def test_runnable_error_carries_message():
    """RunnableError should carry a message."""
    err = RunnableError("pipe stage 'parser' failed")
    assert "pipe stage 'parser' failed" in str(err)

def test_runnable_config_defaults():
    """RunnableConfig should have sensible defaults."""
    from quadkit.contracts.ai.runnable import RunnableConfig
    config = RunnableConfig()
    assert config.timeout == 30
    assert config.max_retries == 3


def test_runnable_config_explicit_values():
    """RunnableConfig should accept explicit values."""
    from quadkit.contracts.ai.runnable import RunnableConfig
    config = RunnableConfig(timeout=60, max_retries=5)
    assert config.timeout == 60
    assert config.max_retries == 5


def test_runnable_protocol_has_invoke():
    """RunnableProtocol must define invoke method."""
    from quadkit.contracts.ai.runnable import RunnableProtocol
    assert hasattr(RunnableProtocol, 'invoke')


def test_runnable_protocol_has_ainvoke():
    """RunnableProtocol must define ainvoke async method."""
    from quadkit.contracts.ai.runnable import RunnableProtocol
    assert hasattr(RunnableProtocol, 'ainvoke')


def test_concrete_runnable_satisfies_protocol():
    """Concrete implementations should satisfy RunnableProtocol."""
    from quadkit.contracts.ai.runnable import RunnableProtocol
    
    class ConcreteRunnable:
        def invoke(self, input: Any) -> Any:
            return f"processed: {input}"
        
        async def ainvoke(self, input: Any) -> Any:
            return f"async processed: {input}"
    
    runnable = ConcreteRunnable()
    assert isinstance(runnable, RunnableProtocol)


def test_runnable_pipe_composes_two_runables():
    """RunnablePipe should compose two runnables in sequence."""
    from quadkit.contracts.ai.runnable import RunnableProtocol, RunnablePipe
    
    class AddSuffix:
        def invoke(self, input: Any) -> Any:
            return f"{input}_suffix"
        
        async def ainvoke(self, input: Any) -> Any:
            return f"{input}_suffix"
    
    class Uppercase:
        def invoke(self, input: Any) -> Any:
            return input.upper()
        
        async def ainvoke(self, input: Any) -> Any:
            return input.upper()
    
    pipe = RunnablePipe(AddSuffix(), Uppercase())
    result = pipe.invoke("hello")
    assert result == "HELLO_SUFFIX"


def test_runnable_pipe_ainvoke():
    """RunnablePipe should support async invocation."""
    from quadkit.contracts.ai.runnable import RunnableProtocol, RunnablePipe
    
    class Double:
        def invoke(self, input: Any) -> Any:
            return input * 2
        
        async def ainvoke(self, input: Any) -> Any:
            return input * 2
    
    pipe = RunnablePipe(Double(), Double())
    result = pipe.ainvoke(5)
    import asyncio
    assert asyncio.run(result) == 20


def test_runnable_parallel_runs_in_parallel():
    """RunnableParallel should run runnables concurrently."""
    from quadkit.contracts.ai.runnable import RunnableProtocol, RunnableParallel
    # This test would verify parallel execution
    # For now, just test the protocol exists
    assert RunnableParallel is not None


def test_runnable_lambda_wraps_sync_function():
    """RunnableLambda should wrap a sync function."""
    from quadkit.contracts.ai.runnable import RunnableLambda
    
    def double(x: int) -> int:
        return x * 2
    
    rl = RunnableLambda(double)
    assert rl.invoke(5) == 10


def test_runnable_lambda_wraps_async_function():
    """RunnableLambda should wrap an async function."""
    from quadkit.contracts.ai.runnable import RunnableLambda
    
    async def async_double(x: int) -> int:
        return x * 2
    
    rl = RunnableLambda(async_double)
    import asyncio
    result = asyncio.run(rl.ainvoke(5))
    assert result == 10


def test_runnable_chain_with_config():
    """RunnableChain should accept config and pass to runnables."""
    from quadkit.contracts.ai.runnable import RunnableChain, RunnableConfig
    
    class AddOne:
        def invoke(self, input: int) -> int:
            return input + 1
        async def ainvoke(self, input: int) -> int:
            return input + 1
    
    config = RunnableConfig(timeout=60, max_retries=5)
    chain = RunnableChain([AddOne(), AddOne()], config=config)
    assert chain.config.timeout == 60
    assert chain.invoke(0) == 2


def test_runnable_chain_invoke():
    """RunnableChain should invoke steps in sequence."""
    from quadkit.contracts.ai.runnable import RunnableChain
    
    class AddOne:
        def invoke(self, input: int) -> int:
            return input + 1
        async def ainvoke(self, input: int) -> int:
            return input + 1
    
    chain = RunnableChain([AddOne(), AddOne(), AddOne()])
    assert chain.invoke(0) == 3


def test_runnable_map_transforms_input():
    """RunnableMap should transform input with a function."""
    from quadkit.contracts.ai.runnable import RunnableMap
    
    mapper = RunnableMap(lambda x: x * 2)
    assert mapper.invoke(5) == 10


def test_runnable_map_with_dict():
    """RunnableMap should accept dict of functions."""
    from quadkit.contracts.ai.runnable import RunnableMap
    
    mapper = RunnableMap({"double": lambda x: x * 2, "triple": lambda x: x * 3})
    result = mapper.invoke(5)
    assert result["double"] == 10
    assert result["triple"] == 15


def test_runnable_generator_yields_chunks():
    """RunnableGenerator should yield chunks for streaming."""
    from quadkit.contracts.ai.runnable import RunnableGenerator
    
    def gen(text: str):
        for char in text:
            yield char
    
    rg = RunnableGenerator(gen)
    result = list(rg.invoke("abc"))
    assert result == ["a", "b", "c"]


def test_runnable_generator_async():
    """RunnableGenerator should support async generators."""
    from quadkit.contracts.ai.runnable import RunnableGenerator
    
    async def agen(text: str):
        for char in text:
            yield char
    
    rg = RunnableGenerator(agen)
    import asyncio
    result = asyncio.run(rg.ainvoke("abc"))
    assert result == ["a", "b", "c"]


def test_runnable_config_with_callbacks():
    """RunnableConfig should support callbacks."""
    from quadkit.contracts.ai.runnable import RunnableConfig, RunnableConfigCallbacks
    
    cb = RunnableConfigCallbacks(
        on_start=lambda input: {"started": True},
        on_end=lambda output: {"completed": True},
    )
    config = RunnableConfig(callbacks=cb)
    assert config.callbacks is not None
    assert config.callbacks.on_start is not None


def test_runnable_with_retry():
    """Runnable should support retry on failure."""
    from quadkit.contracts.ai.runnable import RunnableWithRetry
    
    call_count = 0
    def failing_func(x):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("fail")
        return x * 2
    
    rwr = RunnableWithRetry(failing_func, max_retries=3)
    assert rwr.invoke(5) == 10
    assert call_count == 3
