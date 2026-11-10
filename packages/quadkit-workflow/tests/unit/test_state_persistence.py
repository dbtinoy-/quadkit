"""Unit tests for state transition persistence implementations."""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from quadkit.contracts.data import DatabaseProviderProtocol, QueryResult
from quadkit.workflow.state.persistence import DatabaseStatePersistence


class _NoopTransaction:
    """Minimal async context manager used for provider.transaction()."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _query_result(rows: list[dict[str, object]]) -> QueryResult:
    return QueryResult(
        rows=rows,
        row_count=len(rows),
        execution_time=0.0,
        success=True,
    )


@pytest.mark.asyncio
async def test_append_transition_persists_and_returns_next_version() -> None:
    provider = MagicMock(spec=DatabaseProviderProtocol)
    provider.transaction = MagicMock(return_value=_NoopTransaction())
    provider.execute = AsyncMock(return_value=_query_result([]))
    provider.execute_query = AsyncMock(return_value=_query_result([{"version": 0}]))
    provider.execute_insert = AsyncMock()

    persistence = DatabaseStatePersistence(provider)

    next_version = await persistence.append_transition(
        machine_id="order-1",
        from_state="idle",
        event="start",
        to_state="running",
        expected_version=0,
    )

    assert next_version == 1
    provider.execute.assert_awaited_once()
    provider.execute_insert.assert_awaited_once_with(
        "workflow_state_transitions",
        {
            "machine_id": "order-1",
            "version": 1,
            "from_state": "idle",
            "event": "start",
            "to_state": "running",
            "transitioned_at": ANY,
        },
    )


@pytest.mark.asyncio
async def test_append_transition_raises_on_optimistic_lock_conflict() -> None:
    provider = MagicMock(spec=DatabaseProviderProtocol)
    provider.transaction = MagicMock(return_value=_NoopTransaction())
    provider.execute = AsyncMock(return_value=_query_result([]))
    provider.execute_query = AsyncMock(return_value=_query_result([{"version": 2}]))
    provider.execute_insert = AsyncMock()

    persistence = DatabaseStatePersistence(provider)

    with pytest.raises(RuntimeError, match="Optimistic lock failed"):
        await persistence.append_transition(
            machine_id="order-1",
            from_state="idle",
            event="start",
            to_state="running",
            expected_version=1,
        )

    provider.execute_insert.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_transitions_maps_rows_to_records() -> None:
    provider = MagicMock(spec=DatabaseProviderProtocol)
    provider.transaction = MagicMock(return_value=_NoopTransaction())
    provider.execute = AsyncMock(return_value=_query_result([]))
    provider.execute_query = AsyncMock(
        return_value=_query_result(
            [
                {
                    "machine_id": "order-1",
                    "version": 1,
                    "from_state": "idle",
                    "event": "start",
                    "to_state": "running",
                    "transitioned_at": 100.0,
                },
                {
                    "machine_id": "order-1",
                    "version": 2,
                    "from_state": "running",
                    "event": "complete",
                    "to_state": "done",
                    "transitioned_at": 200.0,
                },
            ]
        )
    )
    provider.execute_insert = AsyncMock()

    persistence = DatabaseStatePersistence(provider)

    records = await persistence.load_transitions("order-1")

    assert len(records) == 2
    assert records[0].from_state == "idle"
    assert records[0].to_state == "running"
    assert records[1].from_state == "running"
    assert records[1].to_state == "done"


def test_invalid_table_name_is_rejected() -> None:
    provider = MagicMock(spec=DatabaseProviderProtocol)

    with pytest.raises(ValueError, match="Invalid table name"):
        DatabaseStatePersistence(provider, table_name="workflow-transitions")


class TestConcurrencyRace:
    """Optimistic-lock edge cases (round 13)."""

    def _provider(self, **overrides: object) -> MagicMock:
        provider = MagicMock(spec=DatabaseProviderProtocol)
        provider.transaction = MagicMock(return_value=_NoopTransaction())
        provider.execute = AsyncMock(return_value=_query_result([]))
        provider.execute_query = AsyncMock(return_value=_query_result([{"version": 0}]))
        provider.execute_insert = AsyncMock()
        for key, value in overrides.items():
            setattr(provider, key, value)
        return provider

    @pytest.mark.asyncio
    async def test_unique_violation_on_insert_is_a_conflict(self) -> None:
        """A concurrent writer winning the PK insert is the same conflict as
        a pre-check mismatch — driver-specific IntegrityError must map to
        the typed StateVersionConflictError, not escape raw."""
        import sqlite3

        from quadkit.workflow.state import StateVersionConflictError

        provider = self._provider(
            execute_query=AsyncMock(
                side_effect=[
                    _query_result([{"version": 0}]),  # pre-check
                    _query_result([{"version": 1}]),  # re-read after violation
                ]
            ),
            execute_insert=AsyncMock(
                side_effect=sqlite3.IntegrityError(
                    "UNIQUE constraint failed: workflow_state_transitions.machine_id"
                )
            ),
        )
        persistence = DatabaseStatePersistence(provider)

        with pytest.raises(StateVersionConflictError) as exc_info:
            await persistence.append_transition(
                machine_id="order-1",
                from_state="idle",
                event="start",
                to_state="running",
                expected_version=0,
            )

        assert exc_info.value.expected_version == 0
        assert exc_info.value.actual_version == 1
        # Still a RuntimeError for contracts-doc compatibility.
        assert isinstance(exc_info.value, RuntimeError)

    @pytest.mark.asyncio
    async def test_non_unique_insert_error_propagates(self) -> None:
        """Driver/infra errors are NOT version conflicts: they propagate
        untouched and trigger no spurious version re-read."""
        provider = self._provider(
            execute_insert=AsyncMock(side_effect=RuntimeError("disk full"))
        )
        persistence = DatabaseStatePersistence(provider)

        with pytest.raises(RuntimeError, match="disk full"):
            await persistence.append_transition(
                machine_id="order-1",
                from_state="idle",
                event="start",
                to_state="running",
                expected_version=0,
            )

        # Only the pre-check query ran — no re-read after the failure.
        assert provider.execute_query.await_count == 1

    @pytest.mark.asyncio
    async def test_postgres_placeholders_translated_in_queries(self) -> None:
        provider = self._provider(name="postgres")
        persistence = DatabaseStatePersistence(provider)

        await persistence.get_current_version("order-1")
        sql = provider.execute_query.await_args.args[0]
        assert "$1" in sql
        assert "?" not in sql
