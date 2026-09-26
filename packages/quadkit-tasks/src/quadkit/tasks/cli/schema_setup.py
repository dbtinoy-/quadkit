"""Schema setup contributions for the quadkit-tasks package."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import SchemaSetupOutcome, SchemaSetupResult
from quadkit.contracts.data.sql.database import DatabaseProviderProtocol

_SCHEDULED_JOBS_TABLE = "scheduled_jobs"
_WORKFLOW_STATES_TABLE = "workflow_states"


async def ensure_scheduled_jobs(db: DatabaseProviderProtocol) -> SchemaSetupOutcome:
    """Ensure the ``scheduled_jobs`` table exists.

    Args:
        db: The database provider.

    Returns:
        Outcome reporting CREATED, ALREADY_PRESENT, or FAILED.
    """
    from quadkit.tasks.scheduling.persistence import DatabaseSchedulerStore

    try:
        existed = await db.table_exists(_SCHEDULED_JOBS_TABLE)
        await DatabaseSchedulerStore(db)._ensure_table()
        return SchemaSetupOutcome(
            status=(
                SchemaSetupResult.ALREADY_PRESENT
                if existed
                else SchemaSetupResult.CREATED
            )
        )
    except Exception as exc:
        return SchemaSetupOutcome(status=SchemaSetupResult.FAILED, message=str(exc))


async def ensure_workflow_states(db: DatabaseProviderProtocol) -> SchemaSetupOutcome:
    """Ensure the ``workflow_states`` table exists.

    Args:
        db: The database provider.

    Returns:
        Outcome reporting CREATED, ALREADY_PRESENT, or FAILED.
    """
    from quadkit.tasks.workflows.state import DatabaseWorkflowStateStore

    try:
        existed = await db.table_exists(_WORKFLOW_STATES_TABLE)
        await DatabaseWorkflowStateStore(db)._ensure_table()
        return SchemaSetupOutcome(
            status=(
                SchemaSetupResult.ALREADY_PRESENT
                if existed
                else SchemaSetupResult.CREATED
            )
        )
    except Exception as exc:
        return SchemaSetupOutcome(status=SchemaSetupResult.FAILED, message=str(exc))
