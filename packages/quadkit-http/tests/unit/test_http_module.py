"""Unit tests for HTTPModule with a real DI Container."""

from __future__ import annotations

from typing import Any, cast

import pytest

from quadkit.contracts.web import HTTPClientProtocol
from quadkit.di.container import Container
from quadkit.di.module import ModuleCompiler
from quadkit.http import HTTPClient, HTTPClientConfig, HTTPModule


@pytest.mark.asyncio
async def test_http_module_boots_and_resolves_in_real_container() -> None:
    """HTTPModule.configure() registers and resolves HTTPClientProtocol in Container."""
    dyn = HTTPModule.configure(HTTPClientConfig(timeout=15.0))
    ModuleCompiler().compile([dyn])

    container = Container()
    providers = [cast("Any", p) for p in dyn.providers]
    for provider in providers:
        await provider.register(container)
    container.freeze()
    for provider in providers:
        await provider.boot(container)

    try:
        proto_client = await container.resolve(HTTPClientProtocol)
        concrete_client = await container.resolve(HTTPClient)
        assert isinstance(proto_client, HTTPClient)
        assert proto_client is concrete_client
    finally:
        for provider in reversed(providers):
            await provider.shutdown()
