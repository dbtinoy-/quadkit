"""Bearer-capable session identifiers must not be copied into logs/audits."""

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.session import manager as module


@pytest.mark.asyncio
async def test_session_events_use_noncredential_correlation_identifiers(monkeypatch):
    logger, audit = MagicMock(), AsyncMock()
    monkeypatch.setattr(module, "logger", logger)
    manager = module.SessionManagerImpl(audit_logger=audit)
    session = await manager.create_session("owner", {})
    await manager.verify_mfa(session.session_id)
    await manager.revoke_session(session.session_id)
    assert session.session_id not in repr(logger.mock_calls)
    assert session.session_id not in repr(audit.mock_calls)
    expected = "sha256:" + hashlib.sha256(session.session_id.encode()).hexdigest()
    assert audit.log.call_args.args[0].resource_id == expected
