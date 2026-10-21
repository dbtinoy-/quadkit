"""Public registration of the SQL admin widget handlers.

``SqlAdminContributor`` resolves its three widget handlers from the DI
container in ``on_admin_boot``. The contributor itself is discovered through
the ``the optional provider module`` entry-point group, so it mounts in *any*
application that installs ``quadkit-sql`` — including applications that own
their database provider instead of using
:class:`~quadkit.sql.di.provider.DatabaseProvider`. Those applications still
have to register the handlers, or the contributor boots into a
``UnresolvableDependencyError`` and the Database widgets render nothing.

This module owns that registration so it lives in exactly one place: the
framework provider delegates to it, and applications with their own provider
call it directly.

Example:
    ```python
    from quadkit.sql.admin.registration import register_admin_widget_handlers

    register_admin_widget_handlers(container, db=my_database_provider)
    ```
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover — typing only
    from quadkit.contracts.core.di import ContainerRegistrarProtocol

logger = get_logger(__name__)


def register_admin_widget_handlers(
    container: ContainerRegistrarProtocol,
    *,
    db: Any = None,
    migration_manager: Any = None,
    migration_runner: Any = None,
) -> None:
    """Register the SQL admin widget handlers as container singletons.

    Args:
        container: DI registrar to bind the handlers into.
        db: Database provider exposing ``get_primary_pool()``. ``None`` is
            accepted — the pool widgets then report ``Unavailable`` instead of
            failing, which is the honest answer when no pool is wired.
        migration_manager: Migration manager behind the migration-status
            widget. ``None`` renders the widget as unavailable.
        migration_runner: Optional runner used to compute pending migrations.
    """
    from quadkit.sql.admin.handlers.migration_status import (
        MigrationStatusWidgetHandler,
    )
    from quadkit.sql.admin.handlers.pool_utilization import (
        PoolUtilizationWidgetHandler,
    )
    from quadkit.sql.admin.handlers.query_stats import QueryStatsWidgetHandler

    container.singleton(
        PoolUtilizationWidgetHandler,
        lambda: PoolUtilizationWidgetHandler(db=db),
    )
    container.singleton(
        QueryStatsWidgetHandler,
        lambda: QueryStatsWidgetHandler(db=db),
    )
    container.singleton(
        MigrationStatusWidgetHandler,
        lambda: MigrationStatusWidgetHandler(
            migration_manager=migration_manager,
            migration_runner=migration_runner,
        ),
    )
    logger.info(
        "sql.admin_widgets_registered",
        pool_widgets=db is not None,
        migration_widget=migration_manager is not None,
    )


__all__ = ["register_admin_widget_handlers"]
