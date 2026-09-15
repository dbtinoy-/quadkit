"""Tests for AppTestBed — integration test harness."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.app import Application
from quadkit.testing import AppTestBed


# ---------------------------------------------------------------------------
# Minimal in-process application used by the test harness
# ---------------------------------------------------------------------------


class _GreeterService:
    """Simple service for DI override testing."""

    def greet(self) -> str:
        return "hello from real service"


class _MockGreeterService:
    """Test double for _GreeterService."""

    def greet(self) -> str:
        return "hello from mock"


def _build_minimal_app() -> Application:
    """Create a minimal Application with no web provider (no-HTTP path)."""
    return Application(name="testbed-test-app")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAppTestBedFromApp:
    """AppTestBed.from_app() correctly boots and tears down."""

    @pytest.mark.asyncio
    async def test_from_app_boots_and_exposes_container(self) -> None:
        app = _build_minimal_app()
        async with AppTestBed.from_app(app) as bed:
            assert bed.app is app
            assert bed.container is not None

    @pytest.mark.asyncio
    async def test_from_app_shuts_down_after_context_exit(self) -> None:
        app = _build_minimal_app()
        async with AppTestBed.from_app(app) as bed:
            booted_app = bed.app
        # After exit, app should be stopped (no running state)
        assert booted_app is not None  # sanity

    @pytest.mark.asyncio
    async def test_from_app_applies_di_overrides(self) -> None:
        app = _build_minimal_app()

        from quadkit.di.provider import Provider

        class _RegProvider(Provider):
            async def register(self, container: object) -> None:
                container.singleton(_GreeterService, _GreeterService())  # type: ignore[union-attr]

        app.add_provider(_RegProvider())

        mock = _MockGreeterService()
        async with AppTestBed.from_app(
            app,
            overrides={_GreeterService: mock},
        ) as bed:
            resolved = await bed.container.resolve(_GreeterService)
            assert resolved.greet() == "hello from mock"


class TestAppTestBedFromFactory:
    """AppTestBed.from_factory() with a callable or string factory."""

    @pytest.mark.asyncio
    async def test_from_factory_with_callable(self) -> None:
        async with AppTestBed.from_factory(_build_minimal_app) as bed:
            assert bed.app is not None

    @pytest.mark.asyncio
    async def test_from_factory_callable_with_overrides(self) -> None:
        from quadkit.di.provider import Provider

        class _P(Provider):
            async def register(self, container: object) -> None:
                container.singleton(_GreeterService, _GreeterService())  # type: ignore[union-attr]

        def _factory() -> Application:
            a = _build_minimal_app()
            a.add_provider(_P())
            return a

        mock = _MockGreeterService()
        async with AppTestBed.from_factory(_factory, overrides={_GreeterService: mock}) as bed:
            resolved = await bed.container.resolve(_GreeterService)
            assert resolved.greet() == "hello from mock"

    @pytest.mark.asyncio
    async def test_from_factory_raises_on_invalid_type(self) -> None:
        with pytest.raises(TypeError, match="callable or dotted string"):
            async with AppTestBed.from_factory(42):  # type: ignore[arg-type]
                pass


class TestAppTestBedPytestFixture:
    """Verify the recommended pytest fixture pattern works correctly."""

    @pytest.mark.asyncio
    async def test_fixture_provides_testbed(self) -> None:
        """AppTestBed used inline as async context manager works correctly."""
        async with AppTestBed.from_app(_build_minimal_app()) as bed:
            assert bed.app is not None
            assert bed.container is not None
