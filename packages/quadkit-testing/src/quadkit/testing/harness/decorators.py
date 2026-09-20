"""``@testbed`` and ``@override`` — pytest class-decorator sugar over ``AppTestBed``.

Provides a concise, NestJS-inspired DX for writing integration tests without
the ``async with AppTestBed.from_factory(...)`` boilerplate::

    from quadkit.testing.harness.decorators import override, testbed

    @testbed("my_app.app:create_app")
    class TestUserEndpoints:

        @override(UserRepository, MockUserRepository())
        async def test_list_users(self, bed):
            resp = await bed.client.get("/api/v1/users")
            assert resp.status_code == 200

    # Or with overrides shared across the whole class:

    @testbed("my_app.app:create_app", overrides={EmailService: MockEmailService()})
    class TestWithSharedOverrides:

        async def test_send_welcome(self, bed):
            svc = await bed.container.resolve(NotificationService)
            await svc.send_welcome("user@example.com")

Usage rules:
- ``@testbed`` marks a *class* with the factory to boot.
- ``@override`` marks a *method* with extra per-test DI overrides.
- Every test method on a ``@testbed`` class receives a ``bed: AppTestBed``
  argument that is freshly created and torn down per test.
- The class does **not** need to inherit from anything specific and works
  with both ``pytest-asyncio`` and ``asyncio.run``.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any

__all__ = ["override", "testbed"]


# ---------------------------------------------------------------------------
# Internal attribute names
# ---------------------------------------------------------------------------

_TESTBED_FACTORY_ATTR = "__testbed_factory__"
_TESTBED_OVERRIDES_ATTR = "__testbed_overrides__"
_METHOD_OVERRIDES_ATTR = "__testbed_method_overrides__"


# ---------------------------------------------------------------------------
# @override — per-method extra DI overrides
# ---------------------------------------------------------------------------


def override(interface: type, implementation: Any) -> Any:
    """Add a per-test DI override to a test method inside a ``@testbed`` class.

    .. note::
        When used on a method, this stacks *on top of* any class-level
        overrides provided to ``@testbed``.

    Args:
        interface: The service type (contract/protocol) to replace.
        implementation: The replacement instance.

    Returns:
        Method decorator that records the override mapping.

    Example::

        @testbed("my_app.app:create_app")
        class TestPayments:

            @override(PaymentGateway, MockPaymentGateway(fail=True))
            async def test_payment_failure(self, bed):
                resp = await bed.client.post("/pay", json={"amount": 100})
                assert resp.status_code == 402
    """

    def decorator(method: Any) -> Any:
        # Store overrides as a list of (interface, impl) tuples on the method.
        existing: list[tuple[type, Any]] = getattr(method, _METHOD_OVERRIDES_ATTR, [])
        # Prepend so the outermost decorator has lowest priority (consistent
        # with normal class-level overrides that are applied first).
        method.__dict__[_METHOD_OVERRIDES_ATTR] = [
            (interface, implementation),
            *existing,
        ]
        return method

    return decorator


# ---------------------------------------------------------------------------
# @testbed — class decorator
# ---------------------------------------------------------------------------


def testbed(
    factory: str | Any,
    *,
    overrides: dict[type, Any] | None = None,  # noqa: PT028
) -> Any:
    """Mark a test class so every async test method receives a booted ``AppTestBed``.

    The decorator wraps each async test method to:

    1. Build the merged overrides dict (class-level + per-method).
    2. Boot the application via ``AppTestBed.from_factory``.
    3. Inject ``bed`` as the *second* positional argument (after ``self``).
    4. Tear the application down after the method returns (or raises).

    Args:
        factory: Application factory — either a dotted import string
            (``"my_app.app:create_app"``) or a callable returning an
            :class:`~quadkit.app.base.Application`.
        overrides: Class-level DI overrides shared across *all* test methods.

    Returns:
        Class decorator.

    Example::

        @testbed("my_app.app:create_app")
        class TestUserFlow:

            async def test_create_user(self, bed):
                resp = await bed.client.post("/users", json={"name": "Alice"})
                assert resp.status_code == 201

            async def test_list_users(self, bed):
                resp = await bed.client.get("/users")
                assert resp.status_code == 200
    """
    class_overrides: dict[type, Any] = dict(overrides or {})

    def decorator(cls: type) -> type:
        # Store metadata on the class for introspection.
        cls.__testbed_factory__ = factory  # type: ignore[attr-defined]
        cls.__testbed_overrides__ = class_overrides  # type: ignore[attr-defined]

        # Wrap every async method whose name starts with "test_".
        for attr_name in list(vars(cls)):
            if not attr_name.startswith("test"):
                continue
            method = vars(cls)[attr_name]
            if not callable(method) or not inspect.iscoroutinefunction(method):
                continue

            setattr(cls, attr_name, _wrap_test_method(method, factory, class_overrides))

        return cls

    return decorator


# ---------------------------------------------------------------------------
# Internal wrapper
# ---------------------------------------------------------------------------


def _wrap_test_method(
    method: Any,
    factory: str | Any,
    class_overrides: dict[type, Any],
) -> Any:
    """Return a new coroutine function that boots ``AppTestBed`` around *method*."""

    # Collect per-method overrides registered via @override.
    method_overrides: list[tuple[type, Any]] = getattr(
        method, _METHOD_OVERRIDES_ATTR, []
    )

    @functools.wraps(method)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        from quadkit.testing.harness.testbed import AppTestBed

        # Merge: class-level first, then method-level (method wins).
        merged: dict[type, Any] = {**class_overrides, **dict(method_overrides)}

        async with AppTestBed.from_factory(factory, overrides=merged or None) as bed:
            # Inject bed as _first_ non-self positional arg.
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())
            # params[0] == "self", params[1] should be "bed" (or similar)
            if len(params) > 1:
                return await method(self, bed, *args, **kwargs)
            # Edge case: test method doesn't declare bed — still call normally.
            return await method(self, *args, **kwargs)

    return wrapper
