"""Tests for auth schema setup contributions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.cli.schema_setup import ensure_oauth_identities
from quadkit.contracts.cli.contributions import SchemaSetupResult


class _AsyncCtxManager:
    """Async context manager double for scoped_context()."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


@pytest.mark.asyncio
async def test_ensure_oauth_identities_reports_created_when_absent():
    """Absent table yields CREATED."""
    db = AsyncMock()
    db.table_exists.return_value = False
    conn = AsyncMock()
    db.get_scoped_connection.return_value = conn
    db.scoped_context = MagicMock(return_value=_AsyncCtxManager())

    outcome = await ensure_oauth_identities(db)

    assert outcome.status == SchemaSetupResult.CREATED


@pytest.mark.asyncio
async def test_ensure_oauth_identities_reports_failure_message():
    """Failure propagates message into FAILED outcome."""
    db = AsyncMock()
    db.table_exists.side_effect = RuntimeError("connection refused")

    outcome = await ensure_oauth_identities(db)

    assert outcome.status == SchemaSetupResult.FAILED
    assert outcome.message == "connection refused"
