"""Tests for CacheProvider Named DI bindings."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from quadkit.cache.config import CacheBackendConfig, CacheConfig
from quadkit.cache.di.provider import CacheProvider
from quadkit.cache.types import BackendType
from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol


def _make_backend_cfg(name: str, default: bool = False) -> CacheBackendConfig:
    return CacheBackendConfig(name=name, type=BackendType.MEMORY, default=default, enabled=True)


def _make_config(*names: str) -> CacheConfig:
    backends = [_make_backend_cfg(n, default=(i == 0)) for i, n in enumerate(names)]
    return CacheConfig(backends=backends)


class TestCacheProviderNamedBindings:
    @pytest.mark.asyncio
    async def test_named_binding_registered_for_each_backend(self) -> None:
        """register() creates a Named binding for every enabled backend."""
        cfg = _make_config("primary", "secondary")
        provider = CacheProvider(config=cfg)
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        names_used = [c.kwargs.get("name") for c in container.singleton.call_args_list]
        assert "primary" in names_used
        assert "secondary" in names_used

    @pytest.mark.asyncio
    async def test_unnamed_binding_exists_for_default_backend(self) -> None:
        """Default backend still receives the unnamed CacheBackendProtocol binding."""
        cfg = _make_config("primary", "secondary")
        provider = CacheProvider(config=cfg)
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        # At least one singleton call with name=None (unnamed)
        unnamed = [c for c in container.singleton.call_args_list if c.kwargs.get("name") is None]
        assert len(unnamed) >= 1

    @pytest.mark.asyncio
    async def test_disabled_backend_not_registered(self) -> None:
        """Disabled backends are skipped — no Named binding created."""
        cfg = CacheConfig(backends=[
            CacheBackendConfig(name="primary", type=BackendType.MEMORY, default=True, enabled=True),
            CacheBackendConfig(name="disabled", type=BackendType.MEMORY, default=False, enabled=False),
        ])
        provider = CacheProvider(config=cfg)
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        names_used = [c.kwargs.get("name") for c in container.singleton.call_args_list]
        assert "disabled" not in names_used

    @pytest.mark.asyncio
    async def test_named_factory_calls_get_backend(self) -> None:
        """Named factory delegates to get_backend(name)."""
        cfg = _make_config("primary", "l2")
        provider = CacheProvider(config=cfg)
        container = MagicMock()
        singleton_calls: list[dict] = []
        container.singleton = MagicMock(side_effect=lambda *a, **kw: singleton_calls.append(kw))

        await provider.register(container)

        # Find the Named binding for "l2"
        l2_call = next((c for c in singleton_calls if c.get("name") == "l2"), None)
        assert l2_call is not None
        assert callable(l2_call.get("factory"))

    @pytest.mark.asyncio
    async def test_single_backend_config_registers_named_and_unnamed(self) -> None:
        """A single backend still gets both Named and unnamed bindings."""
        cfg = _make_config("default")
        provider = CacheProvider(config=cfg)
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        names_used = [c.kwargs.get("name") for c in container.singleton.call_args_list]
        assert "default" in names_used
        # unnamed also present
        assert None in names_used
