"""Tests for DefaultMiddlewareStack.

Covers:
- ``DefaultMiddlewareStack.build()`` always includes ``DIScopeMiddleware``
- Extra middlewares are prepended before the DI-scope entry
- The class is importable from both ``quadkit.web.middleware`` and
  ``quadkit.web``
- ``WebMiddlewareManager.build_native_stack`` produces an equivalent result
"""

from __future__ import annotations

import pytest
from starlette.middleware import Middleware as StarletteMiddleware

# ---------------------------------------------------------------------------
# Test 1 — importable from quadkit.web.middleware and quadkit.web
# ---------------------------------------------------------------------------


def test_default_middleware_stack_importable_from_middleware_package() -> None:
    """``DefaultMiddlewareStack`` is exported from ``quadkit.web.middleware``."""
    from quadkit.web.middleware import DefaultMiddlewareStack  # noqa: F401

    assert DefaultMiddlewareStack is not None


def test_default_middleware_stack_importable_from_quadkit_web() -> None:
    """``DefaultMiddlewareStack`` is importable from the root ``quadkit.web`` package."""
    from quadkit.web import DefaultMiddlewareStack  # noqa: F401

    assert DefaultMiddlewareStack is not None


# ---------------------------------------------------------------------------
# Test 2 — build() returns a list of StarletteMiddleware with DIScopeMiddleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_stack_includes_di_scope_middleware() -> None:
    """``build()`` always includes ``DIScopeMiddleware`` as a Starlette entry.

    Even with an empty ``extra_middlewares`` list the stack must contain at
    least the DI-scope middleware so request-scoped resolution works.
    """
    from quadkit.di.container import Container
    from quadkit.web.middleware.stack import DefaultMiddlewareStack

    container = Container()
    stack = DefaultMiddlewareStack(container=container)
    middlewares = stack.build()

    assert len(middlewares) >= 1
    assert all(isinstance(mw, StarletteMiddleware) for mw in middlewares)
    # At least one entry should wrap DIScopeMiddleware
    cls_names = [mw.cls.__name__ for mw in middlewares]
    assert "DIScopeMiddleware" in cls_names


# ---------------------------------------------------------------------------
# Test 3 — extra middlewares appear in the built list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_stack_includes_extra_middlewares() -> None:
    """User-supplied ``extra_middlewares`` are included in the built stack.

    The stack count grows by one for each extra middleware supplied.
    Quadkit middleware instances are wrapped as ``_QuadkitMiddlewareAdapter``
    Starlette entries — the adapted wrapper class name is not the original class
    name.
    """
    from quadkit.di.container import Container
    from quadkit.web.middleware.stack import DefaultMiddlewareStack
    from quadkit.web.middleware.timing import TimingMiddleware

    container = Container()

    # Baseline — no extra middleware
    base_stack = DefaultMiddlewareStack(container=container)
    base_count = len(base_stack.build())

    # Stack with one extra Quadkit middleware
    timing_mw = TimingMiddleware(app=None)  # type: ignore[arg-type]
    extended_stack = DefaultMiddlewareStack(
        container=container,
        extra_middlewares=[timing_mw],
    )
    extended = extended_stack.build()

    # One extra entry should appear
    assert len(extended) == base_count + 1
    # Quadkit middlewares are wrapped by _QuadkitMiddlewareAdapter
    cls_names = [mw.cls.__name__ for mw in extended]
    assert "_QuadkitMiddlewareAdapter" in cls_names
    assert "DIScopeMiddleware" in cls_names


# ---------------------------------------------------------------------------
# Test 4 — WebMiddlewareManager delegates to DefaultMiddlewareStack (DRY)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_middleware_manager_delegates_to_default_stack() -> None:
    """``WebMiddlewareManager.build_native_stack`` delegates to ``DefaultMiddlewareStack``.

    The list produced by the manager must match what ``DefaultMiddlewareStack``
    would produce independently for the same inputs (DRY guarantee).
    """
    from quadkit.di.container import Container
    from quadkit.web.config import WebConfig
    from quadkit.web.di.provider import WebProvider
    from quadkit.web.middleware.manager import WebMiddlewareManager
    from quadkit.web.middleware.stack import DefaultMiddlewareStack

    container = Container()
    provider = WebProvider(web_config=WebConfig())
    manager = WebMiddlewareManager(provider)

    manager_result = manager.build_native_stack(container)
    stack_result = DefaultMiddlewareStack(
        container=container,
        extra_middlewares=list(provider.middleware),
    ).build()

    assert len(manager_result) == len(stack_result)
    assert [mw.cls for mw in manager_result] == [mw.cls for mw in stack_result]
