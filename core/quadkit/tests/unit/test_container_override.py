"""Tests for Container.override() method."""

from __future__ import annotations

import pytest

from quadkit.di.container import Container


class TestContainerOverride:
    """Tests for Container.override() testing support."""

    @pytest.mark.asyncio
    async def test_override_replaces_singleton(self) -> None:
        """override() replaces a singleton registration with a new instance."""
        container = Container(testing_mode=True)

        class MyService:
            def __init__(self, value: str = "original") -> None:
                self.value = value

        container.singleton(MyService, factory=lambda: MyService("original"))
        container.freeze()

        # Resolve original
        original = await container.resolve(MyService)
        assert original.value == "original"

        # Override with mock
        mock_service = MyService("mocked")
        container.override(MyService, mock_service)

        # Resolve returns override
        overridden = await container.resolve(MyService)
        assert overridden.value == "mocked"

    @pytest.mark.asyncio
    async def test_override_unregistered_raises(self) -> None:
        """override() raises ContainerError for unregistered services."""
        container = Container(testing_mode=True)

        class Unknown:
            pass

        with pytest.raises(Exception, match="not registered"):
            container.override(Unknown, Unknown())

    @pytest.mark.asyncio
    async def test_override_works_on_frozen_container(self) -> None:
        """override() works even after container is frozen."""
        container = Container(testing_mode=True)

        class SvcA:
            pass

        container.singleton(SvcA, factory=SvcA)
        container.freeze()

        replacement = SvcA()
        container.override(SvcA, replacement)
        resolved = await container.resolve(SvcA)
        assert resolved is replacement

    @pytest.mark.asyncio
    async def test_override_requires_testing_mode(self) -> None:
        """override() raises ContainerError on production containers."""
        container = Container()

        class SvcB:
            pass

        container.singleton(SvcB, factory=SvcB)

        with pytest.raises(Exception, match="testing_mode=True"):
            container.override(SvcB, SvcB())
