"""Ambient async lookup must preserve native request scopes, not root authority."""

from types import SimpleNamespace

import pytest

from quadkit.contracts.core.async_resolver import AsyncResolverProtocol
from quadkit.contracts.core.di import ContainerResolverProtocol
from quadkit.di.container import Container
from quadkit.di.resolution.context import get_async_resolver, get_resolver


class Service:
    pass


class Request:
    """Minimal request shape; Core tests do not depend on a web SDK."""

    def __init__(self, scope):
        self.scope = scope

    @property
    def app(self):
        return self.scope["app"]


@pytest.mark.parametrize("shape", ["scope", "request", "state", "direct"])
async def test_native_request_scope_is_resolved_without_root_mutation_methods(shape):
    container = Container()
    container.scoped(Service, Service)
    async with container.create_scope() as scoped:
        assert isinstance(scoped, AsyncResolverProtocol)
        assert not isinstance(scoped, ContainerResolverProtocol)
        scope = {
            "type": "http",
            "state": {"container": scoped},
            "app": SimpleNamespace(container=container),
        }
        if shape == "scope":
            context = scope
        elif shape == "request":
            context = Request(scope)
        elif shape == "state":
            context = SimpleNamespace(state=SimpleNamespace(container=scoped))
        else:
            context = scoped
        resolver = get_async_resolver(context)
        # The legacy broad root helper retains its sync/mutation contract.
        assert (
            get_resolver(
                SimpleNamespace(
                    state=SimpleNamespace(container=scoped),
                    app=SimpleNamespace(container=container),
                )
            )
            is container
        )
        assert resolver is scoped
        assert await resolver.resolve_optional(Service) is await scoped.resolve(Service)


def test_request_without_host_or_resolver_returns_none():
    assert get_async_resolver(Request({"type": "http", "headers": []})) is None


@pytest.mark.parametrize(
    "bad", [None, {}, object(), SimpleNamespace(resolve=lambda _: None)]
)
def test_invalid_resolver_is_not_accepted(bad):
    assert get_async_resolver({"state": {"container": bad}}) is None


def test_existing_root_resolver_is_still_supported():
    container = Container()
    assert get_resolver(container) is container
    assert get_resolver(SimpleNamespace(container=container)) is container
