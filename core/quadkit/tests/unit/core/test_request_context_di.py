from __future__ import annotations

import pytest

from quadkit.contracts.core.context import RequestContextProtocol
from quadkit.di.container import Container
from quadkit.primitives.context import Context, request_scope
from quadkit.primitives.di.provider import CoreInfrastructureProvider


@pytest.mark.asyncio
async def test_core_provider_resolves_active_request_context_from_scope() -> None:
    container = Container()
    provider = CoreInfrastructureProvider()
    await provider.register(container)

    context = await container.resolve(Context)

    async with container.scope() as scoped:
        with request_scope(
            context.registry,
            request_id="req-1",
            user_id="user-1",
            tenant_id="tenant-1",
        ):
            current = await scoped.resolve(RequestContextProtocol)
            assert current is not None
            assert current.user_id == "user-1"
            assert current.tenant_id == "tenant-1"
