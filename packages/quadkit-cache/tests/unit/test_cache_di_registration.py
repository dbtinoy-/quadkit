"""Tests for CacheProvider registration (DI container wiring)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from quadkit.cache import CacheProvider
from quadkit.cache.backends.registry import BackendRegistry
from quadkit.cache.config.top_level import CacheConfig


def _provider(backends: list[dict[str, Any]] | None = None) -> CacheProvider:
    cfg = CacheConfig(backends=backends or [])
    p = CacheProvider(config=cfg)
    # Avoid the entry-point discovery scan (no third-party backends in CI).
    p._discover_backends = AsyncMock()  # type: ignore[method-assign]  # noqa: SLF001
    return p


class _Registrar:
    """Records container bindings (singleton factory bindings)."""

    def __init__(self) -> None:
        self.singletons: dict[Any, dict[str, Any]] = {}
        self.named: dict[tuple[Any, str], dict[str, Any]] = {}
        self.string_keys: dict[str, Any] = {}

    def singleton(self, service: Any, instance: Any = None, factory: Any = None, name: str | None = None) -> None:
        # String service keys (e.g. "state_store.r1") bind positionally with
        # the instance as the second argument — mirror the container's
        # positional convention.
        if isinstance(service, str) and factory is None:
            self.string_keys[service] = instance
            return
        if name is not None:
            # Real registry keys named bindings by (service, name).
            self.named[(service, name)] = {"service": service, "instance": instance, "factory": factory}
        else:
            self.singletons[service] = {"instance": instance, "factory": factory}

    def has(self, service: Any) -> bool:
        return service in self.singletons


class TestRegisterBasics:
    async def test_registers_core_singletons(self) -> None:
        p = _provider()
        reg = _Registrar()
        await p.register(reg)  # type: ignore[arg-type]
        from quadkit.cache.service.core import CacheService
        from quadkit.cache.service.registry import CacheStatusRegistry
        from quadkit.contracts.infra.cache.protocols import (
            CacheBackendProtocol,
            CacheProviderProtocol,
        )

        assert CacheConfig in reg.singletons
        assert reg.singletons[CacheConfig]["instance"] is p.config
        assert BackendRegistry in reg.singletons
        assert CacheStatusRegistry in reg.singletons
        assert CacheProvider in reg.singletons
        assert reg.singletons[CacheProvider]["instance"] is p
        assert CacheProviderProtocol in reg.singletons
        assert reg.singletons[CacheProviderProtocol]["instance"] is p
        assert CacheBackendProtocol in reg.singletons
        assert CacheService in reg.singletons


    async def test_status_registry_backfilled_into_module(self) -> None:
        import quadkit.cache.service.registry as reg_mod
        from quadkit.cache.service.registry import CacheStatusRegistry

        p = _provider()
        reg = _Registrar()
        await p.register(reg)  # type: ignore[arg-type]
        # The module-level singleton must point at the container-managed
        # instance after back-fill.
        assert reg_mod._registry is reg.singletons[CacheStatusRegistry]["instance"]  # noqa: SLF001


class TestNamedBindings:
    async def test_named_bindings_per_enabled_backend(self) -> None:
        p = _provider(
            [
                {"name": "primary", "type": "memory", "default": True},
                {"name": "aux", "type": "memory", "default": False, "enabled": False},
            ]
        )
        reg = _Registrar()
        await p.register(reg)  # type: ignore[arg-type]
        from quadkit.cache.service.core import CacheService
        from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol

        # Both named services are keyed by (service, name) in the real
        # registry, so both coexist under the same name.
        assert (CacheBackendProtocol, "primary") in reg.named
        assert (CacheService, "primary") in reg.named
        # Disabled backend must NOT be bound.
        assert not any(name == "aux" for _, name in reg.named)

    async def test_named_factories_resolve_backends(self) -> None:
        p = _provider([{"name": "primary", "type": "memory", "default": True}])
        reg = _Registrar()
        await p.register(reg)  # type: ignore[arg-type]
        # The default (unnamed) CacheBackendProtocol factory returns the
        # default backend once booted.  Without boot it raises — just verify
        # the factory is bound and callable.
        factory = reg.singletons[
            __import__("quadkit.contracts.infra.cache.protocols", fromlist=["CacheBackendProtocol"])
            .CacheBackendProtocol
        ]["factory"]
        assert callable(factory)


class TestRedisStateStore:
    async def test_redis_backend_gets_state_store_binding(self) -> None:
        p = _provider(
            [
                {
                    "name": "r1",
                    "type": "redis",
                    "default": True,
                    "redis_url": "redis://localhost:6379/0",
                }
            ]
        )
        reg = _Registrar()
        await p.register(reg)  # type: ignore[arg-type]
        assert "state_store.r1" in reg.string_keys
        assert reg.string_keys["state_store.r1"] is not None

    async def test_memory_backend_gets_no_state_store(self) -> None:
        p = _provider([{"name": "m1", "type": "memory", "default": True}])
        reg = _Registrar()
        await p.register(reg)  # type: ignore[arg-type]
        assert "state_store.m1" not in reg.string_keys


def _raw_provider() -> CacheProvider:
    """Provider WITHOUT the _discover_backends mock (discovery is under test)."""
    return CacheProvider(config=CacheConfig(backends=[]))


class TestDiscoverBackends:
    async def test_provider_entrypoints_registered(self) -> None:
        p = _raw_provider()
        reg = _Registrar()

        from quadkit.di.provider import Provider as _ProviderBase

        class _ThirdPartyBackend(_ProviderBase):
            name = "tp"

            async def register(self, container: Any) -> None:
                container.singleton("tp-backend", "tp")

        fake_ep = MagicMock()
        fake_ep.name = "tp"
        fake_ep.load.return_value = _ThirdPartyBackend

        with patch("importlib.metadata.entry_points", return_value=[fake_ep]):
            await p._discover_backends(reg)  # type: ignore[arg-type]  # noqa: SLF001
        assert reg.string_keys.get("tp-backend") == "tp"

    async def test_non_provider_entrypoint_skipped(self) -> None:
        p = _raw_provider()
        reg = _Registrar()
        fake_ep = MagicMock()
        fake_ep.name = "not-a-provider"
        fake_ep.load.return_value = "a string, not a class"

        with patch("importlib.metadata.entry_points", return_value=[fake_ep]):
            await p._discover_backends(reg)  # type: ignore[arg-type]  # noqa: SLF001
        assert reg.singletons == {}
        assert reg.string_keys == {}
        assert reg.string_keys == {}

    async def test_failing_entrypoint_logged_and_skipped(self) -> None:
        p = _raw_provider()
        reg = _Registrar()
        fake_ep = MagicMock()
        fake_ep.name = "broken"

        def boom() -> Any:
            raise ImportError("no module")

        fake_ep.load.side_effect = boom
        with patch("importlib.metadata.entry_points", return_value=[fake_ep]):
            await p._discover_backends(reg)  # type: ignore[arg-type]  # noqa: SLF001
        assert reg.singletons == {}
        assert reg.string_keys == {}
        assert reg.string_keys == {}


class TestSemanticCache:
    async def test_skipped_when_faiss_missing(self) -> None:
        p = _provider()
        with patch.object(
            type(p), "_faiss_available", return_value=False
        ) as mock_faiss:
            reg = _Registrar()
            p._register_semantic_cache(reg)  # type: ignore[arg-type]  # noqa: SLF001
        mock_faiss.assert_called_once()

    async def test_skipped_when_no_embedding_client(self) -> None:
        p = _provider()
        with (
            patch.object(type(p), "_faiss_available", return_value=True),
        ):
            reg = _Registrar()  # has() returns False → skip
            p._register_semantic_cache(reg)  # type: ignore[arg-type]  # noqa: SLF001

    def test_faiss_available_false_without_package(self) -> None:
        with patch.dict("sys.modules", {"faiss": None}):
            assert CacheProvider._faiss_available() is False


class TestAdminComponents:
    async def test_admin_contributor_registered(self) -> None:
        p = _provider()
        reg = _Registrar()
        await p.register(reg)  # type: ignore[arg-type]
        from quadkit.cache.admin.contributor import CacheAdminContributor

        assert CacheAdminContributor in reg.singletons
