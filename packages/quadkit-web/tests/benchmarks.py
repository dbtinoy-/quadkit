"""Performance benchmarks for quadkit-web.

Benchmarks for request throughput, DI resolution, and middleware stack.
"""

from __future__ import annotations

import time
from typing import Any


async def benchmark_request_throughput(
    app_factory: Any,
    num_requests: int = 1000,
) -> dict[str, float]:
    """Benchmark empty handler throughput.

    Returns:
        dict with 'requests_per_second', 'avg_latency_ms', 'total_time_s'
    """
    # Create a minimal app
    from quadkit.web.di.provider import WebProvider

    provider = WebProvider()
    await provider.boot()

    # Import test client
    from quadkit.testing.clients.web import WebTestClient

    client = WebTestClient(provider.starlette)

    start = time.perf_counter()

    for _ in range(num_requests):
        await client.get("/health")

    end = time.perf_counter()
    total_time = end - start

    return {
        "requests_per_second": num_requests / total_time,
        "avg_latency_ms": (total_time / num_requests) * 1000,
        "total_time_s": total_time,
    }


async def benchmark_di_resolution(
    container_factory: Any,
    num_resolutions: int = 1000,
) -> dict[str, float]:
    """Benchmark DI container resolution.

    Returns:
        dict with 'resolutions_per_second', 'avg_latency_ms'
    """
    container = container_factory()

    # Register a service
    class DummyService:
        pass

    container.singleton(DummyService, DummyService)

    start = time.perf_counter()

    for _ in range(num_resolutions):
        await container.resolve(DummyService)

    end = time.perf_counter()
    total_time = end - start

    return {
        "resolutions_per_second": num_resolutions / total_time,
        "avg_latency_ms": (total_time / num_resolutions) * 1000,
    }


async def benchmark_middleware_stack(
    num_middleware: int = 10,
    num_requests: int = 1000,
) -> dict[str, float]:
    """Benchmark middleware stack overhead.

    Returns:
        dict with 'requests_per_second', 'overhead_ms'
    """
    from starlette.applications import Starlette
    from starlette.routing import Route
    from testing import WebTestClient

    # Create a simple endpoint
    async def homepage(request):
        return {"status": "ok"}

    # Build middleware stack
    middleware = []
    for _i in range(num_middleware):

        class Middleware:
            def __init__(self, app):
                self.app = app

            async def __call__(self, scope, receive, send):
                await self.app(scope, receive, send)

        middleware.append(Middleware)

    # Create app
    app = Starlette(
        routes=[Route("/", homepage)],
        middleware=middleware,
    )

    client = WebTestClient(app)

    start = time.perf_counter()

    for _ in range(num_requests):
        await client.get("/")

    end = time.perf_counter()
    total_time = end - start

    return {
        "requests_per_second": num_requests / total_time,
        "avg_latency_ms": (total_time / num_requests) * 1000,
        "middleware_count": num_middleware,
    }


async def run_all_benchmarks() -> dict[str, Any]:
    """Run all benchmarks and return results."""
    results = {}

    # Middleware benchmarks
    for count in [1, 5, 10, 20]:
        results[f"middleware_{count}"] = await benchmark_middleware_stack(count, 500)

    return results


__all__ = [
    "benchmark_di_resolution",
    "benchmark_middleware_stack",
    "benchmark_request_throughput",
    "run_all_benchmarks",
]
