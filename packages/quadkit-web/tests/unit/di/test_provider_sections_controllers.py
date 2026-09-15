"""Regression tests for controller singleton registration.

Guards the fix for the bug where ``register_controller_singletons``
unconditionally re-registered every controller class, clobbering richer
registrations made earlier by feature providers (e.g. GraphQLProvider
binding ``GraphQLController`` to itself). The unbound class then resolved
with no provider attached and every ``POST /graphql`` returned 503
"GraphQL subsystem not configured".
"""

from __future__ import annotations

import pytest

from quadkit.di.container import Container
from quadkit.web.di import provider_sections
from quadkit.web.routing.controllers import Controller


class _BoundController(Controller):
    """Stand-in for a feature provider's controller."""

    def __init__(self, marker: str = "unbound") -> None:
        self.marker = marker


class _FreshController(Controller):
    """Controller nobody registered before web boot."""


@pytest.mark.asyncio
async def test_existing_bound_registration_is_kept() -> None:
    """A pre-registered (bound) singleton must survive web-boot registration."""
    container = Container()
    bound = _BoundController(marker="bound")
    container.singleton(_BoundController, bound)

    provider_sections.register_controller_singletons(
        container,
        [_BoundController],
    )

    resolved = await container.resolve(_BoundController)
    assert resolved is bound
    assert resolved.marker == "bound"


@pytest.mark.asyncio
async def test_existing_factory_registration_is_kept() -> None:
    """A pre-registered factory (e.g. lambda closing over a provider) wins."""
    container = Container()
    container.singleton(
        _BoundController,
        lambda: _BoundController(marker="from-factory"),
    )

    provider_sections.register_controller_singletons(
        container,
        [_BoundController],
    )

    resolved = await container.resolve(_BoundController)
    assert resolved.marker == "from-factory"


@pytest.mark.asyncio
async def test_unregistered_controller_is_registered() -> None:
    """Classes nobody registered yet are still registered as singletons."""
    container = Container()

    provider_sections.register_controller_singletons(
        container,
        [_FreshController],
    )

    resolved = await container.resolve(_FreshController)
    assert isinstance(resolved, _FreshController)
    # Singleton semantics: the same instance every time.
    assert (await container.resolve(_FreshController)) is resolved
