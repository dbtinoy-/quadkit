"""Runnable composition contracts for G-01 parity.

Defines the core interfaces for composable runnable components (analogous to
LangChain's Runnable interface).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class RunnableConfigCallbacks:
    """Callbacks for runnable lifecycle events.

    Attributes:
        on_start: Called before runnable execution starts.
        on_end: Called after runnable execution completes.
        on_error: Called when runnable execution raises an error.
    """

    on_start: Callable[[Any], Any] | None = None
    on_end: Callable[[Any], Any] | None = None
    on_error: Callable[[Exception], Any] | None = None


@dataclass(frozen=True)
class RunnableConfig:
    """Configuration for runnable components.

    Attributes:
        timeout: Maximum execution time in seconds (default: 30).
        max_retries: Maximum retry attempts on failure (default: 3).
        callbacks: Lifecycle callbacks for the runnable.
    """

    timeout: int = 30
    max_retries: int = 3
    callbacks: RunnableConfigCallbacks | None = None


@runtime_checkable
class RunnableProtocol(Protocol):
    """Protocol for composable runnable components.

    Analogous to LangChain's Runnable interface. Implementations must provide
    both sync ``invoke`` and async ``ainvoke`` methods.
    """

    def invoke(self, input: Any) -> Any:
        """Synchronously process input.

        Args:
            input: Input to process.

        Returns:
            Processed output.
        """
        ...

    async def ainvoke(self, input: Any) -> Any:
        """Asynchronously process input.

        Args:
            input: Input to process.

        Returns:
            Processed output.
        """
        ...


class RunnablePipe:
    """Compose two runnables in sequence (like LangChain's pipe | operator).

    The output of the first runnable becomes the input to the second.
    """

    def __init__(self, first: RunnableProtocol, second: RunnableProtocol) -> None:
        self.first = first
        self.second = second

    def invoke(self, input: Any) -> Any:
        return self.second.invoke(self.first.invoke(input))

    async def ainvoke(self, input: Any) -> Any:
        return await self.second.ainvoke(await self.first.ainvoke(input))


class RunnableParallel:
    """Run multiple runnables concurrently (like LangChain's parallel Runnable).

    Each runnable receives the same input and results are returned as a dict.
    """

    def __init__(self, **runnables: RunnableProtocol) -> None:
        self.runnables = runnables

    def invoke(self, input: Any) -> dict[str, Any]:
        return {
            name: runnable.invoke(input) for name, runnable in self.runnables.items()
        }

    async def ainvoke(self, input: Any) -> dict[str, Any]:
        import asyncio

        results = await asyncio.gather(
            *(runnable.ainvoke(input) for runnable in self.runnables.values())
        )
        return dict(zip(self.runnables.keys(), results, strict=True))


class RunnableLambda:
    """Wrap a function as a runnable (like LangChain's RunnableLambda).

    Accepts either a sync or async function and wraps it to satisfy
    the RunnableProtocol interface.
    """

    def __init__(self, func: Callable[[Any], Any]) -> None:
        self.func = func

    def invoke(self, input: Any) -> Any:
        if asyncio.iscoroutinefunction(self.func):
            raise TypeError("Use ainvoke for async functions")
        return self.func(input)

    async def ainvoke(self, input: Any) -> Any:
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(input)
        return self.func(input)


class RunnableChain:
    """Chain multiple runnables with config support.

    Like LangChain's RunnableSequence, this chains multiple runnables
    together with optional configuration.
    """

    def __init__(
        self,
        steps: list[RunnableProtocol],
        config: RunnableConfig | None = None,
    ) -> None:
        self.steps = steps
        self.config = config or RunnableConfig()

    def invoke(self, input: Any) -> Any:
        result = input
        for step in self.steps:
            result = step.invoke(result)
        return result

    async def ainvoke(self, input: Any) -> Any:
        result = input
        for step in self.steps:
            result = await step.ainvoke(result)
        return result


class RunnableMap:
    """Map input through transforms (like LangChain's RunnableMap).

    Accepts either a single transform function or a dict of named transforms.
    """

    def __init__(
        self,
        func_or_funcs: Callable[[Any], Any] | dict[str, Callable[[Any], Any]],
    ) -> None:
        if isinstance(func_or_funcs, dict):
            self.funcs: dict[str, Callable[[Any], Any]] = func_or_funcs
            self.single_func: Callable[[Any], Any] | None = None
        else:
            self.single_func = func_or_funcs
            self.funcs = {}

    def invoke(self, input: Any) -> Any:
        if self.funcs:
            return {name: func(input) for name, func in self.funcs.items()}
        if self.single_func is not None:
            return self.single_func(input)
        return input

    async def ainvoke(self, input: Any) -> Any:
        if self.funcs:
            results = await asyncio.gather(
                *(func(input) for func in self.funcs.values())
            )
            return dict(zip(self.funcs.keys(), results, strict=True))
        if self.single_func is not None:
            if asyncio.iscoroutinefunction(self.single_func):
                return await self.single_func(input)
            return self.single_func(input)
        return input


class RunnableGenerator:
    """Wrap a generator function for streaming (like LangChain's RunnableGenerator).

    Yields chunks for streaming responses.
    """

    def __init__(self, generator_func: Callable[[Any], Any]) -> None:
        self.generator_func = generator_func

    def invoke(self, input: Any) -> list[Any]:
        if asyncio.iscoroutinefunction(self.generator_func):
            raise TypeError("Use ainvoke for async generators")
        return list(self.generator_func(input))

    async def ainvoke(self, input: Any) -> list[Any]:
        import inspect

        gen = self.generator_func(input)
        if inspect.isasyncgenfunction(self.generator_func) or inspect.isasyncgen(gen):
            result = []
            async for chunk in gen:
                result.append(chunk)
            return result
        if asyncio.iscoroutinefunction(self.generator_func):
            return [await self.generator_func(input)]
        return list(gen)


class RunnableWithRetry:
    """Wrap a runnable with retry logic.

    Retries on failure up to max_retries times.
    """

    def __init__(
        self,
        func: Callable[[Any], Any],
        max_retries: int = 3,
    ) -> None:
        self.func = func
        self.max_retries = max_retries

    def invoke(self, input: Any) -> Any:
        last_error: Exception | None = None
        for _attempt in range(self.max_retries):
            try:
                return self.func(input)
            except Exception as e:
                last_error = e
        if last_error is not None:
            raise last_error
        return input

    async def ainvoke(self, input: Any) -> Any:
        last_error: Exception | None = None
        for _attempt in range(self.max_retries):
            try:
                if asyncio.iscoroutinefunction(self.func):
                    return await self.func(input)
                return self.func(input)
            except Exception as e:
                last_error = e
        if last_error is not None:
            raise last_error
        return input


__all__ = [
    "RunnableChain",
    "RunnableConfig",
    "RunnableConfigCallbacks",
    "RunnableGenerator",
    "RunnableLambda",
    "RunnableMap",
    "RunnableParallel",
    "RunnablePipe",
    "RunnableProtocol",
    "RunnableWithRetry",
]
