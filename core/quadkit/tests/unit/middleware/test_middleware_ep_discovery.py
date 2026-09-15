"""Tests for entry-point discovery in MiddlewareProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quadkit.middleware.di.provider import _EP_GROUP, MiddlewareProvider


class _FakeProvider:
    """Test stub that is *not* a Provider subclass — should be skipped."""

    async def register(self, container: object) -> None:
        pass


class TestMiddlewareProviderEpDiscovery:
    """Tests for ``MiddlewareProvider._discover_providers``."""

    @pytest.mark.asyncio
    async def test_no_entry_points(self) -> None:
        """Discovery with an empty EP group registers nothing extra."""

        container = MagicMock()
        container.singleton = MagicMock()

        with patch(
            "quadkit.middleware.di.provider.importlib.metadata.entry_points",
            return_value=[],
        ):
            provider = MiddlewareProvider()
            await provider._discover_providers(container)

        # No extra registrations beyond what register() itself would add
        container.singleton.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_provider_ep_is_called(self) -> None:
        """A Provider subclass found via EP has its register() called."""
        from quadkit.di.provider import Provider

        registered: list[object] = []

        class _DiscoveredProvider(Provider):
            name = "discovered"

            async def register(self, container: object) -> None:
                registered.append(container)

            async def boot(self, container: object) -> None:
                pass

            async def shutdown(self) -> None:
                pass

        fake_ep = MagicMock()
        fake_ep.name = "discovered"
        fake_ep.load.return_value = _DiscoveredProvider

        container = MagicMock()

        with patch(
            "quadkit.middleware.di.provider.importlib.metadata.entry_points",
            return_value=[fake_ep],
        ):
            provider = MiddlewareProvider()
            await provider._discover_providers(container)

        assert len(registered) == 1
        assert registered[0] is container

    @pytest.mark.asyncio
    async def test_non_provider_ep_is_skipped(self) -> None:
        """An EP that resolves to a non-Provider type is silently skipped."""
        registered: list[object] = []

        class _NotAProvider:
            async def register(self, container: object) -> None:
                registered.append(container)

        fake_ep = MagicMock()
        fake_ep.name = "not_a_provider"
        fake_ep.load.return_value = _NotAProvider

        container = MagicMock()

        with patch(
            "quadkit.middleware.di.provider.importlib.metadata.entry_points",
            return_value=[fake_ep],
        ):
            provider = MiddlewareProvider()
            await provider._discover_providers(container)

        # Not a Provider subclass — must be skipped
        assert len(registered) == 0

    @pytest.mark.asyncio
    async def test_load_failure_is_tolerated(self) -> None:
        """An EP whose load() raises continues without crashing discovery."""
        from quadkit.di.provider import Provider

        class _GoodProvider(Provider):
            name = "good"
            registered = False

            async def register(self, container: object) -> None:
                _GoodProvider.registered = True

            async def boot(self, container: object) -> None:
                pass

            async def shutdown(self) -> None:
                pass

        bad_ep = MagicMock()
        bad_ep.name = "bad"
        bad_ep.load.side_effect = ImportError("missing dep")

        good_ep = MagicMock()
        good_ep.name = "good"
        good_ep.load.return_value = _GoodProvider

        container = MagicMock()

        with patch(
            "quadkit.middleware.di.provider.importlib.metadata.entry_points",
            return_value=[bad_ep, good_ep],
        ):
            provider = MiddlewareProvider()
            await provider._discover_providers(container)

        assert _GoodProvider.registered is True

    @pytest.mark.asyncio
    async def test_ep_group_constant(self) -> None:
        """The EP group name matches the expected constant."""
        assert _EP_GROUP == "quadkit.middleware"
