"""Database module for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.data import DatabaseProviderProtocol, UnitOfWorkProtocol
from quadkit.di.module import DynamicModule, Module, module

if TYPE_CHECKING:
    from quadkit.sql.config import DatabaseConfig


@module()
class DatabaseModule(Module):
    """Async SQLAlchemy ORM: repositories, unit-of-work, migrations, and connection pooling.

    Registers :class:`~quadkit.contracts.data.DatabaseProviderProtocol` and
    :class:`~quadkit.contracts.data.UnitOfWorkProtocol` for constructor injection.

    Call :meth:`configure` to configure and register the full database infrastructure,
    or :meth:`stub` for an isolated setup with no external service dependencies.

    Usage::

        from quadkit.sql.config import DatabaseConfig

        @module(
            imports=[
                DatabaseModule.configure(
                    DatabaseConfig(url="postgresql+asyncpg://localhost/mydb")
                )
            ]
        )
        class AppModule(Module):
            pass

    Shorthand with a URL string::

        @module(
            imports=[DatabaseModule.configure("postgresql+asyncpg://localhost/mydb")]
        )
        class AppModule(Module):
            pass
    """

    @classmethod
    def configure(
        cls,
        config: DatabaseConfig | Any | None = None,
        migration_dir: str = "migrations",
        enable_migrations: bool = False,
        enable_query_logging: bool = False,
    ) -> DynamicModule:
        """Create a DatabaseModule with explicit configuration.

        Args:
            config: A :class:`~quadkit.sql.config.DatabaseConfig` instance,
                a database URL string, or ``None`` to resolve config from the
                container's ``ConfigProtocol`` at boot time.
            migration_dir: Path to the Alembic migrations directory relative to
                the project root.  Defaults to ``"migrations"``.
            enable_migrations: Run Alembic migrations automatically on boot.
                Defaults to ``False`` for safety in production deployments.
            enable_query_logging: Emit every SQL statement to the structured
                logger for debugging.  Defaults to ``False``; enable only in
                development environments.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.sql.di.provider import DatabaseProvider

        return DynamicModule(
            module=cls,
            providers=[
                DatabaseProvider(
                    config=config,
                    migration_dir=migration_dir,
                    enable_migrations=enable_migrations,
                )
            ],
            exports=[DatabaseProviderProtocol, UnitOfWorkProtocol],
        )

    @classmethod
    def scope(cls, *repositories: type) -> DynamicModule:  # type: ignore[override]
        """Scope repository classes into a feature module.

        Registers the given repository classes as providers and exports them
        for constructor injection within the feature.  The parent module graph
        must already include :meth:`DatabaseModule.configure` — this does
        **not** create a new database connection.

        Uses the anonymous token pattern so both ``configure()`` and
        ``scope()`` can coexist in the same compiled graph without a
        ``ModuleDuplicateError``.

        Example::

            @module(
                imports=[
                    DatabaseModule.configure(config),
                    DatabaseModule.scope(UserRepository, OrderRepository),
                ]
            )
            class UserFeatureModule(Module):
                pass

        Args:
            *repositories: Repository classes to register and export.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` scoped to this feature.
        """
        token = type(
            f"_{cls.__name__}Scope",
            (cls,),
            {"__quadkit_scope_of__": cls},
        )
        return DynamicModule(
            module=token,
            providers=list(repositories),
            exports=list(repositories),
        )

    @classmethod
    def stub(cls, config: DatabaseConfig | None = None) -> DynamicModule:
        """Create a DatabaseModule suitable for unit and integration testing.

        Uses an in-memory or minimal backend with no external service dependencies.

        Args:
            config: Optional :class:`~quadkit.sql.config.DatabaseConfig`
                override.  Uses safe in-memory defaults when ``None``.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.sql.di.provider import DatabaseProvider

        return DynamicModule(
            module=cls,
            providers=[DatabaseProvider(config=config)],
            exports=[DatabaseProviderProtocol, UnitOfWorkProtocol],
        )


__all__ = ["DatabaseModule"]
