"""Integration test environment.

Unlike :class:`~quadkit.testing.fixtures.bed.TestEnvironment`, which
defaults to fakes and is designed for fast unit tests, ``IntegrationEnvironment``
defaults to real providers and controlled configuration.  Fakes are only
registered when you explicitly call :meth:`~TestEnvironment.fake` or
:meth:`~TestEnvironment.override`.

Typical use-case: integration tests that need one or more real backing services
(database, cache, message broker) but still want the rest of the framework
wired up correctly.

Example::

    # In-memory SQLite + real ORM, everything else is fakes
    async with IntegrationEnvironment.with_database() as env:
        repo = await env.resolve(UserRepository)
        result = await repo.find_by_email("test@example.com")
        assert result.is_err()  # Table is empty

    # Real Redis cache, everything else is fakes
    @requires_redis
    async def test_redis_cache_roundtrip():
        async with IntegrationEnvironment.with_cache(backend="redis") as env:
            cache = await env.resolve(CacheService)
            await cache.set("k", "v", ttl=10)
            value = await cache.get("k")
            assert value == "v"
"""

from __future__ import annotations

from typing import Any, Self

from quadkit.testing.fixtures.bed import TestEnvironment

__all__ = ["IntegrationEnvironment"]


class IntegrationEnvironment(TestEnvironment):
    """A :class:`~quadkit.testing.fixtures.bed.TestEnvironment` pre-configured
    for integration tests.

    Inherits the full ``TestEnvironment`` API (``use_provider``, ``fake``,
    ``override``, ``resolve``, async context-manager) and adds:

    - :meth:`with_database` — boots a real database provider (defaults to
      SQLite in-memory so tests don't need an external process).
    - :meth:`with_cache` — boots a real cache provider (defaults to the
      in-memory cache backend so tests can run without Redis).
    - :meth:`with_all` — combines database + cache in one call.
    - Config override shortcut via ``config=`` constructor argument.

    None of the factory methods import the provider packages at class
    definition time — they use lazy imports so the test can collect and skip
    cleanly when a package isn't installed.
    """

    def __init__(
        self,
        name: str = "integration-test",
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name)
        self._config_overrides: dict[str, Any] = config or {}

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def with_database(
        cls,
        url: str = "sqlite+aiosqlite:///:memory:",
        *,
        name: str = "integration-test",
        config: dict[str, Any] | None = None,
    ) -> IntegrationEnvironment:
        """Return an environment wired with a real database provider.

        Args:
            url: Database URL.  Defaults to an in-memory SQLite database so
                 tests run without any external process.
            name: Environment name shown in log output.
            config: Additional config overrides (merged with the database URL).

        Returns:
            An ``IntegrationEnvironment`` with the database provider registered.

        Raises:
            ImportError: If ``quadkit-sql`` is not installed.
        """
        try:
            from quadkit.sql.di.provider import (
                DatabaseProvider,
            )
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "quadkit-sql is required for IntegrationEnvironment.with_database(). "
                "Install it with: uv add quadkit-sql"
            ) from exc

        merged: dict[str, Any] = {"database.url": url}
        if config:
            merged.update(config)

        env = cls(name=name, config=merged)
        env.use_provider(DatabaseProvider())
        return env

    @classmethod
    def with_cache(
        cls,
        backend: str = "memory",
        *,
        url: str | None = None,
        name: str = "integration-test",
        config: dict[str, Any] | None = None,
    ) -> IntegrationEnvironment:
        """Return an environment wired with a real cache provider.

        Args:
            backend: Backend type — ``"memory"`` (default), ``"redis"``,
                     or ``"memcached"``.
            url: Backend connection URL (required for Redis / Memcached;
                 omit for the in-memory backend).
            name: Environment name.
            config: Additional config overrides.

        Returns:
            An ``IntegrationEnvironment`` with the cache provider registered.

        Raises:
            ImportError: If ``quadkit-cache`` is not installed.
        """
        try:
            from quadkit.cache.di.provider import (
                CacheProvider,
            )
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "quadkit-cache is required for IntegrationEnvironment.with_cache(). "
                "Install it with: uv add quadkit-cache"
            ) from exc

        merged: dict[str, Any] = {"cache.backend": backend}
        if url:
            merged["cache.url"] = url
        if config:
            merged.update(config)

        env = cls(name=name, config=merged)
        env.use_provider(CacheProvider())
        return env

    @classmethod
    def with_all(
        cls,
        *,
        database_url: str = "sqlite+aiosqlite:///:memory:",
        cache_backend: str = "memory",
        cache_url: str | None = None,
        name: str = "integration-test",
        config: dict[str, Any] | None = None,
    ) -> IntegrationEnvironment:
        """Return an environment with both database and cache providers.

        This is a convenience factory combining :meth:`with_database` and
        :meth:`with_cache`.  Both providers are registered before the
        environment is returned.

        Args:
            database_url: Passed to :meth:`with_database`.
            cache_backend: Passed to :meth:`with_cache`.
            cache_url: Passed to :meth:`with_cache`.
            name: Environment name.
            config: Additional config overrides.

        Raises:
            ImportError: If any required extension package is missing.
        """
        try:
            from quadkit.sql.di.provider import (
                DatabaseProvider,
            )
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "quadkit-sql is required for IntegrationEnvironment.with_all(). "
                "Install it with: uv add quadkit-sql"
            ) from exc

        try:
            from quadkit.cache.di.provider import (
                CacheProvider,
            )
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "quadkit-cache is required for IntegrationEnvironment.with_all(). "
                "Install it with: uv add quadkit-cache"
            ) from exc

        merged: dict[str, Any] = {
            "database.url": database_url,
            "cache.backend": cache_backend,
        }
        if cache_url:
            merged["cache.url"] = cache_url
        if config:
            merged.update(config)

        env = cls(name=name, config=merged)
        env.use_provider(DatabaseProvider())
        env.use_provider(CacheProvider())
        return env

    # ------------------------------------------------------------------
    # Config support
    # ------------------------------------------------------------------

    async def setup(self) -> Any:
        """Set up the environment, injecting FakeConfig for config overrides.

        If ``config`` was passed to the constructor, it is registered as an
        override *before* the application boots so that it lands in the
        container before it is frozen.  The override is keyed by
        ``ConfigProtocol`` when available, falling back to the ``FakeConfig``
        class itself.
        """
        if self._config_overrides:
            from quadkit.testing.fakes import FakeConfig

            fake_cfg = FakeConfig(self._config_overrides)
            from quadkit.contracts.core.config import (
                ConfigProtocol,
            )

            # Register override under the protocol key and the concrete class
            self.override(ConfigProtocol, fake_cfg)
            self.override(FakeConfig, fake_cfg)

        return await super().setup()

    # ------------------------------------------------------------------
    # Async context-manager — return Self so type checkers stay happy
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        await self.setup()
        return self
