"""Feature tour: middleware as explicit, composable structure.

Three shipped pieces cover the whole lifecycle of a middleware stack.
`MiddlewareChain` is the fluent builder: `add` in the order you want,
`build` freezes an immutable onion pipeline where each middleware wraps
the next. `MiddlewareRegistry` keeps named entries with priorities and
hands back either the priority-ordered list or a ready chain. And
`DefaultMiddlewareStack` makes the web framework's own stack equally
visible — the same list `WebProvider` installs — so user middleware
joins in user order right behind the always-outermost DI-scope layer.
"""

import pytest
from starlette.middleware import Middleware as StarletteMiddleware

from quadkit import MiddlewareChain, MiddlewareRegistry
from quadkit.di.container import Container
from quadkit.web import DefaultMiddlewareStack
from quadkit.web.middleware.timing import TimingMiddleware

Context = dict[str, str]


def recorder(name: str, calls: list[str]):  # type: ignore[no-untyped-def]
    """A pipeline middleware: ``async (context, next_handler) -> result``."""

    async def _middleware(context: Context, next_handler):  # type: ignore[no-untyped-def]
        calls.append(f"{name}:enter")
        result = await next_handler(context)
        calls.append(f"{name}:exit")
        return result

    return _middleware


@pytest.mark.asyncio
async def test_chain_builds_a_frozen_onion_pipeline() -> None:
    calls: list[str] = []
    pipeline = (
        MiddlewareChain()
        .add(recorder("auth", calls))
        .add(recorder("audit", calls))
        .build()
    )

    async def handler(context: Context) -> dict[str, bool]:
        calls.append("handler")
        return {"ok": True}

    result = await pipeline.execute({"request": "r1"}, handler)

    assert result == {"ok": True}
    # Onion order: first added wraps everyone else.
    assert calls == ["auth:enter", "audit:enter", "handler", "audit:exit", "auth:exit"]

    # The built pipeline is immutable: `add` returns a new pipeline and
    # leaves the original exactly as built.
    extended = pipeline.add(recorder("extra", calls))
    calls.clear()
    await pipeline.execute({"request": "r2"}, handler)
    assert calls == ["auth:enter", "audit:enter", "handler", "audit:exit", "auth:exit"]

    calls.clear()
    await extended.execute({"request": "r3"}, handler)
    assert calls == [
        "auth:enter",
        "audit:enter",
        "extra:enter",
        "handler",
        "extra:exit",
        "audit:exit",
        "auth:exit",
    ]


@pytest.mark.asyncio
async def test_registry_orders_by_priority_and_builds_chains() -> None:
    calls: list[str] = []
    registry = MiddlewareRegistry()
    auth, audit, access_log = object(), object(), object()
    registry.register("auth", auth, priority=10)
    registry.register("access_log", access_log, priority=50)  # 50 is the default
    registry.register("audit", audit, priority=5)

    # Lower priority runs earlier; `names()` is alphabetical, `all()` is ordered.
    assert registry.names() == ["access_log", "audit", "auth"]
    assert registry.all() == [audit, auth, access_log]

    # Duplicate names are a wiring error, not an overwrite.
    with pytest.raises(ValueError, match="Middleware 'auth' is already registered"):
        registry.register("auth", object(), priority=99)

    # `build_chain()` lifts the priority order straight into a chain.
    registry2 = MiddlewareRegistry()
    registry2.register("second", recorder("second", calls), priority=20)
    registry2.register("first", recorder("first", calls), priority=10)
    pipeline = registry2.build_chain().build()

    async def handler(context: Context) -> None:
        calls.append("handler")

    await pipeline.execute({"request": "r1"}, handler)
    assert calls == ["first:enter", "second:enter", "handler", "second:exit", "first:exit"]


@pytest.mark.asyncio
async def test_default_stack_is_explicit_and_extensible() -> None:
    container = Container()
    base = DefaultMiddlewareStack(container=container).build()
    base_names = [entry.cls.__name__ for entry in base]

    # The framework's own stack is a plain list of Starlette entries —
    # inspectable, with request-scoped DI always present.
    assert base
    assert all(isinstance(entry, StarletteMiddleware) for entry in base)
    assert "DIScopeMiddleware" in base_names

    # A user middleware joins right behind DIScopeMiddleware, which stays
    # outermost by design: request-scoped DI must wrap every later layer.
    extended = DefaultMiddlewareStack(
        container=container,
        extra_middlewares=[TimingMiddleware(app=None)],  # type: ignore[arg-type]
    ).build()
    assert len(extended) == len(base) + 1
    assert extended[0].cls.__name__ == "DIScopeMiddleware"
    extra_position = next(
        i for i, e in enumerate(extended) if e.cls.__name__ not in base_names
    )
    assert extra_position == 1
