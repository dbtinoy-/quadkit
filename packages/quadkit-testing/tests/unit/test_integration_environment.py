"""Unit tests for IntegrationEnvironment.

These tests operate without real database or cache processes by either:
- Testing constructor / config-merge logic directly (no provider calls), or
- Patching sys.modules to simulate missing extension packages for the ImportError paths.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest import mock

import pytest

from quadkit.testing import IntegrationEnvironment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DB_PROVIDER_MODULE = "quadkit.sql.di.provider"
_CACHE_PROVIDER_MODULE = "quadkit.cache.di.provider"


def _make_mock_provider() -> mock.MagicMock:
    """Return a mock that acts like a provider instance."""
    return mock.MagicMock()


def _make_mock_provider_class(instance: mock.MagicMock) -> mock.MagicMock:
    """Return a mock provider class whose constructor returns *instance*."""
    cls = mock.MagicMock()
    cls.return_value = instance
    return cls


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestIntegrationEnvironmentConstructor:
    def test_default_name(self) -> None:
        env = IntegrationEnvironment()
        assert env.name == "integration-test"

    def test_custom_name(self) -> None:
        env = IntegrationEnvironment(name="my-env")
        assert env.name == "my-env"

    def test_default_config_overrides_is_empty(self) -> None:
        env = IntegrationEnvironment()
        assert env._config_overrides == {}

    def test_config_kwarg_populates_overrides(self) -> None:
        env = IntegrationEnvironment(config={"cache.backend": "redis"})
        assert env._config_overrides == {"cache.backend": "redis"}

    def test_none_config_leaves_overrides_empty(self) -> None:
        env = IntegrationEnvironment(config=None)
        assert env._config_overrides == {}


# ---------------------------------------------------------------------------
# with_database — config merge
# ---------------------------------------------------------------------------


class TestWithDatabase:
    def _patch_db(self) -> tuple[mock.MagicMock, dict[str, Any]]:
        """Inject a fake DatabaseProvider and return (provider_instance, modules_patch)."""
        provider_instance = _make_mock_provider()
        provider_class = _make_mock_provider_class(provider_instance)
        fake_module = mock.MagicMock()
        fake_module.DatabaseProvider = provider_class
        return provider_instance, {_DB_PROVIDER_MODULE: fake_module}

    def test_default_url_stored_in_config_overrides(self) -> None:
        _, modules = self._patch_db()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_database()
        assert env._config_overrides["database.url"] == "sqlite+aiosqlite:///:memory:"

    def test_custom_url_stored_in_config_overrides(self) -> None:
        _, modules = self._patch_db()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_database(
                url="postgresql+asyncpg://localhost/test"
            )
        assert (
            env._config_overrides["database.url"]
            == "postgresql+asyncpg://localhost/test"
        )

    def test_extra_config_merged(self) -> None:
        _, modules = self._patch_db()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_database(
                config={"db.pool_size": 10},
            )
        assert env._config_overrides["database.url"] == "sqlite+aiosqlite:///:memory:"
        assert env._config_overrides["db.pool_size"] == 10

    def test_extra_config_overrides_url_when_specified(self) -> None:
        _, modules = self._patch_db()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_database(
                config={"database.url": "postgresql+asyncpg://override/db"},
            )
        assert (
            env._config_overrides["database.url"] == "postgresql+asyncpg://override/db"
        )

    def test_default_name_passed_through(self) -> None:
        _, modules = self._patch_db()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_database()
        assert env.name == "integration-test"

    def test_custom_name_passed_through(self) -> None:
        _, modules = self._patch_db()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_database(name="db-test")
        assert env.name == "db-test"

    def test_provider_registered(self) -> None:
        provider_instance, modules = self._patch_db()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_database()
        assert provider_instance in env.providers.values()

    def test_raises_import_error_when_package_missing(self) -> None:
        with mock.patch.dict(sys.modules, {_DB_PROVIDER_MODULE: None}):
            with pytest.raises(ImportError, match="quadkit-sql is required"):
                IntegrationEnvironment.with_database()


# ---------------------------------------------------------------------------
# with_cache — config merge
# ---------------------------------------------------------------------------


class TestWithCache:
    def _patch_cache(self) -> tuple[mock.MagicMock, dict[str, Any]]:
        provider_instance = _make_mock_provider()
        provider_class = _make_mock_provider_class(provider_instance)
        fake_module = mock.MagicMock()
        fake_module.CacheProvider = provider_class
        return provider_instance, {_CACHE_PROVIDER_MODULE: fake_module}

    def test_default_backend_memory(self) -> None:
        _, modules = self._patch_cache()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_cache()
        assert env._config_overrides["cache.backend"] == "memory"

    def test_custom_backend(self) -> None:
        _, modules = self._patch_cache()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_cache(backend="redis")
        assert env._config_overrides["cache.backend"] == "redis"

    def test_url_included_when_provided(self) -> None:
        _, modules = self._patch_cache()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_cache(
                backend="redis", url="redis://localhost:6379/0"
            )
        assert env._config_overrides["cache.url"] == "redis://localhost:6379/0"

    def test_url_omitted_for_memory_backend(self) -> None:
        _, modules = self._patch_cache()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_cache(backend="memory")
        assert "cache.url" not in env._config_overrides

    def test_extra_config_merged(self) -> None:
        _, modules = self._patch_cache()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_cache(config={"cache.ttl": 300})
        assert env._config_overrides["cache.ttl"] == 300

    def test_provider_registered(self) -> None:
        provider_instance, modules = self._patch_cache()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_cache()
        assert provider_instance in env.providers.values()

    def test_raises_import_error_when_package_missing(self) -> None:
        with mock.patch.dict(sys.modules, {_CACHE_PROVIDER_MODULE: None}):
            with pytest.raises(ImportError, match="quadkit-cache is required"):
                IntegrationEnvironment.with_cache()


# ---------------------------------------------------------------------------
# with_all — combined config merge
# ---------------------------------------------------------------------------


class TestWithAll:
    def _patch_both(self) -> dict[str, Any]:
        db_provider = _make_mock_provider()
        db_cls = _make_mock_provider_class(db_provider)
        db_module = mock.MagicMock()
        db_module.DatabaseProvider = db_cls

        cache_provider = _make_mock_provider()
        cache_cls = _make_mock_provider_class(cache_provider)
        cache_module = mock.MagicMock()
        cache_module.CacheProvider = cache_cls

        return {
            _DB_PROVIDER_MODULE: db_module,
            _CACHE_PROVIDER_MODULE: cache_module,
        }

    def test_defaults_include_both_keys(self) -> None:
        modules = self._patch_both()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_all()
        assert "database.url" in env._config_overrides
        assert "cache.backend" in env._config_overrides

    def test_default_database_url(self) -> None:
        modules = self._patch_both()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_all()
        assert env._config_overrides["database.url"] == "sqlite+aiosqlite:///:memory:"

    def test_default_cache_backend_memory(self) -> None:
        modules = self._patch_both()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_all()
        assert env._config_overrides["cache.backend"] == "memory"

    def test_custom_database_url(self) -> None:
        modules = self._patch_both()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_all(
                database_url="postgresql+asyncpg://localhost/testdb",
            )
        assert (
            env._config_overrides["database.url"]
            == "postgresql+asyncpg://localhost/testdb"
        )

    def test_cache_url_included_when_given(self) -> None:
        modules = self._patch_both()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_all(
                cache_backend="redis",
                cache_url="redis://localhost/1",
            )
        assert env._config_overrides["cache.url"] == "redis://localhost/1"

    def test_cache_url_absent_by_default(self) -> None:
        modules = self._patch_both()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_all()
        assert "cache.url" not in env._config_overrides

    def test_extra_config_merged(self) -> None:
        modules = self._patch_both()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_all(config={"app.env": "test"})
        assert env._config_overrides["app.env"] == "test"

    def test_two_providers_registered(self) -> None:
        modules = self._patch_both()
        with mock.patch.dict(sys.modules, modules):
            env = IntegrationEnvironment.with_all()
        assert len(env.providers) == 2

    def test_raises_when_db_missing(self) -> None:
        modules = self._patch_both()
        modules[_DB_PROVIDER_MODULE] = None  # hide db package
        with mock.patch.dict(sys.modules, modules):
            with pytest.raises(ImportError, match="quadkit-sql is required"):
                IntegrationEnvironment.with_all()

    def test_raises_when_cache_missing(self) -> None:
        modules = self._patch_both()
        modules[_CACHE_PROVIDER_MODULE] = None  # hide cache package
        with mock.patch.dict(sys.modules, modules):
            with pytest.raises(ImportError, match="quadkit-cache is required"):
                IntegrationEnvironment.with_all()


# ---------------------------------------------------------------------------
# setup() — FakeConfig injection
# ---------------------------------------------------------------------------


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup_without_overrides_does_not_inject_config(self) -> None:
        env = IntegrationEnvironment()
        await env.setup()
        # No crash; no FakeConfig registered (nothing to assert beyond no error)

    @pytest.mark.asyncio
    async def test_setup_injects_fake_config_when_overrides_present(self) -> None:
        from quadkit.testing.fakes import FakeConfig

        # Use a nested dict so dotted key traversal in FakeConfig.get() works.
        env = IntegrationEnvironment(config={"some": {"key": "value"}})
        await env.setup()
        # FakeConfig should be resolvable from the environment's async resolve helper
        resolved = await env.resolve(FakeConfig)
        assert isinstance(resolved, FakeConfig)
        assert resolved.get("some.key") == "value"

    @pytest.mark.asyncio
    async def test_context_manager_enters_and_exits_cleanly(self) -> None:
        env = IntegrationEnvironment(config={"key": "val"})
        async with env as e:
            assert e is env
            assert env.app is not None
