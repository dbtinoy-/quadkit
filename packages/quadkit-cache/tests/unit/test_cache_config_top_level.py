"""Tests for the top-level CacheConfig (validators, lookups, helpers)."""

from __future__ import annotations

import pytest

from quadkit.cache.config import resolve_backend_type
from quadkit.cache.config.top_level import CacheConfig, make_cache_config
from quadkit.cache.types import BackendType
from quadkit.contracts.core.config import Environment


def _redis_backend(name: str = "r", **kw: object) -> dict:
    base = {
        "name": name,
        "type": "redis",
        "default": kw.pop("default", False),
        "redis_password": kw.pop("redis_password", None),
        "redis_url": kw.pop("redis_url", None),
    }
    base.update(kw)
    return base


class TestDefaults:
    def test_defaults(self) -> None:
        cfg = CacheConfig()
        assert cfg.name == "cache"
        assert cfg.enabled is True
        assert cfg.debug is False
        assert cfg.backends == []
        assert cfg.env is None
        assert cfg.service is not None

    def test_config_section(self) -> None:
        assert CacheConfig.config_section == "cache"

    def test_make_cache_config_helper(self) -> None:
        cfg = make_cache_config(name="custom", enabled=False)
        assert cfg.name == "custom"
        assert cfg.enabled is False

    def test_get_provider_class(self) -> None:
        from quadkit.cache import CacheProvider

        assert CacheConfig.get_provider_class() is CacheProvider


class TestBackendValidators:
    def test_no_backends_ok(self) -> None:
        cfg = CacheConfig(backends=[])
        assert cfg.backends == []

    def test_exactly_one_default_required(self) -> None:
        with pytest.raises(ValueError, match="Exactly one backend"):
            CacheConfig(
                backends=[
                    _redis_backend("a", default=False),
                    _redis_backend("b", default=False),
                ]
            )
        with pytest.raises(ValueError, match="Exactly one backend"):
            CacheConfig(
                backends=[
                    _redis_backend("a", default=True),
                    _redis_backend("b", default=True),
                ]
            )

    def test_unique_names_required(self) -> None:
        with pytest.raises(ValueError, match="names must be unique"):
            CacheConfig(
                backends=[
                    _redis_backend("same", default=True),
                    _redis_backend("same", default=False),
                ]
            )

    def test_valid_multi_backend(self) -> None:
        cfg = CacheConfig(
            backends=[
                _redis_backend("primary", default=True),
                {"name": "local", "type": "memory", "default": False},
            ]
        )
        assert len(cfg.backends) == 2


class TestProductionSecurity:
    def test_insecure_password_blocked_in_production(self) -> None:
        with pytest.raises(ValueError, match="Insecure Redis password"):
            CacheConfig(
                env=Environment.PRODUCTION,
                backends=[_redis_backend("r", default=True, redis_password="password")],
            )

    def test_insecure_url_credential_blocked_in_production(self) -> None:
        with pytest.raises(ValueError, match="Insecure"):
            CacheConfig(
                env=Environment.PRODUCTION,
                backends=[
                    _redis_backend(
                        "r", default=True, redis_url="redis://user:123456@host:6379/0"
                    )
                ],
            )

    def test_secure_password_allowed_in_production(self) -> None:
        cfg = CacheConfig(
            env=Environment.PRODUCTION,
            backends=[_redis_backend("r", default=True, redis_password="s3cure-xyz")],
        )
        assert cfg.get_default_backend() is not None

    def test_insecure_password_allowed_outside_production(self) -> None:
        cfg = CacheConfig(
            env=Environment.DEVELOPMENT,
            backends=[_redis_backend("r", default=True, redis_password="password")],
        )
        assert cfg.get_default_backend() is not None

    def test_non_redis_backends_not_checked(self) -> None:
        cfg = CacheConfig(
            env=Environment.PRODUCTION,
            backends=[{"name": "m", "type": "memory", "default": True}],
        )
        assert cfg.get_default_backend() is not None


class TestLookups:
    def _cfg(self) -> CacheConfig:
        return CacheConfig(
            backends=[
                _redis_backend("primary", default=True),
                {"name": "local", "type": "memory", "default": False},
            ]
        )

    def test_get_default_backend(self) -> None:
        cfg = self._cfg()
        default = cfg.get_default_backend()
        assert default is not None
        assert default.name == "primary"

    def test_get_default_backend_none(self) -> None:
        assert CacheConfig().get_default_backend() is None

    def test_get_backend_by_name(self) -> None:
        cfg = self._cfg()
        assert cfg.get_backend("local").name == "local"  # type: ignore[union-attr]
        assert cfg.get_backend("missing") is None

    def test_backend_type_resolution(self) -> None:
        cfg = self._cfg()
        default = cfg.get_default_backend()
        assert resolve_backend_type(default) is BackendType.REDIS
