"""Tests for notification schema setup contributions."""

from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.cli.contributions import SchemaSetupResult
from quadkit.contracts.data.sql.database import QueryResult
from quadkit.notification.cli.schema_setup import ensure_inbox_messages


@pytest.mark.asyncio
async def test_ensure_inbox_messages_reports_created_when_absent():
    """Absent table yields CREATED."""
    db = AsyncMock()
    db.table_exists.return_value = False
    db.execute_query.return_value = QueryResult(
        rows=[], row_count=0, execution_time=0.0, success=True
    )

    outcome = await ensure_inbox_messages(db)

    assert outcome.status == SchemaSetupResult.CREATED


@pytest.mark.asyncio
async def test_ensure_inbox_messages_reports_failure_message():
    """Failure propagates message into FAILED outcome."""
    db = AsyncMock()
    db.table_exists.side_effect = RuntimeError("connection refused")

    outcome = await ensure_inbox_messages(db)

    assert outcome.status == SchemaSetupResult.FAILED
    assert outcome.message == "connection refused"
