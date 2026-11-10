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
async def test_ensure_scheduled_jobs_reports_safe_failure_type():
    """Failure outcomes expose the exception type, not driver details."""
    private_error = "connection refused /srv/private/db.sqlite?secret=sentinel"
    db = AsyncMock()
    db.table_exists.side_effect = RuntimeError(private_error)

    outcome = await ensure_scheduled_jobs(db)

    assert outcome.status == SchemaSetupResult.FAILED
    assert outcome.message == "Schema setup failed (RuntimeError)"
    assert private_error not in outcome.message


@pytest.mark.asyncio
async def test_ensure_workflow_states_reports_safe_failure_type():
    """Workflow state schema errors also discard raw driver messages."""
    db = AsyncMock()
    db.table_exists.side_effect = OSError("PRIVATE_PATH_SENTINEL /srv/private")

    outcome = await ensure_workflow_states(db)

    assert outcome.status == SchemaSetupResult.FAILED
    assert outcome.message == "Schema setup failed (OSError)"
    assert "PRIVATE_PATH_SENTINEL" not in outcome.message