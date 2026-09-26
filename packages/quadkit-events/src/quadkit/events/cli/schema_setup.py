"""Schema setup contributions for the quadkit-events package."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import SchemaSetupOutcome, SchemaSetupResult
from quadkit.contracts.data.sql.database import DatabaseProviderProtocol

_SAGA_TABLE = "saga_records"


async def ensure_saga_records(db: DatabaseProviderProtocol) -> SchemaSetupOutcome:
    """Ensure the ``saga_records`` table exists.

    Args:
        db: The database provider.

    Returns:
        Outcome reporting CREATED, ALREADY_PRESENT, or FAILED.
    """
    from quadkit.events.sagas.sql import SqlSagaStore

    try:
        existed = await db.table_exists(_SAGA_TABLE)
        await SqlSagaStore(db).initialize()
        return SchemaSetupOutcome(
            status=(
                SchemaSetupResult.ALREADY_PRESENT
                if existed
                else SchemaSetupResult.CREATED
            )
        )
    except Exception as exc:
        return SchemaSetupOutcome(status=SchemaSetupResult.FAILED, message=str(exc))
