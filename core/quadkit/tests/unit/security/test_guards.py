"""Tests for security guards.

Adapted from quadkit-security/tests/unit/test_guards.py.
Adds origin-guard assertion proving modules resolve to quadkit core.
"""

from __future__ import annotations

import importlib.util

import pytest

from quadkit.security.guards.chain import GuardChainImpl
from quadkit.security.guards.decorator import use_guards


# ---------------------------------------------------------------------------
# Origin guard — proves core package is being exercised
# ---------------------------------------------------------------------------


class TestGuardsModuleIsCore:
    """Verify guards resolves to quadkit core, not quadkit-security."""

    def test_guards_chain_module_is_core_package(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.guards.chain")
        assert spec is not None, "quadkit.security.guards.chain must be importable"
        assert spec.origin is not None
        assert "quadkit-security" not in spec.origin, (
            f"Expected quadkit.security.guards.chain to resolve to quadkit core, "
            f"but got: {spec.origin!r}"
        )

    def test_guards_decorator_module_is_core_package(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.guards.decorator")
        assert spec is not None
        assert spec.origin is not None
        assert "quadkit-security" not in spec.origin, (
            f"Expected quadkit.security.guards.decorator to resolve to quadkit core, "
            f"but got: {spec.origin!r}"
        )


# ---------------------------------------------------------------------------
# P2-guard-chain: propagate_exceptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guard_chain_propagate_exceptions_reraises() -> None:
    """P2-guard-chain: propagate_exceptions=True must re-raise guard exceptions."""

    class BrokenGuard:
        async def can_activate(self, context: dict) -> bool:
            raise RuntimeError("guard internals exploded")

    chain = GuardChainImpl([BrokenGuard()], propagate_exceptions=True)
    with pytest.raises(RuntimeError, match="guard internals exploded"):
        await chain.check({})


@pytest.mark.asyncio
async def test_guard_chain_default_returns_false_on_exception() -> None:
    """P2-guard-chain: default behaviour (propagate=False) still returns False."""

    class BrokenGuard:
        async def can_activate(self, context: dict) -> bool:
            raise ValueError("oops")

    chain = GuardChainImpl([BrokenGuard()])
    result = await chain.check({})
    assert result is False


@pytest.mark.asyncio
async def test_guard_chain_add_preserves_propagate_exceptions() -> None:
    """P2-guard-chain: .add() must preserve the propagate_exceptions flag."""

    class BrokenGuard:
        async def can_activate(self, context: dict) -> bool:
            raise RuntimeError("blown up")

    base = GuardChainImpl(propagate_exceptions=True)
    chain = base.add(BrokenGuard())
    with pytest.raises(RuntimeError, match="blown up"):
        await chain.check({})


class TestGuardChain:
    """Tests for GuardChainImpl."""

    @pytest.fixture
    def mock_guard(self):
        class MockGuard:
            async def can_activate(self, context: dict) -> bool:
                return context.get("allowed", False)

        return MockGuard()

    def test_empty_chain(self) -> None:
        """Should create an empty chain."""
        chain = GuardChainImpl()
        assert len(chain._guards) == 0

    def test_chain_with_guards(self, mock_guard) -> None:
        """Should create a chain with guards."""
        chain = GuardChainImpl([mock_guard])
        assert len(chain._guards) == 1

    @pytest.mark.asyncio
    async def test_check_all_allowed(self, mock_guard) -> None:
        """Should pass when all guards allow."""
        chain = GuardChainImpl([mock_guard])
        result = await chain.check({"allowed": True})
        assert result is True

    @pytest.mark.asyncio
    async def test_check_denied(self, mock_guard) -> None:
        """Should fail when guard denies."""
        chain = GuardChainImpl([mock_guard])
        result = await chain.check({"allowed": False})
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_is_alias_for_check(self, mock_guard) -> None:
        """execute() should behave identically to check()."""
        chain = GuardChainImpl([mock_guard])
        assert await chain.execute({"allowed": True}) is True
        assert await chain.execute({"allowed": False}) is False

    def test_repr(self) -> None:
        chain = GuardChainImpl()
        assert "0 guards" in repr(chain)


class TestUseGuardsDecorator:
    """Tests for @use_guards decorator."""

    @pytest.mark.asyncio
    async def test_decorator_applies_guard(self) -> None:
        """Should apply guard to decorated function."""

        class TestGuard:
            async def can_activate(self, context: dict) -> bool:
                return context.get("user", {}).get("is_admin", False)

        @use_guards(TestGuard())
        async def protected_func(context: dict) -> str:
            return "success"

        result = await protected_func({"user": {"is_admin": True}})
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_raises_on_deny(self) -> None:
        """Should raise when guard denies."""

        class TestGuard:
            async def can_activate(self, context: dict) -> bool:
                return False

        @use_guards(TestGuard())
        async def protected_func(context: dict) -> str:
            return "success"

        from quadkit.contracts.exceptions.middleware import MiddlewareGuardError

        with pytest.raises(MiddlewareGuardError):
            await protected_func({"user": {"is_admin": False}})

    def test_decorator_rejects_sync_function(self) -> None:
        """Should reject non-async functions."""
        with pytest.raises(TypeError, match="async"):

            @use_guards()
            def sync_func(context: dict) -> None:
                pass

    @pytest.mark.asyncio
    async def test_empty_guards_allows_all(self) -> None:
        """Empty guard list always allows."""

        @use_guards()
        async def open_func() -> str:
            return "ok"

        result = await open_func()
        assert result == "ok"
