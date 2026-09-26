"""Regression test: DI boundary contract for CacheBackendProtocol vs CacheService.

The bug: ``CacheProvider`` registered the bare-value facade ``CacheService`` under
the ``CacheBackendProtocol`` key. The protocol declares a ``Result``-based contract,
so every consumer that resolved ``CacheBackendProtocol`` and called ``.is_ok()`` /
``.unwrap_or()`` on the result crashed (e.g. the CSRF middleware).

These tests exercise the *real* resolution path through a real container so they
fail if the unnamed ``CacheBackendProtocol`` binding ever resolves to a
``CacheService`` again — including the subtle regression of keeping a ``factory=``
binding but pointing it back at ``get_default_service``.
"""

from __future__ import annotations

import pytest

from quadkit import Container
from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.config import CacheBackendConfig, CacheConfig
from quadkit.cache.di.provider import CacheProvider
from quadkit.cache.service.core import CacheService
from quadkit.cache.types import BackendType
from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol


def _make_memory_config() -> CacheConfig:
    """A minimal config with a single default in-memory backend."""
    return CacheConfig(
        backends=[
            CacheBackendConfig(
                name="default",
                type=BackendType.MEMORY,
                default=True,
                enabled=True,
            )
        ]
    )


async def _booted_provider_and_container() -> tuple[CacheProvider, Container]:
    """Register a provider into a real container and populate its backends."""
    provider = CacheProvider(config=_make_memory_config())
    container = Container()
    await provider.register(container)
    # boot() also wires repositories (and needs a clock); for this contract test
    # we only need the backends/services populated, which these two calls do.
    await provider._initialize_backends(container)
    provider._initialize_services()
    return provider, container


class TestDiBoundaryContract:
    @pytest.mark.asyncio
    async def test_resolve_cache_backend_protocol_is_result_based(self) -> None:
        """The crux: resolving CacheBackendProtocol yields a Result-based backend.

        Before the fix this resolved to a CacheService whose ``get()`` returns a
        bare value, so ``result.is_ok()`` raised AttributeError — the exact crash
        the CSRF middleware hit.
        """
        _provider, container = await _booted_provider_and_container()

        backend = await container.resolve(CacheBackendProtocol)

        assert not isinstance(backend, CacheService), (
            "CacheBackendProtocol must resolve to a backend, not the bare-value "
            "CacheService facade."
        )
        assert isinstance(backend, MemoryCacheBackend)

        result = await backend.get("missing-key")
        assert hasattr(result, "is_ok"), (
            f"backend.get() returned {result!r} (type={type(result).__name__}); "
            "the protocol requires a Result. This is the CSRF crash."
        )
        assert result.is_ok()
        assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_resolve_cache_service_is_bare_value(self) -> None:
        """CacheService resolves under its own key and keeps its bare-value API."""
        _provider, container = await _booted_provider_and_container()

        service = await container.resolve(CacheService)

        assert isinstance(service, CacheService)
        value = await service.get("missing-key")
        assert not hasattr(value, "is_ok"), (
            f"CacheService.get() must return a bare value, got {value!r}."
        )
        assert value is None

    @pytest.mark.asyncio
    async def test_backend_and_service_are_distinct_resolutions(self) -> None:
        """The two keys must not collapse to the same object/contract."""
        _provider, container = await _booted_provider_and_container()

        backend = await container.resolve(CacheBackendProtocol)
        service = await container.resolve(CacheService)

        assert isinstance(service, CacheService)
        assert not isinstance(backend, CacheService)
