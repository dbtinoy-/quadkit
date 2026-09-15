"""Tests for ContainerTestFixture — isolated DI container for unit tests."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.testing.fixtures.container import ContainerTestFixture


# ---------------------------------------------------------------------------
# Minimal protocol stubs for injection tests
# ---------------------------------------------------------------------------


class _Greeter:
    """Trivial service class used in injection tests."""

    def greet(self) -> str:
        return "hello"


class _MockGreeter:
    """Test double for _Greeter."""

    def greet(self) -> str:
        return "mocked"


# ---------------------------------------------------------------------------
# ContainerTestFixture unit tests
# ---------------------------------------------------------------------------


class TestContainerTestFixtureLifecycle:
    @pytest.mark.asyncio
    async def test_creates_fresh_fixture(self) -> None:
        fixture = ContainerTestFixture()
        assert not fixture._disposed

    @pytest.mark.asyncio
    async def test_dispose_sets_disposed_flag(self) -> None:
        fixture = ContainerTestFixture()
        await fixture.dispose()
        assert fixture._disposed

    @pytest.mark.asyncio
    async def test_dispose_is_idempotent(self) -> None:
        fixture = ContainerTestFixture()
        await fixture.dispose()
        await fixture.dispose()  # Must not raise
        assert fixture._disposed

    @pytest.mark.asyncio
    async def test_async_context_manager_disposes_on_exit(self) -> None:
        async with ContainerTestFixture() as fixture:
            assert not fixture._disposed
        assert fixture._disposed

    @pytest.mark.asyncio
    async def test_async_context_manager_disposes_on_exception(self) -> None:
        fixture = None
        with pytest.raises(ValueError, match="expected"):
            async with ContainerTestFixture() as f:
                fixture = f
                raise ValueError("expected")
        assert fixture is not None and fixture._disposed

    @pytest.mark.asyncio
    async def test_get_raises_after_dispose(self) -> None:
        fixture = ContainerTestFixture()
        await fixture.dispose()
        with pytest.raises(RuntimeError, match="disposed"):
            await fixture.get(_Greeter)

    @pytest.mark.asyncio
    async def test_get_optional_returns_none_after_dispose(self) -> None:
        fixture = ContainerTestFixture()
        await fixture.dispose()
        result = await fixture.get_optional(_Greeter)
        assert result is None


class TestContainerTestFixtureMocking:
    @pytest.mark.asyncio
    async def test_mock_registers_singleton(self) -> None:
        async with ContainerTestFixture() as fixture:
            mock = _MockGreeter()
            fixture.mock(_Greeter, mock)
            resolved = await fixture.get(_Greeter)
            assert resolved is mock

    @pytest.mark.asyncio
    async def test_mock_overwrites_previous_registration(self) -> None:
        async with ContainerTestFixture() as fixture:
            first_mock = _MockGreeter()
            second_mock = _MockGreeter()
            fixture.mock(_Greeter, first_mock)
            fixture.mock(_Greeter, second_mock)
            resolved = await fixture.get(_Greeter)
            assert resolved is second_mock

    @pytest.mark.asyncio
    async def test_override_context_manager_registers_mock(self) -> None:
        async with ContainerTestFixture() as fixture:
            mock = _MockGreeter()
            async with fixture.override(_Greeter, mock):
                resolved = await fixture.get(_Greeter)
                assert resolved is mock


class TestContainerTestFixtureContainerProperty:
    @pytest.mark.asyncio
    async def test_container_property_returns_test_container(self) -> None:
        from quadkit.testing.harness.container import QuadkitContainerHarness

        async with ContainerTestFixture() as fixture:
            assert isinstance(fixture.container, QuadkitContainerHarness)

    @pytest.mark.asyncio
    async def test_each_fixture_has_isolated_container(self) -> None:
        async with ContainerTestFixture() as a, ContainerTestFixture() as b:
            assert a.container is not b.container


class TestContainerTestFixtureTopLevelImport:
    """Verify ContainerTestFixture is importable from quadkit.testing."""

    def test_importable_from_top_level(self) -> None:
        from quadkit.testing import ContainerTestFixture as TopLevel  # noqa: PLC0415

        assert TopLevel is ContainerTestFixture


# ---------------------------------------------------------------------------
# test_container pytest fixture tests
# ---------------------------------------------------------------------------


class TestTestContainerFixture:
    @pytest.mark.asyncio
    async def test_test_container_fixture_is_container_test_fixture(
        self, test_container: ContainerTestFixture
    ) -> None:
        assert isinstance(test_container, ContainerTestFixture)

    @pytest.mark.asyncio
    async def test_test_container_fixture_is_not_disposed(
        self, test_container: ContainerTestFixture
    ) -> None:
        assert not test_container._disposed

    @pytest.mark.asyncio
    async def test_test_container_fixture_accepts_mock(
        self, test_container: ContainerTestFixture
    ) -> None:
        mock = _MockGreeter()
        test_container.mock(_Greeter, mock)
        resolved = await test_container.get(_Greeter)
        assert resolved is mock

    @pytest.mark.asyncio
    async def test_test_container_fixture_isolation_between_tests_a(
        self, test_container: ContainerTestFixture
    ) -> None:
        """Fixture registers a mock — isolated per test. (Part A)"""
        mock = _MockGreeter()
        test_container.mock(_Greeter, mock)
        resolved = await test_container.get(_Greeter)
        assert resolved is mock

    @pytest.mark.asyncio
    async def test_test_container_fixture_isolation_between_tests_b(
        self, test_container: ContainerTestFixture
    ) -> None:
        """Should NOT see the mock from the previous test. (Part B)"""
        # Because ContainerTestFixture creates a fresh container per test,
        # _Greeter is not registered here; resolve_optional returns None.
        resolved = await test_container.get_optional(_Greeter)
        # Either None (not registered) or a fresh unrelated instance — NOT mock.
        assert resolved is None or not isinstance(resolved, _MockGreeter)
