"""Runnable companion to docs/guides/dependency-overrides.md.

A controller that asks for a *protocol* in its constructor, production
bindings from a provider, and a test that substitutes a fake before the
application boots:

    pytest test_dependency_overrides_app.py
"""

from typing import Protocol

from quadkit import Application
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.di.provider import Provider
from quadkit.web import Controller, WebModule, get


class Greeter(Protocol):
    """The service contract the controller depends on — not a class."""

    def greet(self) -> str: ...


class FriendlyGreeter:
    """The production implementation bound by the provider."""

    def greet(self) -> str:
        return "hello from friendly"


class GreeterProvider(Provider):
    """Binds the protocol to the production implementation."""

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(Greeter, instance=FriendlyGreeter())


class GreetingController(Controller):
    """Constructor injection: annotate with the protocol, get the binding."""

    def __init__(self, greeter: Greeter) -> None:
        self._greeter = greeter

    @get("/greet")
    async def greet(self) -> dict:
        return {"greeting": self._greeter.greet()}


def create_app() -> Application:
    app = Application()
    app.add_modules([WebModule.configure(controllers=[GreetingController])])
    app.add_provider(GreeterProvider())
    return app


app = create_app()
