"""Durable state storage for task workflows.

Provides the :class:`WorkflowStateStore` protocol and two concrete backends:

* :class:`InMemoryWorkflowStateStore` — for testing / single-process use.
* :class:`DatabaseWorkflowStateStore` — durable persistence via the DI-injected
  :class:`~quadkit.contracts.data.DatabaseProviderProtocol`.

Callers that want **resumable** workflows should:

1. Pass a stable ``workflow_id`` to the workflow constructor.
2. Provide a ``state_store`` so state is checkpointed after each step.
3. On restart, create a new instance with the same ``workflow_id`` — the
   workflow will skip already-completed steps and resume from where it left
   off, using the last completed step's output as the next step's input.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.logging import get_logger
import quadkit.serialization as json
from quadkit.tasks.dialect import translate_placeholders
from quadkit.tasks.workflows.core import StepResult, WorkflowResult, WorkflowStatus

if TYPE_CHECKING:
    from quadkit.contracts.data import DatabaseProviderProtocol

logger = get_logger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS workflow_states (
    workflow_id  TEXT      NOT NULL PRIMARY KEY,
    status       TEXT      NOT NULL,
    state_json   TEXT      NOT NULL,
    created_at   TIMESTAMP NOT NULL,
    updated_at   TIMESTAMP NOT NULL
)
"""

_UPSERT_SQL = (
    "INSERT INTO workflow_states "
    "(workflow_id, status, state_json, created_at, updated_at) "
    "VALUES (?, ?, ?, ?, ?) "
    "ON CONFLICT (workflow_id) DO UPDATE SET "
    "status = excluded.status, "
    "state_json = excluded.state_json, "
    "updated_at = excluded.updated_at"
)

_GET_SQL = "SELECT state_json FROM workflow_states WHERE workflow_id = ?"

_LIST_ACTIVE_SQL = (
    "SELECT workflow_id, status, state_json, created_at, updated_at "
    "FROM workflow_states "
    "WHERE status NOT IN ('completed', 'failed')"
)

_DELETE_SQL = "DELETE FROM workflow_states WHERE workflow_id = ?"

__all__ = [
    "DatabaseWorkflowStateStore",
    "InMemoryWorkflowStateStore",
    "WorkflowStateStore",
    "WorkflowSummary",
]


@dataclass
class WorkflowSummary:
    """Summary of a persisted workflow.

    Attributes:
        workflow_id: Unique workflow run identifier.
        status: Current workflow status.
        completed_steps: Names of steps that finished successfully.
        created_at: When the workflow first started executing.
        last_updated: When the state was most recently saved.
    """

    workflow_id: str
    status: WorkflowStatus
    completed_steps: list[str]
    created_at: datetime
    last_updated: datetime


@runtime_checkable
class WorkflowStateStore(Protocol):
    """Protocol for durable workflow state persistence.

    Implementations must provide ``save_state``, ``load_state``,
    ``list_active``, and ``delete_state``.  All methods are async.
    """

    async def save_state(self, workflow_id: str, result: WorkflowResult) -> None:
        """Persist (or overwrite) the current workflow state.

        Args:
            workflow_id: Unique identifier for this workflow run.
            result: Current :class:`~quadkit.tasks.workflows.core.WorkflowResult`
                snapshot including completed steps and their outputs.
        """
        ...

    async def load_state(self, workflow_id: str) -> WorkflowResult | None:
        """Load a previously saved workflow state.

        Args:
            workflow_id: Unique identifier for the workflow run.

        Returns:
            Saved :class:`~quadkit.tasks.workflows.core.WorkflowResult`, or
            ``None`` if no state has been persisted for this ID.
        """
        ...

    async def list_active(self) -> list[WorkflowSummary]:
        """Return summaries of all non-terminal workflows.

        Returns:
            :class:`WorkflowSummary` list for workflows in ``PENDING`` or
            ``RUNNING`` state.
        """
        ...

    async def delete_state(self, workflow_id: str) -> None:
        """Remove persisted state for a completed or abandoned workflow.

        Args:
            workflow_id: Unique identifier for the workflow run.
        """
        ...


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_result(result: WorkflowResult) -> str:
    """Convert a WorkflowResult to a JSON string for persistence.

    Serialisation uses the framework JSON backend, whose default encoder
    (``quadkit.serialization``'s ``json_serialize``) handles domain types
    consistently on both backends: UUID, datetime, Enum, Pydantic models,
    and objects exposing ``__dict__``. Genuinely unserializable step data
    raises ``TypeError`` — checkpointing fails loudly instead of corrupting
    resumed state with opaque strings.

    Args:
        result: WorkflowResult to serialize.

    Returns:
        JSON string representing the full workflow state.
    """
    payload: dict[str, Any] = {
        "workflow_id": result.workflow_id,
        "status": str(result.status),
        "total_duration_ms": result.total_duration_ms,
        "error": result.error,
        "steps": [
            {
                "step_name": s.step_name,
                "success": s.success,
                "data": s.data,
                "error": s.error,
                "duration_ms": s.duration_ms,
            }
            for s in result.steps
        ],
    }
    try:
        payload["final_result"] = result.final_result
    except (AttributeError, TypeError, KeyError):
        payload["final_result"] = None
    return json.dumps(payload).decode()


def _deserialize_result(state_json: str) -> WorkflowResult:
    """Reconstruct a WorkflowResult from a persisted JSON string.

    Args:
        state_json: JSON string produced by :func:`_serialize_result`.

    Returns:
        WorkflowResult with steps and metadata restored.
    """
    data = json.loads(state_json)
    steps = [
        StepResult(
            step_name=s["step_name"],
            success=s["success"],
            data=s.get("data"),
            error=s.get("error"),
            duration_ms=s.get("duration_ms", 0.0),
        )
        for s in data.get("steps", [])
    ]
    return WorkflowResult(
        workflow_id=data["workflow_id"],
        status=WorkflowStatus(data["status"]),
        steps=steps,
        final_result=data.get("final_result"),
        total_duration_ms=data.get("total_duration_ms", 0.0),
        error=data.get("error"),
    )


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


class InMemoryWorkflowStateStore:
    """In-memory :class:`WorkflowStateStore` for testing and single-process use.

    State is lost when the process exits.  Use
    :class:`DatabaseWorkflowStateStore` for durable across-restart persistence.
    """

    def __init__(self) -> None:
        """Create a new in-memory workflow state store."""
        self._states: dict[str, WorkflowResult] = {}
        self._created: dict[str, datetime] = {}

    async def save_state(self, workflow_id: str, result: WorkflowResult) -> None:
        """Persist the workflow result in memory.

        Args:
            workflow_id: Unique identifier for this workflow run.
            result: Current WorkflowResult snapshot.
        """
        if workflow_id not in self._created:
            self._created[workflow_id] = datetime.now(UTC)
        self._states[workflow_id] = result

    async def load_state(self, workflow_id: str) -> WorkflowResult | None:
        """Return a previously saved workflow result.

        Args:
            workflow_id: Unique identifier for the workflow run.

        Returns:
            Stored WorkflowResult or ``None`` if not found.
        """
        return self._states.get(workflow_id)

    async def list_active(self) -> list[WorkflowSummary]:
        """Return summaries of all non-terminal in-memory workflows.

        Returns:
            WorkflowSummary list for PENDING / RUNNING workflows.
        """
        active_statuses = {WorkflowStatus.PENDING, WorkflowStatus.RUNNING}
        return [
            WorkflowSummary(
                workflow_id=wid,
                status=result.status,
                completed_steps=[s.step_name for s in result.steps if s.success],
                created_at=self._created.get(wid, datetime.now(UTC)),
                last_updated=datetime.now(UTC),
            )
            for wid, result in self._states.items()
            if result.status in active_statuses
        ]

    async def delete_state(self, workflow_id: str) -> None:
        """Remove a workflow result from memory.

        Args:
            workflow_id: Unique identifier for the workflow run.
        """
        self._states.pop(workflow_id, None)
        self._created.pop(workflow_id, None)


class DatabaseWorkflowStateStore:
    """Durable :class:`WorkflowStateStore` backed by a relational database.

    Uses a single ``workflow_states`` table (created lazily on first use) to
    store JSON-serialized :class:`~quadkit.tasks.workflows.core.WorkflowResult`
    snapshots.  The database provider is injected by the DI container and must
    implement :class:`~quadkit.contracts.data.DatabaseProviderProtocol`.

    Resume support: once a workflow's state is saved here, create a new
    workflow instance with the same ``workflow_id``.  The workflow will call
    :meth:`load_state`, discover which steps already completed, and skip them.

    Args:
        db: Database provider resolved from the DI container.
    """

    def __init__(self, db: DatabaseProviderProtocol) -> None:
        """Create a database-backed workflow state store.

        Args:
            db: Database provider from the DI container.
        """
        self._db = db
        self._initialised = False

    def _sql(self, sql: str) -> str:
        """Translate ``?`` placeholders to the provider dialect style."""
        dialect = str(getattr(self._db, "name", "sqlite"))
        return translate_placeholders(sql, dialect)

    async def _ensure_table(self) -> None:
        """Create the workflow_states table if it does not yet exist."""
        if not self._initialised:
            await self._db.execute(self._sql(_CREATE_TABLE_SQL))
            self._initialised = True

    async def save_state(self, workflow_id: str, result: WorkflowResult) -> None:
        """Upsert the workflow state in the database.

        Args:
            workflow_id: Unique identifier for this workflow run.
            result: Current WorkflowResult snapshot.
        """
        await self._ensure_table()
        now = datetime.now(UTC)
        state_json = _serialize_result(result)
        await self._db.execute(
            self._sql(_UPSERT_SQL),
            [workflow_id, str(result.status), state_json, now, now],
        )
        logger.debug(
            "workflow_state.saved", workflow_id=workflow_id, status=str(result.status)
        )

    async def load_state(self, workflow_id: str) -> WorkflowResult | None:
        """Load and deserialize a workflow state from the database.

        Args:
            workflow_id: Unique identifier for the workflow run.

        Returns:
            Deserialized WorkflowResult or ``None`` if no state is stored.
        """
        await self._ensure_table()
        query_result = await self._db.execute_query(self._sql(_GET_SQL), [workflow_id])
        if not query_result.rows:
            return None
        state_json = query_result.rows[0]["state_json"]
        return _deserialize_result(state_json)

    async def list_active(self) -> list[WorkflowSummary]:
        """Return summaries of all non-terminal workflows from the database.

        Returns:
            WorkflowSummary list for PENDING / RUNNING workflows.
        """
        await self._ensure_table()
        query_result = await self._db.execute_query(self._sql(_LIST_ACTIVE_SQL))
        summaries = []
        for row in query_result.rows:
            result = _deserialize_result(row["state_json"])
            summaries.append(
                WorkflowSummary(
                    workflow_id=row["workflow_id"],
                    status=WorkflowStatus(row["status"]),
                    completed_steps=[s.step_name for s in result.steps if s.success],
                    created_at=row["created_at"],
                    last_updated=row["updated_at"],
                )
            )
        return summaries

    async def delete_state(self, workflow_id: str) -> None:
        """Delete a workflow state from the database.

        Args:
            workflow_id: Unique identifier for the workflow run.
        """
        await self._ensure_table()
        await self._db.execute(self._sql(_DELETE_SQL), [workflow_id])
        logger.debug("workflow_state.deleted", workflow_id=workflow_id)
