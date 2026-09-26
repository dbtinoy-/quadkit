"""Tests for the Events admin overview's public diagnostics boundary."""

from __future__ import annotations

import pytest

from quadkit.contracts.admin import PageContent, StatContent
from quadkit.events.admin.pages import EventsOverviewPage


class PrivateOnlyBus:
    """Legacy-shaped bus used to ensure private diagnostics are not inspected."""

    _dispatch_errors = (RuntimeError("private failure"),)


class PublicDiagnosticsBus:
    """Minimal bus exposing the optional public diagnostics capability."""

    dispatch_errors = (RuntimeError("public failure"),)


class TestEventsOverviewPage:
    """The overview should consume diagnostics through the public boundary."""

    @pytest.mark.asyncio
    async def test_uses_public_dispatch_errors_without_private_fallback(self) -> None:
        private_content = await EventsOverviewPage(PrivateOnlyBus()).handle(None)
        public_content = await EventsOverviewPage(PublicDiagnosticsBus()).handle(None)

        assert isinstance(private_content, PageContent)
        assert isinstance(private_content.body, StatContent)
        assert isinstance(public_content.body, StatContent)

        private_stats = {stat.label: stat.value for stat in private_content.body.stats}
        public_stats = {stat.label: stat.value for stat in public_content.body.stats}
        assert private_stats["Errors"] == "0"
        assert public_stats["Errors"] == "1"
