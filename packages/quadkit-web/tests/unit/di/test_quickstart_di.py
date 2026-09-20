"""Tests for quickstart @singleton / @injectable DI decorators.

Covers:
- ``@singleton`` decorated class is resolved from the container in a route handler
- ``@singleton`` returns the **same instance** on each resolve (shared state)
- ``@injectable`` returns a **new instance** each resolve (transient scope)
- Both decorators are importable from ``quadkit.web``

Each test creates a fresh :class:`~quadkit.web.quickstart._QuickstartApp`
instance and patches ``_collect_script_services`` with only the classes
relevant to that test to prevent cross-test DI pollution.
"""

# NOTE: Do NOT add ``from __future__ import annotations`` here.
# The _wrap_script_handler inspects annotation objects at runtime via
# ``inspect.signature``; postponed evaluation (PEP 563) turns them into
# strings, breaking the type-based injection lookup.

from httpx import ASGITransport, AsyncClient
import pytest

from quadkit.web.quickstart import _PendingRoute, _QuickstartApp

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _boot(app: _QuickstartApp) -> AsyncClient:
    """Boot *app* and return an ``AsyncClient`` wrapping its Starlette backend.

    Args:
        app: A freshly created, not-yet-booted ``_QuickstartApp`` instance.

    Returns:
        An :class:`httpx.AsyncClient` targeting the underlying Starlette app.
    """
    await app._ensure_booted()
    return AsyncClient(
        transport=ASGITransport(app=app._starlette),
        base_url="http://test",
    )


# ---------------------------------------------------------------------------
# Test 1 — importable from quadkit.web
# ---------------------------------------------------------------------------


def test_singleton_and_injectable_importable_from_quadkit_web() -> None:
    """Both decorators can be imported directly from ``quadkit.web``."""
    from quadkit.web import injectable, singleton  # noqa: F401

    assert callable(singleton)
    assert callable(injectable)


# ---------------------------------------------------------------------------
# Test 2 — @singleton class resolves correctly in a route handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_singleton_resolved_in_route_handler() -> None:
    """A ``@singleton``-decorated service is injected into a route handler.

    Uses :func:`~quadkit.web.quickstart.singleton` to mark a class, then
    verifies that the HTTP response reflects the service's output.
    """
    from quadkit.web.quickstart import singleton

    @singleton
    class GreetingService:
        def greet(self, name: str) -> str:
            return f"Hello, {name}!"

    async def greet_handler(svc: GreetingService) -> dict:
        return {"message": svc.greet("World")}

    qs = _QuickstartApp()
    qs._collect_script_routes = lambda: [  # type: ignore[method-assign]
        _PendingRoute(path="/greet", method="GET", handler=greet_handler)
    ]
    qs._collect_script_services = lambda: [  # type: ignore[method-assign]
        (GreetingService, "singleton")
    ]

    async with await _boot(qs) as client:
        response = await client.get("/greet")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}


# ---------------------------------------------------------------------------
# Test 3 — @singleton returns the same instance across requests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_singleton_same_instance_across_requests() -> None:
    """``@singleton`` scope means all route calls share the same object.

    Each call to the route increments a counter on the service.  If the same
    instance is reused the counter grows monotonically (1, 2, 3 …).  A
    transient scope would reset the counter on every request.
    """
    from quadkit.web.quickstart import singleton

    @singleton
    class CounterService:
        def __init__(self) -> None:
            self.count: int = 0

        def increment(self) -> int:
            self.count += 1
            return self.count

    async def count_handler(svc: CounterService) -> dict:
        return {"count": svc.increment()}

    qs = _QuickstartApp()
    qs._collect_script_routes = lambda: [  # type: ignore[method-assign]
        _PendingRoute(path="/count", method="GET", handler=count_handler)
    ]
    qs._collect_script_services = lambda: [  # type: ignore[method-assign]
        (CounterService, "singleton")
    ]

    async with await _boot(qs) as client:
        r1 = await client.get("/count")
        r2 = await client.get("/count")
        r3 = await client.get("/count")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 200

    # Same singleton instance: counter increments across requests
    assert r1.json()["count"] == 1
    assert r2.json()["count"] == 2
    assert r3.json()["count"] == 3


# ---------------------------------------------------------------------------
# Test 4 — @injectable returns a new instance on each request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_injectable_new_instance_per_request() -> None:
    """``@injectable`` (transient) scope creates a new instance each resolution.

    The counter on the service always starts at 0 because the container
    creates a fresh instance for every injection point.
    """
    from quadkit.web.quickstart import injectable

    @injectable
    class TransientCounter:
        def __init__(self) -> None:
            self.count: int = 0

        def increment(self) -> int:
            self.count += 1
            return self.count

    async def count_handler(svc: TransientCounter) -> dict:
        return {"count": svc.increment()}

    qs = _QuickstartApp()
    qs._collect_script_routes = lambda: [  # type: ignore[method-assign]
        _PendingRoute(path="/transient", method="GET", handler=count_handler)
    ]
    qs._collect_script_services = lambda: [  # type: ignore[method-assign]
        (TransientCounter, "transient")
    ]

    async with await _boot(qs) as client:
        r1 = await client.get("/transient")
        r2 = await client.get("/transient")
        r3 = await client.get("/transient")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 200

    # New instance each time: counter is always 1
    assert r1.json()["count"] == 1
    assert r2.json()["count"] == 1
    assert r3.json()["count"] == 1


# ---------------------------------------------------------------------------
# Test 5 — _QUICKSTART_REGISTRY is populated by the decorators
# ---------------------------------------------------------------------------


def test_quickstart_registry_populated_by_decorators() -> None:
    """Calling :func:`singleton` / :func:`injectable` appends to the registry.

    This verifies that classes defined inside any scope (not just module-level)
    are findable by ``_collect_script_services`` without a ``sys.modules`` scan.
    """
    from quadkit.web.quickstart import (
        _QUICKSTART_REGISTRY,
        _reset_quickstart_registry,
        injectable,
        singleton,
    )

    _reset_quickstart_registry()
    try:

        @singleton
        class MySingleton:
            pass

        @injectable
        class MyTransient:
            pass

        registry_classes = [cls for cls, _ in _QUICKSTART_REGISTRY]
        registry_scopes = {cls: scope for cls, scope in _QUICKSTART_REGISTRY}

        assert MySingleton in registry_classes
        assert MyTransient in registry_classes
        assert registry_scopes[MySingleton] == "singleton"
        assert registry_scopes[MyTransient] == "transient"

    finally:
        _reset_quickstart_registry()
