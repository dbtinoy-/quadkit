"""Tests for dependency_overrides_app.py — runs from docs/guides/examples in CI."""

import pytest

from quadkit.testing import AppTestBed, WebTestBed

from dependency_overrides_app import Greeter, create_app


class ShoutyGreeter:
    """A test double: same contract, different behavior, zero config."""

    def greet(self) -> str:
        return "HELLO FROM SHOUTY"


@pytest.mark.asyncio
async def test_production_binding_is_used_by_default():
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/greet")
        assert response.json == {"greeting": "hello from friendly"}


@pytest.mark.asyncio
async def test_web_test_bed_override_before_boot():
    # Overrides must be registered *before* the application boots, because
    # providers run at boot: construct the bed, override, then enter.
    bed = WebTestBed(create_app())
    bed.override(Greeter, ShoutyGreeter())
    async with bed:
        response = bed.get("/greet")
        assert response.json == {"greeting": "HELLO FROM SHOUTY"}


@pytest.mark.asyncio
async def test_app_test_bed_overrides_mapping():
    # The same substitution, for application-level (non-HTTP) tests.
    async with AppTestBed.from_factory(
        create_app, overrides={Greeter: ShoutyGreeter()}
    ) as bed:
        greeter = await bed.app.container.resolve(Greeter)
        assert greeter.greet() == "HELLO FROM SHOUTY"
