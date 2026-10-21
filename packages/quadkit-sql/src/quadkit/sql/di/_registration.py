"""Registration-phase methods for DatabaseProvider."""

from __future__ import annotations

from collections.abc import Callable
import inspect
from pathlib import Path
from typing import Any, cast

from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.logging import get_logger
from quadkit.sql.config import DatabaseConfig
from quadkit.sql.migrations.manager import SimpleMigrationManager
from quadkit.sql.providers.database_service import DatabaseService

logger = get_logger(__name__)
_alembic_warned = [False]


class _DatabaseRegistrationMixin:
    """Mixin holding DI-registration logic."""

    config: Any
    _explicit_config: DatabaseConfig | None
    _backends: dict[str, Any]
    _primary_backend: str | None
    _db_provider: DatabaseService
    _enable_migrations: bool | None
    _register_admin_widgets: Callable[..., Any]
    _migration_dir: str | Path

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register all database services (singletons/scoped) into the container."""
        # Resolve effective config: explicit arg → auto-injected → sqlite default
        effective_config: DatabaseConfig
        if self._explicit_config is not None:
            effective_config = self._explicit_config
        elif isinstance(getattr(self, "config", None), DatabaseConfig):
            effective_config = self.config
        else:
            effective_config = DatabaseConfig()

        # Store as instance attr so remaining methods can reference self._config
        self._config = effective_config

        # Resolve optional dependencies
        id_generator: Any = None
        tracer: Any = None
        metrics: Any = None

        resolve_optional = getattr(container, "resolve_optional", None)
        if callable(resolve_optional):
            from quadkit.contracts.core.identity import IdGeneratorProtocol
            from quadkit.contracts.observability.metrics import (
                MetricsCollectorProtocol,
            )
            from quadkit.contracts.observability.tracing import TracerProtocol

            try:
                maybe_id_gen = resolve_optional(IdGeneratorProtocol)
                maybe_id_gen = (
                    await maybe_id_gen
                    if inspect.isawaitable(maybe_id_gen)
                    else maybe_id_gen
                )
                if maybe_id_gen is not None:
                    id_generator = maybe_id_gen
            except Exception:  # noqa: S110 — intentional best-effort fallback
                pass

            try:
                maybe_tracer = resolve_optional(TracerProtocol)
                maybe_tracer = (
                    await maybe_tracer
                    if inspect.isawaitable(maybe_tracer)
                    else maybe_tracer
                )
                if maybe_tracer is not None:
                    tracer = maybe_tracer
            except Exception:  # noqa: S110 — intentional best-effort fallback
                pass

            try:
                maybe_metrics = resolve_optional(MetricsCollectorProtocol)
                maybe_metrics = (
                    await maybe_metrics
                    if inspect.isawaitable(maybe_metrics)
                    else maybe_metrics
                )
                if maybe_metrics is not None:
                    metrics = maybe_metrics
            except Exception:  # noqa: S110 — intentional best-effort fallback
                pass

        self._clock = None  # Now using ambient clock
        self._id_generator = id_generator
        self._tracer = tracer
        self._metrics = metrics

        # Register data-layer config and query compiler
        from quadkit.sql.config import DataConfig
        from quadkit.sql.query.compiler import PredicateCompiler

        container.singleton(DataConfig, instance=DataConfig())
        container.singleton(PredicateCompiler, instance=PredicateCompiler())

        if effective_config.backends:
            await self._register_multi_backend(container, effective_config)
        else:
            await self._register_single_backend(container, effective_config)

        # Register admin widget services
        self._register_admin_widgets(container)

    def _make_session_factory(self, name: str, backend: Any) -> Any:
        """Build (once) the ORM session factory for one backend.

        Memoised so repeated resolution shares the engine rather than
        quietly opening another pool — which is the very problem this
        feature exists to remove.
        """
        from quadkit.sql.orm.session import SessionFactory

        existing = self._session_factories.get(name)
        if existing is not None:
            return existing
        factory = SessionFactory(
            backend.url.get_secret_value(),
            echo=bool(getattr(backend, "echo", False)),
        )
        self._session_factories[name] = factory
        return factory

    async def _register_single_backend(
        self,
        container: ContainerRegistrarProtocol,
        config: DatabaseConfig,
    ) -> None:
        """Register a single database backend (existing behavior, preserved exactly)."""
        from quadkit.contracts import (
            ConnectionPoolProtocol,
            DatabaseProviderProtocol,
            MigrationManagerProtocol,
            QueryLoggerProtocol,
            UnitOfWorkProtocol,
        )
        from quadkit.sql.orm.session import SessionFactory

        self._db_provider = self._db_provider or DatabaseService(
            config, clock=self._clock, id_generator=self._id_generator
        )
        container.singleton(DatabaseService, self._db_provider)
        container.singleton(DatabaseProviderProtocol, self._db_provider)

        # ORM session factory: one engine and one pool shared with the raw
        # providers, so an application mapping declarative models does not
        # build a second engine against the same database
        # (Improve-QuadKit #1).
        #
        # Registered as a FACTORY, not an instance: the engine is built
        # only if something resolves it. Building eagerly would also fail
        # for apps configured with a sync driver (`sqlite://` rather than
        # `sqlite+aiosqlite://`), which use the raw providers happily and
        # never ask for an ORM session.
        container.singleton(
            SessionFactory,
            factory=lambda: self._make_session_factory("default", config.backend),
        )

        # Protocol bindings for optional collaborators
        container.singleton(
            ConnectionPoolProtocol,
            lambda: self._db_provider.connection_pool,
        )
        container.singleton(
            QueryLoggerProtocol,
            lambda: self._db_provider.query_logger,
        )

        if self._db_provider.migration_manager:
            container.singleton(
                MigrationManagerProtocol,
                lambda: self._db_provider.migration_manager,
            )

        # High-level MigrationRunnerProtocol — used by the CLI and other consumers
        # that want to run/rollback migrations without importing quadkit-sql internals.
        from quadkit.contracts.data.sql.migrations import MigrationRunnerProtocol
        from quadkit.sql.migrations.runner import MigrationRunnerAdapter

        _migration_runner_factory = lambda: MigrationRunnerAdapter(  # noqa: E731
            cast(
                "SimpleMigrationManager",
                self._db_provider.migration_manager,
            )
        )
        container.singleton(MigrationRunnerProtocol, _migration_runner_factory)

        # Scoped unit-of-work
        container.scoped(UnitOfWorkProtocol, self._db_provider.get_unit_of_work)  # type: ignore[type-abstract]

        self._register_shared_stores(container, self._db_provider)

        # Register migration manager if alembic is available
        try:
            from quadkit.sql.migrations.api import AlembicManager

            # Unwrap SecretStr only at the driver call site — never store plain URL
            raw_url = config.backend.url if hasattr(config, "backend") else config.url  # type: ignore[attr-defined]
            migration_url = (
                raw_url.get_secret_value()
                if hasattr(raw_url, "get_secret_value")
                else str(raw_url)
            )
            migration_manager = AlembicManager(migration_url, self._migration_dir)
            container.singleton(AlembicManager, migration_manager)
            if self._enable_migrations:
                self._db_provider.migration_manager = migration_manager
        except ImportError:
            from quadkit.sql.di.provider import _warn_alembic_missing  # noqa: PLC0415

            _warn_alembic_missing()

        # Database-backed search backends have moved to the optional provider
        # (`the optional provider module` / `the optional provider module`).
        # SearchProvider is responsible for
        # resolving DatabaseProviderProtocol from the container and registering
        # the appropriate DatabaseSearchBackendProtocol singleton.  DatabaseProvider
        # no longer imports from quadkit.sql.search to keep the package boundary clean.

    async def _register_multi_backend(
        self,
        container: ContainerRegistrarProtocol,
        config: DatabaseConfig,
    ) -> None:
        """Register multiple named database backends.

        Each backend in ``config.backends`` is registered under its name via
        ``container.singleton(name=entry.name)``, resolvable through
        ``Annotated[DatabaseProviderProtocol, Named(name)]``.  The primary
        backend (``primary=True`` or the first entry) also receives unnamed
        bindings for backward compatibility.
        """
        from quadkit.contracts import (
            ConnectionPoolProtocol,
            DatabaseProviderProtocol,
            QueryLoggerProtocol,
            UnitOfWorkProtocol,
        )
        from quadkit.sql.orm.session import SessionFactory

        backends = config.backends
        primary_entry = next((b for b in backends if b.primary), backends[0])

        self._db_services = []
        self._session_factories: dict[str, Any] = {}
        primary_svc: Any = None
        primary_factory: Any = None

        for entry in backends:
            db_cfg = DatabaseConfig.from_named(entry, base=config)
            db_svc = DatabaseService(
                db_cfg, clock=self._clock, id_generator=self._id_generator
            )
            # Track backend service for parallel boot/shutdown/health coordination
            self._db_services.append((entry.name, db_svc))

            # Named registration — resolvable via Annotated[T, Named(entry.name)]
            container.singleton(
                DatabaseProviderProtocol,
                name=entry.name,
                instance=db_svc,
            )
            container.singleton(
                DatabaseService,
                name=entry.name,
                instance=db_svc,
            )

            # Named protocol bindings — each backend resolves via Annotated[T, Named(entry.name)]
            _svc = db_svc  # capture per-iteration for closure correctness
            container.scoped(
                UnitOfWorkProtocol,  # type: ignore[type-abstract]
                _svc.get_unit_of_work,
                name=f"{entry.name}:uow",
            )
            container.singleton(
                ConnectionPoolProtocol,
                lambda svc=_svc: svc.connection_pool,
                name=f"{entry.name}:pool",
            )
            container.singleton(
                QueryLoggerProtocol,
                lambda svc=_svc: svc.query_logger,
                name=f"{entry.name}:logger",
            )

            # Register named migration runner for backends that declare a migration_dir
            if entry.migration_dir:
                self._register_migration_runner(
                    container, db_svc, entry.migration_dir, name=entry.name
                )

            # ORM session factory: one engine and one pool per backend, so
            # an application mapping declarative models does not build a
            # second engine against the same database (Improve-QuadKit #1).
            # Engine construction is lazy — no connection is opened here.
            container.singleton(
                SessionFactory,
                name=entry.name,
                factory=lambda e=entry: self._make_session_factory(e.name, e.backend),
            )

            if entry.name == primary_entry.name:
                primary_svc = db_svc
                primary_factory = entry

        # Primary backend also gets the unnamed bindings (backward compat)
        self._db_provider = primary_svc
        container.singleton(DatabaseProviderProtocol, instance=primary_svc)
        container.singleton(DatabaseService, instance=primary_svc)
        if primary_factory is not None:
            container.singleton(
                SessionFactory,
                factory=lambda e=primary_factory: self._make_session_factory(
                    e.name, e.backend
                ),
            )

        container.scoped(UnitOfWorkProtocol, primary_svc.get_unit_of_work)  # type: ignore[type-abstract]

        container.singleton(
            ConnectionPoolProtocol,
            lambda: self._db_provider.connection_pool,
        )
        container.singleton(
            QueryLoggerProtocol,
            lambda: self._db_provider.query_logger,
        )

        # Shared stores (audit, state, secrets, locks) — always use primary
        self._register_shared_stores(container, primary_svc)

        # Unnamed migration runner for primary backend (backward compat — resolves without Named())
        if primary_entry.migration_dir:
            self._register_migration_runner(
                container, primary_svc, primary_entry.migration_dir
            )

    def _register_shared_stores(
        self,
        container: ContainerRegistrarProtocol,
        db_provider: Any,
    ) -> None:
        """Register shared database-backed stores: state, secrets, locks."""
        from quadkit.contracts.core.stores import LockStoreProtocol
        from quadkit.contracts.infra import StateStoreProtocol
        from quadkit.contracts.security.stores import AsyncSecretStoreProtocol
        from quadkit.sql.stores import (
            DatabaseLockStore,
            DatabaseSecretStore,
            DatabaseStateStore,
        )

        _db_ref = db_provider
        container.singleton(
            StateStoreProtocol,
            lambda: DatabaseStateStore(db_provider=_db_ref),
        )
        container.singleton(
            AsyncSecretStoreProtocol,
            lambda: DatabaseSecretStore(db_provider=_db_ref),
        )
        container.singleton(
            LockStoreProtocol,
            lambda: DatabaseLockStore(db_provider=_db_ref),
        )

    def _register_migration_runner(
        self,
        container: ContainerRegistrarProtocol,
        db_provider: Any,
        migration_dir: str,
        name: str | None = None,
    ) -> None:
        """Register migration runner for a database backend.

        Called for every backend that has ``migration_dir`` set (with ``name``),
        and again unnamed for the primary backend to preserve backward compatibility.
        """
        from quadkit.contracts import MigrationManagerProtocol
        from quadkit.contracts.data.sql.migrations import MigrationRunnerProtocol
        from quadkit.sql.migrations.runner import MigrationRunnerAdapter

        _db_ref = db_provider

        if db_provider.migration_manager:
            container.singleton(
                MigrationManagerProtocol,
                lambda: _db_ref.migration_manager,
                name=name,
            )

        _factory = lambda: MigrationRunnerAdapter(_db_ref.migration_manager)  # noqa: E731
        container.singleton(MigrationRunnerProtocol, _factory, name=name)

        try:
            from quadkit.sql.migrations.api import AlembicManager

            raw_url = _db_ref.config.backend.url
            migration_url = (
                raw_url.get_secret_value()
                if hasattr(raw_url, "get_secret_value")
                else str(raw_url)
            )
            migration_manager = AlembicManager(migration_url, migration_dir)
            container.singleton(AlembicManager, migration_manager, name=name)
            if self._enable_migrations:
                _db_ref.migration_manager = migration_manager
        except ImportError:
            from quadkit.sql.di.provider import _warn_alembic_missing  # noqa: PLC0415

            _warn_alembic_missing()
