"""Tests for tasks schema setup contributions."""

from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.cli.contributions import SchemaSetupResult
from quadkit.tasks.cli.schema_setup import ensure_scheduled_jobs, ensure_workflow_states


@pytest.mark.asyncio
async def test_ensure_scheduled_jobs_reports_created_when_absent():
    """Absent table yields CREATED."""
    db = AsyncMock()
    db.table_exists.return_value = False
    db.execute.return_value = None

    outcome = await ensure_scheduled_jobs(db)

    assert outcome.status == SchemaSetupResult.CREATED


@pytest.mark.asyncio
async def test_ensure_workflow_states_reports_already_present():
    """Existing table yields ALREADY_PRESENT."""
    db = AsyncMock()
    db.table_exists.return_value = True
    db.execute.return_value = None

    outcome = await ensure_workflow_states(db)

    assert outcome.status == SchemaSetupResult.ALREADY_PRESENT


@pytest.mark.asyncio
async def test_ensure_scheduled_jobs_reports_failure_message():
    """Failure propagates message into FAILED outcome."""
    db = AsyncMock()
    db.table_exists.side_effect = RuntimeError("connection refused")

    outcome = await ensure_scheduled_jobs(db)

    assert outcome.status == SchemaSetupResult.FAILED
    assert outcome.message == "connection refused"