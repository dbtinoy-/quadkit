"""Tests for events schema setup contributions."""

from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.cli.contributions import SchemaSetupResult
from quadkit.events.cli.schema_setup import ensure_saga_records


@pytest.mark.asyncio
async def test_ensure_saga_records_reports_created_when_absent():
    """Absent table yields CREATED."""
    db = AsyncMock()
    db.table_exists.return_value = False
    db.execute_query.return_value = None

    outcome = await ensure_saga_records(db)

    assert outcome.status == SchemaSetupResult.CREATED


@pytest.mark.asyncio
async def test_ensure_saga_records_reports_failure_message():
    """Failure propagates message into FAILED outcome."""
    db = AsyncMock()
    db.table_exists.side_effect = RuntimeError("connection refused")

    outcome = await ensure_saga_records(db)

    assert outcome.status == SchemaSetupResult.FAILED
    assert outcome.message == "connection refused"